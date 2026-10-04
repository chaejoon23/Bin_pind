"""DTO 직렬화 — 좌표 변환·커서·URL 해석 (app/schemas)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.models.enums import SourceModality, VideoStatus
from app.schemas import (
    Page,
    PlaceCreate,
    PlaceRead,
    VideoCreate,
    VideoRead,
    decode_cursor,
    encode_cursor,
    extract_youtube_id,
    lat_lng_to_point,
    point_to_lat_lng,
)
from geoalchemy2.elements import WKBElement
from pydantic import ValidationError

SEOUL_LAT, SEOUL_LNG = 37.5665, 126.9780


class _FakePlaceRow:
    """Place ORM 인스턴스 흉내. `from_attributes` 경로를 DB 없이 태운다."""

    def __init__(self, geom: WKBElement | None) -> None:
        self.id = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
        self.video_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        self.name = "을지다방"
        self.category = "cafe"
        self.address = "서울 중구"
        self.google_place_id = "ChIJtest"
        self.geom = geom
        self.confidence = 0.9
        self.source_modality = SourceModality.VIDEO
        self.context_start_sec = 10
        self.context_end_sec = 20
        self.raw_extracted_text = "을지다방"
        self.created_at = datetime(2026, 10, 4, tzinfo=UTC)


# ── 좌표 왕복 ─────────────────────────────────────────────────────────────────


def test_lat_lng_round_trip_keeps_order() -> None:
    """(lat, lng) → POINT → (lat, lng) 가 순서를 뒤집지 않는다.

    PostGIS 는 (경도, 위도), 지도 API 는 (위도, 경도)다. 서울처럼 두 값이 모두
    유효 범위면 뒤집혀도 예외가 없고 핀만 엉뚱한 곳에 꽂힌다 — 그래서 왕복으로 고정.
    """
    point = lat_lng_to_point(SEOUL_LAT, SEOUL_LNG)
    assert point is not None
    assert point_to_lat_lng(point) == (SEOUL_LAT, SEOUL_LNG)


def test_point_wkt_puts_longitude_first() -> None:
    point = lat_lng_to_point(SEOUL_LAT, SEOUL_LNG)
    assert point is not None
    assert str(point.data) == f"POINT({SEOUL_LNG} {SEOUL_LAT})"
    assert point.srid == 4326


def test_lat_lng_to_point_needs_both_values() -> None:
    assert lat_lng_to_point(SEOUL_LAT, None) is None
    assert lat_lng_to_point(None, SEOUL_LNG) is None
    assert lat_lng_to_point(None, None) is None


def test_point_to_lat_lng_passes_through_none() -> None:
    assert point_to_lat_lng(None) is None


def test_decodes_postgis_ewkb_hex() -> None:
    """DB 가 실제로 돌려주는 모양(SRID 가 박힌 EWKB hex)을 읽는다."""
    point = lat_lng_to_point(SEOUL_LAT, SEOUL_LNG)
    assert point is not None
    # WKT → EWKB hex 로 바꿔 넣어도 같은 좌표가 나와야 한다.
    from shapely import wkb as shapely_wkb
    from shapely.geometry import Point

    ewkb_hex = shapely_wkb.dumps(Point(SEOUL_LNG, SEOUL_LAT), hex=True, srid=4326)
    assert point_to_lat_lng(WKBElement(ewkb_hex, srid=4326)) == (SEOUL_LAT, SEOUL_LNG)


# ── PlaceRead ─────────────────────────────────────────────────────────────────


def test_place_read_unpacks_geom_from_orm_object() -> None:
    geom = lat_lng_to_point(SEOUL_LAT, SEOUL_LNG)
    assert geom is not None
    from shapely import wkb as shapely_wkb
    from shapely.geometry import Point

    stored = WKBElement(
        shapely_wkb.dumps(Point(SEOUL_LNG, SEOUL_LAT), hex=True, srid=4326), srid=4326
    )
    place = PlaceRead.model_validate(_FakePlaceRow(stored))
    assert (place.lat, place.lng) == (SEOUL_LAT, SEOUL_LNG)
    assert "geom" not in place.model_dump(), "WKB 를 API 표면에 흘리지 않는다"


def test_place_read_handles_failed_geocoding() -> None:
    place = PlaceRead.model_validate(_FakePlaceRow(None))
    assert place.lat is None
    assert place.lng is None
    assert place.name == "을지다방", "좌표가 없어도 이름과 구간은 남는다"
    assert place.context_end_sec == 20


def test_place_rejects_half_coordinate() -> None:
    with pytest.raises(ValidationError, match="둘 다"):
        PlaceCreate(name="가게", lat=SEOUL_LAT, context_start_sec=0, context_end_sec=1)


def test_place_rejects_reversed_context() -> None:
    with pytest.raises(ValidationError, match="앞설 수 없습니다"):
        PlaceCreate(name="가게", context_start_sec=30, context_end_sec=10)


@pytest.mark.parametrize(("lat", "lng"), [(91.0, 0.0), (-91.0, 0.0), (0.0, 181.0), (0.0, -181.0)])
def test_place_rejects_out_of_range_coordinates(lat: float, lng: float) -> None:
    with pytest.raises(ValidationError):
        PlaceCreate(name="가게", lat=lat, lng=lng, context_start_sec=0, context_end_sec=1)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_place_rejects_out_of_range_confidence(confidence: float) -> None:
    with pytest.raises(ValidationError):
        PlaceCreate(name="가게", confidence=confidence, context_start_sec=0, context_end_sec=1)


def test_place_defaults_to_video_modality() -> None:
    """A안(Gemini 단일 영상 입력)이 현재 유일한 경로."""
    place = PlaceCreate(name="가게", context_start_sec=0, context_end_sec=1)
    assert place.source_modality is SourceModality.VIDEO


# ── Video ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ&t=90s",
        "https://www.youtube.com/watch?list=PLxxxx&v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?si=abcdef",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
    ],
)
def test_extract_youtube_id_folds_every_url_shape(url: str) -> None:
    """같은 영상이 어떤 URL 로 들어와도 같은 ID 로 접힌다.

    `UNIQUE (user_id, youtube_id)` 가 중복 판정의 기준이라, 여기서 갈라지면
    같은 영상이 두 행이 되고 웹훅이 두 번 돈다.
    """
    assert extract_youtube_id(url) == "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=tooshort",
        "https://www.youtube.com/@somechannel",
        "https://vimeo.com/123456789",
    ],
)
def test_extract_youtube_id_rejects_other_urls(url: str) -> None:
    assert extract_youtube_id(url) is None


def test_video_create_derives_id() -> None:
    video = VideoCreate(youtube_url="https://youtu.be/dQw4w9WgXcQ?si=x")  # type: ignore[arg-type]
    assert video.youtube_id == "dQw4w9WgXcQ"


def test_video_create_rejects_non_youtube_url() -> None:
    with pytest.raises(ValidationError, match="YouTube 영상 URL"):
        VideoCreate(youtube_url="https://vimeo.com/123456789")  # type: ignore[arg-type]


def test_video_create_rejects_mismatched_id() -> None:
    """클라이언트가 보낸 ID 가 URL 과 다르면 조용히 덮어쓰지 않고 거부한다."""
    with pytest.raises(ValidationError, match="URL 과 다릅니다"):
        VideoCreate(
            youtube_url="https://youtu.be/dQw4w9WgXcQ",  # type: ignore[arg-type]
            youtube_id="aaaaaaaaaaa",
        )


def test_video_read_from_orm_like_object() -> None:
    class Row:
        id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        youtube_url = "https://youtu.be/dQw4w9WgXcQ"
        youtube_id = "dQw4w9WgXcQ"
        title = None
        channel = None
        duration_sec = None
        thumbnail_url = None
        status = VideoStatus.PENDING
        error_message = None
        processed_at = None
        created_at = datetime(2026, 10, 4, tzinfo=UTC)
        cost_usd = 0.42  # 노출되지 않아야 한다

    video = VideoRead.model_validate(Row())
    assert video.status is VideoStatus.PENDING
    assert "cost_usd" not in video.model_dump()


# ── 커서 ──────────────────────────────────────────────────────────────────────


def test_cursor_round_trip() -> None:
    raw = "2026-10-04T03:00:00+00:00|aaaaaaaa-0000-4000-8000-000000000001"
    assert decode_cursor(encode_cursor(raw)) == raw


def test_cursor_is_url_safe_and_unpadded() -> None:
    token = encode_cursor("a" * 10)
    assert "=" not in token
    assert "+" not in token and "/" not in token


def test_decode_cursor_returns_none_on_garbage() -> None:
    assert decode_cursor("!!!not-base64!!!") is None


def test_page_last_page_has_no_cursor() -> None:
    page: Page[PlaceRead] = Page(items=[], next_cursor=None)
    assert page.next_cursor is None
    assert page.model_dump()["items"] == []
