"""목 라우터의 응답 모양 (app/routers).

본문은 더미 데이터지만, **응답 스키마와 OpenAPI 는 진짜다.** web·extension 이
`packages/shared-types/src/api.ts` 로 받아 쓰는 계약이라, 모양이 흔들리면 여기서
먼저 깨져야 한다. DB 없이 돈다.
"""

from __future__ import annotations

import uuid

import pytest
from app.main import app
from fastapi.testclient import TestClient

VIDEO_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


# ── /api/v1/places ────────────────────────────────────────────────────────────


def test_places_returns_page_shape(client: TestClient) -> None:
    body = client.get("/api/v1/places").json()
    assert set(body) == {"items", "next_cursor"}
    assert body["next_cursor"] is None
    assert len(body["items"]) == 3


def test_place_item_exposes_lat_lng_not_geom(client: TestClient) -> None:
    item = client.get("/api/v1/places").json()["items"][0]
    assert "geom" not in item
    assert item["lat"] == 37.5665
    assert item["lng"] == 126.9910


def test_mock_includes_a_place_without_coordinates(client: TestClient) -> None:
    """지오코딩 실패 사례가 섞여 있어야 지도 쪽이 null 을 처음부터 다룬다."""
    items = client.get("/api/v1/places").json()["items"]
    no_coords = [i for i in items if i["lat"] is None]
    assert len(no_coords) == 1
    assert no_coords[0]["lng"] is None
    assert no_coords[0]["name"]
    assert no_coords[0]["context_end_sec"] >= no_coords[0]["context_start_sec"]


def test_places_video_id_filter(client: TestClient) -> None:
    assert len(client.get("/api/v1/places", params={"video_id": VIDEO_ID}).json()["items"]) == 3
    other = str(uuid.UUID("22222222-2222-4222-8222-222222222222"))
    assert client.get("/api/v1/places", params={"video_id": other}).json()["items"] == []


def test_places_limit(client: TestClient) -> None:
    assert len(client.get("/api/v1/places", params={"limit": 2}).json()["items"]) == 2


@pytest.mark.parametrize("limit", [0, -1, 201])
def test_places_rejects_bad_limit(client: TestClient, limit: int) -> None:
    assert client.get("/api/v1/places", params={"limit": limit}).status_code == 422


def test_places_bad_cursor_is_400_not_500(client: TestClient) -> None:
    """URL 을 손으로 고친 사용자가 500 을 보지 않게."""
    response = client.get("/api/v1/places", params={"cursor": "!!!not-base64!!!"})
    assert response.status_code == 400


# ── /api/v1/videos ────────────────────────────────────────────────────────────


def test_resolve_returns_youtube_id(client: TestClient) -> None:
    response = client.post(
        "/api/v1/videos/resolve",
        json={"youtube_url": "https://youtu.be/dQw4w9WgXcQ?si=abc"},
    )
    assert response.status_code == 200
    assert response.json()["youtube_id"] == "dQw4w9WgXcQ"


def test_resolve_rejects_non_youtube_url(client: TestClient) -> None:
    response = client.post(
        "/api/v1/videos/resolve", json={"youtube_url": "https://vimeo.com/123456789"}
    )
    assert response.status_code == 422


def test_get_video_returns_status(client: TestClient) -> None:
    body = client.get(f"/api/v1/videos/{VIDEO_ID}").json()
    assert body["id"] == VIDEO_ID
    assert body["status"] == "completed"
    assert "cost_usd" not in body


# ── OpenAPI ───────────────────────────────────────────────────────────────────


def test_openapi_exposes_the_schemas_the_frontend_needs() -> None:
    """`make gen-types` 가 TS 로 옮길 스키마가 스펙에 다 들어 있다."""
    schemas = app.openapi()["components"]["schemas"]
    for name in ("PlaceRead", "VideoRead", "VideoCreate", "VideoStatus", "SourceModality"):
        assert name in schemas, name


def test_every_route_is_under_api_v1_and_tagged() -> None:
    for path, operations in app.openapi()["paths"].items():
        if path == "/health":
            continue
        assert path.startswith("/api/v1/"), path
        for method, operation in operations.items():
            assert operation.get("tags"), f"{method.upper()} {path} 에 tags 가 없습니다"
