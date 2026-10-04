"""`videos` DTO. Read / Create 분리 (apps/api/CLAUDE.md)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.models.enums import VideoStatus

__all__ = ["VideoCreate", "VideoRead", "extract_youtube_id"]

#: watch?v=, youtu.be/, /shorts/, /embed/, /live/ 를 모두 받는다.
_YOUTUBE_ID = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:[^&]*&)*v=|shorts/|embed/|live/)|youtu\.be/)"
    r"(?P<id>[0-9A-Za-z_-]{11})"
)


def extract_youtube_id(url: str) -> str | None:
    """URL 에서 11자 영상 ID. 못 찾으면 None.

    `videos` 에 `UNIQUE (user_id, youtube_id)` 가 걸려 있어 이 값이 중복 판정의
    기준이다(PROGRESS.md ADR 2026-10-04). 같은 영상이 단축 URL·타임스탬프·
    플레이리스트 파라미터를 달고 들어와도 같은 ID 로 접혀야 한다.
    """
    match = _YOUTUBE_ID.search(url)
    return match.group("id") if match else None


class VideoCreate(BaseModel):
    """영상 등록 요청.

    실제 INSERT 는 클라이언트가 Supabase 에 직접 한다(그 INSERT 가 Webhook 으로
    FastAPI 를 깨운다). 이 스키마는 그 전에 URL 을 검증하고 `youtube_id` 를
    뽑아 주는 쪽에서 쓴다 — 추출 규칙이 web·extension·API 세 곳에 흩어지지 않게
    OpenAPI 로 내보내 공유한다.
    """

    youtube_url: HttpUrl
    youtube_id: str = Field(default="", pattern=r"^[0-9A-Za-z_-]{0,11}$")

    @model_validator(mode="after")
    def _derive_youtube_id(self) -> Self:
        extracted = extract_youtube_id(str(self.youtube_url))
        if extracted is None:
            raise ValueError("YouTube 영상 URL 이 아닙니다 (11자 영상 ID 를 찾지 못했습니다)")
        if self.youtube_id and self.youtube_id != extracted:
            raise ValueError(f"youtube_id 가 URL 과 다릅니다 (URL: {extracted})")
        self.youtube_id = extracted
        return self


class VideoRead(BaseModel):
    """영상 한 편의 현재 상태.

    `status` 를 Supabase Realtime 으로 구독하는 쪽이 보는 모양과 같다.
    `cost_usd` 는 넣지 않는다 — 비용 상한을 조정하기 위한 운영 지표이고 화면에 쓸
    곳이 없다. 민감한 값은 아니라 RLS 쪽에서는 SELECT 를 막지 않았다(막으면
    supabase-js 의 `select('*')` 가 전부 깨진다).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    youtube_url: str
    youtube_id: str
    title: str | None = None
    channel: str | None = None
    duration_sec: int | None = None
    thumbnail_url: str | None = None
    status: VideoStatus
    error_message: str | None = None
    processed_at: datetime | None = None
    created_at: datetime
