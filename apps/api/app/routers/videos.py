"""`/api/v1/videos` — Phase 1-2 목 라우터 + URL 해석.

`videos` 에 `UNIQUE (user_id, youtube_id)` 를 걸었기 때문에, **INSERT 하는 쪽이
youtube_id 를 알고 있어야** 한다(PROGRESS.md ADR 2026-10-04). INSERT 하는 쪽은
클라이언트다 — web 과 extension 둘 다. 추출 규칙을 양쪽에 복사해 두면 한쪽만
고쳐지는 날이 온다(단축 URL, `/shorts/`, `/live/` 가 계속 늘어난다).

그래서 규칙은 `schemas/video.py` 한 곳에 두고, `POST /videos/resolve` 로 노출한다.
클라이언트는 URL 을 붙여넣은 직후 한 번 호출해 `youtube_id` 를 받고, 그 값으로
Supabase 에 INSERT 한다. 왕복이 한 번 늘지만 규칙이 갈라지지 않는다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter

from app.models.enums import VideoStatus
from app.schemas.video import VideoCreate, VideoRead

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


@router.post(
    "/resolve",
    response_model=VideoCreate,
    summary="YouTube URL → 영상 ID",
    description=(
        "URL 에서 11자 영상 ID 를 뽑아 돌려준다. YouTube 영상 URL 이 아니면 422. "
        "클라이언트는 이 값을 Supabase `videos` INSERT 에 쓴다."
    ),
)
async def resolve_video_url(payload: VideoCreate) -> VideoCreate:
    """검증은 `VideoCreate` 의 validator 가 전부 한다 — 여기선 되돌려주기만."""
    return payload


@router.get(
    "/{video_id}",
    response_model=VideoRead,
    summary="영상 상태 (Phase 1-2 목 응답)",
    description="현재는 고정된 더미 데이터. Phase 3-4 에서 실제 질의로 바꾼다.",
)
async def get_video(video_id: uuid.UUID) -> VideoRead:
    """목 응답. `status` 는 Realtime 으로 구독하는 값과 같은 모양이다."""
    return VideoRead(
        id=video_id,
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        youtube_id="dQw4w9WgXcQ",
        title="을지로 카페 투어 브이로그",
        channel="mock channel",
        duration_sec=742,
        thumbnail_url="https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
        status=VideoStatus.COMPLETED,
        error_message=None,
        processed_at=datetime(2026, 10, 4, 3, 2, tzinfo=UTC),
        created_at=datetime(2026, 10, 4, 3, 0, tzinfo=UTC),
    )
