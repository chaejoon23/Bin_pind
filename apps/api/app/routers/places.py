"""`GET /api/v1/places` — Phase 1-2 목 라우터.

**아직 DB 를 읽지 않는다.** 이 단계의 목적은 응답 모양을 확정해 OpenAPI 로 내보내고,
그걸로 `packages/shared-types/src/api.ts` 를 생성해 web·extension 이 실제 데이터
없이도 화면을 만들 수 있게 하는 것이다. Phase 3-4 에서 본문만 실제 질의로 바꾼다.

목 응답이 거짓 안심을 주지 않도록 두 가지를 지킨다.

- 반환 타입은 실제 스키마(`Page[PlaceRead]`)다. 모양이 틀리면 지금 터진다.
- 좌표가 없는 장소(지오코딩 실패)를 더미에 하나 섞는다. 지도 쪽에서 `lat`/`lng`
  가 null 인 경우를 처음부터 다루게 만든다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.models.enums import SourceModality
from app.schemas.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page, decode_cursor
from app.schemas.place import PlaceRead

router = APIRouter(prefix="/api/v1", tags=["places"])

_MOCK_VIDEO_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
_MOCK_CREATED_AT = datetime(2026, 10, 4, 3, 0, tzinfo=UTC)

_MOCK_PLACES: list[PlaceRead] = [
    PlaceRead(
        id=uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001"),
        video_id=_MOCK_VIDEO_ID,
        name="을지다방",
        category="cafe",
        address="서울 중구 을지로3가 315-6",
        google_place_id="ChIJmock0000000000000001",
        lat=37.5665,
        lng=126.9910,
        confidence=0.92,
        source_modality=SourceModality.VIDEO,
        context_start_sec=132,
        context_end_sec=148,
        raw_extracted_text="을지다방",
        created_at=_MOCK_CREATED_AT,
    ),
    PlaceRead(
        id=uuid.UUID("aaaaaaaa-0000-4000-8000-000000000002"),
        video_id=_MOCK_VIDEO_ID,
        name="커피한약방",
        category="cafe",
        address="서울 중구 삼각동 115",
        google_place_id="ChIJmock0000000000000002",
        lat=37.5673,
        lng=126.9842,
        confidence=0.78,
        source_modality=SourceModality.VIDEO,
        context_start_sec=301,
        context_end_sec=330,
        raw_extracted_text="커피한약방 COFFEE HANYAKBANG",
        created_at=_MOCK_CREATED_AT,
    ),
    PlaceRead(
        # 지오코딩 실패 사례 — 이름과 영상 구간은 있고 좌표가 없다.
        id=uuid.UUID("aaaaaaaa-0000-4000-8000-000000000003"),
        video_id=_MOCK_VIDEO_ID,
        name="이름만 읽힌 가게",
        category=None,
        address=None,
        google_place_id=None,
        lat=None,
        lng=None,
        confidence=0.41,
        source_modality=SourceModality.VIDEO,
        context_start_sec=512,
        context_end_sec=515,
        raw_extracted_text="OO상회",
        created_at=_MOCK_CREATED_AT,
    ),
]


@router.get(
    "/places",
    response_model=Page[PlaceRead],
    summary="장소 목록 (Phase 1-2 목 응답)",
    description=(
        "지도에 꽂을 장소를 커서 페이지네이션으로 돌려준다. "
        "현재는 고정된 더미 데이터이며 `video_id` 필터만 흉내낸다."
    ),
)
async def list_places(
    video_id: Annotated[uuid.UUID | None, Query(description="이 영상의 장소만")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: Annotated[str | None, Query(description="이전 응답의 next_cursor")] = None,
) -> Page[PlaceRead]:
    """목 응답. 질의는 Phase 3-4 에서 연결한다."""
    if cursor is not None and decode_cursor(cursor) is None:
        # 손으로 고친 커서가 500 으로 새지 않게 여기서 400 으로 바꾼다.
        raise HTTPException(status_code=400, detail="cursor 형식이 올바르지 않습니다")

    items = _MOCK_PLACES
    if video_id is not None:
        items = [place for place in items if place.video_id == video_id]
    return Page(items=items[:limit], next_cursor=None)
