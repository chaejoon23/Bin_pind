"""프레임 임베더.

중복 프레임 제거의 품질은 "두 프레임이 같은 장면인가"를 얼마나 잘 재는지에 달려 있다.
두 가지 구현을 같은 `Embedder` 프로토콜 뒤에 두고 런타임에 교체한다.

- `PerceptualEmbedder` (기본): pHash + HSV 히스토그램. 추가 의존성 없음, CPU에서 프레임당
  1ms 미만. 컷 전환은 잘 잡지만 같은 가게를 다른 각도에서 찍은 프레임은 다른 장면으로 본다.
- `Dinov3Embedder` (옵션): DINOv3 ViT-S/16 (Simeoni et al., arXiv:2508.10104) CLS 임베딩.
  자기지도 학습 특징이라 조명·각도·스케일 변화에 강해 "같은 장소"를 훨씬 잘 묶는다.
  대신 torch + transformers가 필요하다 → `pip install -e '.[vision-embed]'`.

두 구현 모두 L2 정규화된 벡터를 돌려주므로 유사도는 항상 코사인으로 계산한다.
`PerceptualEmbedder`는 두 블록을 각각 정규화한 뒤 가중치를 곱해 이어 붙이므로, 코사인 값이
"해밍 유사도와 히스토그램 유사도의 가중 평균"과 같은 의미를 갖는다.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import cv2
import numpy as np
import structlog
from numpy.typing import NDArray

logger = structlog.get_logger(__name__)

BgrImage = NDArray[np.uint8]
Embedding = NDArray[np.float32]

DEFAULT_DINOV3_MODEL = "facebook/dinov3-vits16-pretrain-lvd1689m"


@runtime_checkable
class Embedder(Protocol):
    """프레임 → L2 정규화 임베딩."""

    @property
    def name(self) -> str:
        """로그·벤치마크 표에 찍히는 식별자."""
        ...

    def embed(self, images: list[BgrImage]) -> Embedding:
        """(N, D) float32 행렬을 반환한다. 각 행은 L2 정규화되어 있다."""
        ...


def _l2_normalize(matrix: Embedding) -> Embedding:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    normalized: Embedding = (matrix / np.maximum(norms, 1e-8)).astype(np.float32)
    return normalized


def phash_bits(image: BgrImage, *, hash_size: int = 8, dct_size: int = 32) -> Embedding:
    """DCT 기반 perceptual hash를 ±1 벡터로 반환한다.

    Zauner, "Implementation and Benchmarking of Perceptual Image Hash Functions" (2010)의
    pHash. 저주파 DCT 계수를 중앙값으로 이진화해 밝기·대비 변화에 둔감한 서명을 만든다.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (dct_size, dct_size), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(resized.astype(np.float32))
    block = dct[:hash_size, :hash_size].flatten()
    # DC 성분은 전체 밝기라 제외한다.
    coeffs = block[1:]
    median = float(np.median(coeffs))
    bits = np.where(coeffs > median, 1.0, -1.0).astype(np.float32)
    return bits


def hsv_histogram(image: BgrImage, *, bins: tuple[int, int, int] = (8, 8, 4)) -> Embedding:
    """HSV 3D 히스토그램. 장면의 색 구성을 요약한다."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, list(bins), [0, 180, 0, 256, 0, 256])
    flat = hist.flatten().astype(np.float32)
    total = float(flat.sum())
    return flat / total if total > 0 else flat


class PerceptualEmbedder:
    """pHash + HSV 히스토그램 기반 기본 임베더. 외부 모델 가중치 불필요."""

    def __init__(self, *, hash_weight: float = 0.6, color_weight: float = 0.4) -> None:
        """가중치를 정하고 임베더를 초기화한다.

        Args:
            hash_weight: 구조(pHash) 블록 가중치.
            color_weight: 색(히스토그램) 블록 가중치.
        """
        total = hash_weight + color_weight
        self._hash_weight = hash_weight / total
        self._color_weight = color_weight / total

    @property
    def name(self) -> str:
        return "perceptual(phash+hsv)"

    def embed(self, images: list[BgrImage]) -> Embedding:
        rows: list[Embedding] = []
        for image in images:
            bits = phash_bits(image)
            bits = bits / max(float(np.linalg.norm(bits)), 1e-8)
            color = hsv_histogram(image)
            color = color / max(float(np.linalg.norm(color)), 1e-8)
            rows.append(
                np.concatenate(
                    [bits * np.sqrt(self._hash_weight), color * np.sqrt(self._color_weight)]
                ).astype(np.float32)
            )
        return _l2_normalize(np.vstack(rows).astype(np.float32))


class Dinov3Embedder:
    """DINOv3 CLS 임베딩. `[vision-embed]` extra 설치 시 사용 가능.

    같은 장소를 다른 각도/조명에서 찍은 프레임을 하나의 샷으로 묶는 능력이 pHash보다 크게
    높다. 가중치는 첫 호출 때 Hugging Face 허브에서 내려온다(ViT-S/16, 약 86MB).
    """

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_DINOV3_MODEL,
        device: str | None = None,
        batch_size: int = 16,
    ) -> None:
        """모델을 내려받아 추론 모드로 올린다.

        Args:
            model_id: Hugging Face 모델 ID.
            device: "cuda" / "cpu". None이면 자동 선택.
            batch_size: 추론 배치 크기.
        """
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModel
        except ImportError as exc:  # pragma: no cover - 옵션 의존성
            raise ImportError(
                "Dinov3Embedder 는 torch 와 transformers 가 필요합니다. "
                "apps/api 에서 `pip install -e '.[vision-embed]'` 를 실행하세요."
            ) from exc

        self._torch = torch
        self._model_id = model_id
        self._batch_size = batch_size
        self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._processor = AutoImageProcessor.from_pretrained(model_id)
        self._model = AutoModel.from_pretrained(model_id).to(self._device).eval()
        logger.info("dinov3_loaded", model_id=model_id, device=self._device)

    @property
    def name(self) -> str:
        return f"dinov3({self._model_id.split('/')[-1]})"

    def embed(self, images: list[BgrImage]) -> Embedding:
        rgb = [cv2.cvtColor(image, cv2.COLOR_BGR2RGB) for image in images]
        outputs: list[NDArray[np.float32]] = []
        with self._torch.inference_mode():
            for start in range(0, len(rgb), self._batch_size):
                batch = rgb[start : start + self._batch_size]
                inputs = self._processor(images=batch, return_tensors="pt").to(self._device)
                hidden = self._model(**inputs).last_hidden_state
                cls = hidden[:, 0, :]  # CLS 토큰
                outputs.append(cls.float().cpu().numpy().astype(np.float32))
        return _l2_normalize(np.vstack(outputs).astype(np.float32))


def build_embedder(kind: str = "auto") -> Embedder:
    """이름으로 임베더를 만든다.

    Args:
        kind: "perceptual" | "dinov3" | "auto". "auto"는 DINOv3를 먼저 시도하고
            의존성이 없으면 조용히 perceptual로 내려간다.
    """
    if kind == "perceptual":
        return PerceptualEmbedder()
    if kind == "dinov3":
        return Dinov3Embedder()
    if kind == "auto":
        try:
            return Dinov3Embedder()
        except ImportError:
            logger.info("dinov3_unavailable_fallback_perceptual")
            return PerceptualEmbedder()
    raise ValueError(f"알 수 없는 임베더: {kind}")
