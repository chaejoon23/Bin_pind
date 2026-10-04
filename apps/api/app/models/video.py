"""`videos` — 사용자가 넣은 YouTube 영상 하나와 그 처리 상태."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import VideoStatus

if TYPE_CHECKING:
    from app.models.place import Place

__all__ = ["Video"]


class Video(UUIDMixin, TimestampMixin, Base):
    """처리 대상 영상 한 편.

    행을 만드는 쪽은 **클라이언트**다 (Supabase 에 직접 INSERT). 그 INSERT 가 Database
    Webhook 을 통해 FastAPI 를 깨우고, FastAPI 가 같은 행의 `status` 를 옮겨 적으며
    파이프라인을 진행한다. 그래서 이 테이블은 작업 큐와 사용자에게 보이는 상태를
    겸한다.
    """

    __tablename__ = "videos"

    # ── 소유자 ───────────────────────────────────────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    """`auth.users.id`.

    **DB 레벨 FK 를 걸지 않는다.** `auth` 스키마는 Supabase 가 관리하므로 Alembic 이
    소유권을 주장하면 안 되고, 로컬 Postgres(docker-compose)에는 그 스키마가 아예
    없어 마이그레이션이 깨진다. 소유권 강제는 RLS(`auth.uid() = user_id`)와 FastAPI
    의 JWT 검증이 맡는다. 사용자 삭제 시 정리는 Supabase 쪽 트리거에서 처리한다.
    """

    # ── 영상 식별 ────────────────────────────────────────────────────────────
    youtube_url: Mapped[str] = mapped_column(Text, nullable=False)
    """사용자가 붙여넣은 원문 URL (단축·타임스탬프·플레이리스트 파라미터 포함 가능)."""

    youtube_id: Mapped[str] = mapped_column(String(16), nullable=False)
    """URL 에서 추출한 11자 영상 ID. 중복 판정과 캐시 키의 기준."""

    # ── 메타데이터 (yt-dlp 가 채움, 내려받기 전에는 비어 있음) ───────────────
    title: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str | None] = mapped_column(Text)
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)

    # ── 처리 상태 ────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=VideoStatus.PENDING,
        server_default=VideoStatus.PENDING,
    )
    """`VideoStatus` 값. CHECK 제약으로 DB 에서도 막는다 (Realtime 구독 대상)."""

    error_message: Mapped[str | None] = mapped_column(Text)
    """`status = 'failed'` 일 때의 사유. 사용자에게 보여줄 문장."""

    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """`completed` 또는 `failed` 로 끝난 시각."""

    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    """이 영상에 실제로 쓴 AI 비용.

    `cost_guard` 는 호출 **전에** 추정치로 막지만, 추정이 맞았는지는 사후에만 안다.
    실측을 남겨 두면 `MAX_COST_PER_VIDEO_USD` 를 감으로 정하지 않을 수 있다.
    """

    places: Mapped[list[Place]] = relationship(
        back_populates="video", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        # 같은 사용자가 같은 영상을 두 번 넣으면 새 행이 아니라 기존 행을 재사용한다.
        # 웹훅이 중복 발화해도 안전해지고(멱등), 실패한 영상의 재시도는 같은 행의
        # status 를 되돌리는 일이 된다. 다른 사용자가 같은 영상을 넣는 건 허용.
        UniqueConstraint("user_id", "youtube_id", name="videos_user_youtube_uniq"),
        CheckConstraint(
            "status IN ('pending', 'downloading', 'analyzing', 'resolving', 'completed', 'failed')",
            name="videos_status_check",
        ),
        CheckConstraint("duration_sec IS NULL OR duration_sec > 0", name="videos_duration_check"),
        CheckConstraint("cost_usd IS NULL OR cost_usd >= 0", name="videos_cost_check"),
        # RLS 정책이 모든 질의에 user_id 조건을 붙이므로 이 인덱스는 사실상 필수다.
        Index("videos_user_id_idx", "user_id"),
        Index("videos_youtube_id_idx", "youtube_id"),
    )

    def __repr__(self) -> str:
        return f"<Video {self.youtube_id} {self.status}>"
