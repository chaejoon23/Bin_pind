"""`places` — 한 영상에서 추출·확정된 장소 하나."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import SourceModality

if TYPE_CHECKING:
    from app.models.video import Video

__all__ = ["Place"]


class Place(UUIDMixin, TimestampMixin, Base):
    """지도에 꽂히는 핀 하나.

    파이프라인이 뽑은 `PlaceCandidate` 가 dedup 과 지오코딩을 거쳐 여기 적재된다.
    쓰기는 FastAPI(service_role)만 하고, 클라이언트는 자기 영상에 속한 행만 읽는다.
    """

    __tablename__ = "places"

    video_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        # 이름을 명시한다 — 익명 제약은 Postgres 가 자동 이름을 붙여서, 나중에
        # 되돌리는 마이그레이션에서 무엇을 drop 할지 코드만 보고 알 수 없다.
        ForeignKey("videos.id", ondelete="CASCADE", name="places_video_id_fkey"),
        nullable=False,
    )

    # ── 장소 정보 ────────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(Text, nullable=False)
    """지오코딩이 성공하면 Google Places 의 공식 명칭, 실패하면 추출된 이름 그대로."""

    category: Mapped[str | None] = mapped_column(Text)
    """카페·식당·전시장 등. Google Places 타입을 쓰되 없으면 모델이 말한 분류."""

    address: Mapped[str | None] = mapped_column(Text)

    google_place_id: Mapped[str | None] = mapped_column(String(64))
    """지오코딩 성공 시의 Place ID. 같은 영상 안 중복 제거의 기준(아래 UNIQUE)."""

    geom: Mapped[WKBElement | None] = mapped_column(
        # spatial_index=False: GeoAlchemy2 가 자동으로 만드는 `idx_places_geom` 대신
        # 아래 __table_args__ 에서 이름을 지정해 한 개만 만든다 (중복 인덱스 방지).
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    """WGS84 좌표.

    `geometry` 가 아니라 `geography` 다 — 미터 단위 거리·반경 질의(`ST_DWithin`)를
    투영 걱정 없이 쓰기 위해서다. 지오코딩이 실패한 장소는 이름만 남기고 좌표는
    NULL 로 둔다(지도에는 못 꽂지만 영상 구간 이동은 된다).
    """

    # ── 출처·신뢰도 (B안 비교 실험용) ───────────────────────────────────────
    source_modality: Mapped[str] = mapped_column(
        String(8), nullable=False, default=SourceModality.VIDEO, server_default=SourceModality.VIDEO
    )
    """`SourceModality` 값. A안만 쓰는 지금은 전부 `video`."""

    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    """모델이 말한 0~1 신뢰도. 지도에서 흐리게 표시할지, 아예 숨길지의 기준."""

    raw_extracted_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    """모델이 근거로 읽은 원문 (간판 문자열·나레이션 조각).

    오탐을 사후에 추적하는 유일한 단서다. 정규화된 `name` 만 남기면 "왜 이 장소가
    나왔는지"를 되짚을 수 없다.
    """

    # ── 영상 안 위치 ─────────────────────────────────────────────────────────
    context_start_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    context_end_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    """마커를 눌렀을 때 이동할 구간. 서비스의 핵심 동작이라 NULL 을 허용하지 않는다."""

    video: Mapped[Video] = relationship(back_populates="places")

    __table_args__ = (
        # 같은 영상에서 같은 Place ID 가 두 번 나오면 같은 가게다 (등장 구간만 다름).
        # google_place_id 가 NULL 인 행은 Postgres 규칙상 서로 충돌하지 않으므로,
        # 지오코딩 실패 장소는 이 제약에 걸리지 않는다.
        UniqueConstraint("video_id", "google_place_id", name="places_video_google_uniq"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="places_confidence_check"),
        CheckConstraint("context_start_sec >= 0", name="places_context_start_check"),
        CheckConstraint("context_end_sec >= context_start_sec", name="places_context_order_check"),
        CheckConstraint(
            "source_modality IN ('audio', 'vision', 'text', 'video')",
            name="places_source_modality_check",
        ),
        Index("places_video_id_idx", "video_id"),
        Index("places_google_place_id_idx", "google_place_id"),
        # 반경 검색(`ST_DWithin`)용. GeoAlchemy2 가 Geography 컬럼에 자동으로 GIST
        # 인덱스를 만들지만(`spatial_index=True` 기본값), 이름을 우리가 정해 두면
        # 마이그레이션 diff 와 supabase/CLAUDE.md 의 규약이 일치한다.
        Index("places_geom_idx", "geom", postgresql_using="gist"),
    )

    def __repr__(self) -> str:
        return f"<Place {self.name!r} video={self.video_id}>"
