"""DB 컬럼에 쓰는 열거형.

SQLAlchemy `Enum` 대신 `StrEnum` + `String` 컬럼을 쓴다 (루트 CLAUDE.md 규칙).
Postgres enum 타입은 값을 추가할 때마다 `ALTER TYPE` 마이그레이션이 필요하고,
Supabase 쪽에서 타입을 참조하면 되돌리기가 번거롭다. 값 검증은 Pydantic 스키마와
DB CHECK 제약 양쪽에서 한다.
"""

from __future__ import annotations

from enum import StrEnum


class VideoStatus(StrEnum):
    """영상 처리 파이프라인의 단계.

    클라이언트는 Supabase Realtime 으로 이 값의 변화를 구독한다. 그래서 단계 이름이
    곧 사용자에게 보이는 진행 표시가 된다 — 내부 구현 단위가 아니라 "지금 무엇을
    기다리는지"가 드러나는 이름을 쓴다.
    """

    PENDING = "pending"
    """큐에 들어갔고 아직 아무것도 시작하지 않음."""

    DOWNLOADING = "downloading"
    """yt-dlp 내려받기 중."""

    ANALYZING = "analyzing"
    """Gemini 분석 중 (A안: 영상 직접 입력 / B안: 모달리티별)."""

    RESOLVING = "resolving"
    """후보 dedup + Google Places 지오코딩 중."""

    COMPLETED = "completed"
    """places 가 모두 적재됨."""

    FAILED = "failed"
    """복구 불가 실패. 사유는 `videos.error_message`."""


class SourceModality(StrEnum):
    """장소 후보가 어느 신호에서 나왔는지.

    A안(Gemini 단일 영상 입력)만 쓰는 지금은 전부 `VIDEO` 로 들어온다. B안(멀티모달
    앙상블)으로 갈 때 모달리티별 정확도를 **마이그레이션 없이** 비교하려고 지금부터
    컬럼을 둔다. `pipeline.types.PlaceCandidate.source_modality` 와 같은 값 집합이다.
    """

    AUDIO = "audio"
    """나레이션·발화 (Whisper 전사 → 텍스트 분석)."""

    VISION = "vision"
    """프레임 이미지 (비전 프론트엔드 → Gemini Vision)."""

    TEXT = "text"
    """영상 설명·자막·댓글 등 부가 텍스트."""

    VIDEO = "video"
    """영상을 통째로 넣은 단일 호출 (A안)."""
