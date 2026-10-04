"""좌표를 API 표면과 DB 사이에서 옮기는 어댑터.

DB 는 `geography(POINT, 4326)` 를, API 는 `lat`/`lng` 두 개의 float 를 쓴다
(루트 CLAUDE.md: "좌표는 API 표면에 lat/lng 로 노출"). Leaflet·Google Maps 둘 다
`(lat, lng)` 순서로 받으므로 클라이언트에 WKB/WKT 를 흘리지 않는다.

**순서가 뒤집히기 쉬운 지점이 여기다.** PostGIS 의 POINT 는 `(x, y) = (경도, 위도)`
이고 지도 API 는 `(위도, 경도)` 다. 서울(위도 37.5, 경도 127.0)처럼 두 값이 모두
유효 범위에 있으면 뒤집혀도 예외가 나지 않고 핀만 엉뚱한 곳(중국 동부)에 꽂힌다.
그래서 변환을 이 한 모듈에만 두고 왕복 테스트로 고정한다.
"""

from __future__ import annotations

from typing import Annotated

from geoalchemy2.elements import WKBElement, WKTElement
from geoalchemy2.shape import to_shape
from pydantic import Field

__all__ = ["SRID", "Latitude", "Longitude", "point_to_lat_lng", "lat_lng_to_point"]

SRID = 4326
"""WGS84. 레포 전체에서 고정 (supabase/CLAUDE.md)."""

Latitude = Annotated[float, Field(ge=-90, le=90, examples=[37.5665])]
Longitude = Annotated[float, Field(ge=-180, le=180, examples=[126.9780])]


def point_to_lat_lng(point: WKBElement | WKTElement | None) -> tuple[float, float] | None:
    """DB 의 POINT → `(lat, lng)`. 좌표가 없으면 None.

    지오코딩에 실패한 장소는 `geom` 이 NULL 이다 (이름과 영상 구간만 남는다).
    """
    if point is None:
        return None
    shape = to_shape(point)
    # shapely 는 PostGIS 와 같은 (x, y) = (경도, 위도) 순서를 쓴다.
    return (shape.y, shape.x)


def lat_lng_to_point(lat: float | None, lng: float | None) -> WKTElement | None:
    """`(lat, lng)` → DB 에 넣을 POINT. 둘 중 하나라도 없으면 None.

    WKT 로 만들어 넘기면 SQLAlchemy 가 `ST_GeogFromText` 로 감싼다 — 쿼리마다
    `ST_SetSRID(ST_MakePoint(...))` 를 손으로 조립하지 않아도 된다.
    """
    if lat is None or lng is None:
        return None
    return WKTElement(f"POINT({lng} {lat})", srid=SRID)
