"""Pydantic DTO. API 표면의 모양은 전부 여기서 정의한다.

`packages/shared-types/src/api.ts` 는 이 스키마들이 만든 OpenAPI 에서 자동 생성된다
(`make gen-types`). TypeScript 인터페이스를 손으로 쓰는 것은 금지 — 여기만 고친다.
"""

from app.schemas.geo import SRID, Latitude, Longitude, lat_lng_to_point, point_to_lat_lng
from app.schemas.pagination import Cursor, Limit, Page, decode_cursor, encode_cursor
from app.schemas.place import PlaceCreate, PlaceRead
from app.schemas.video import VideoCreate, VideoRead, extract_youtube_id

__all__ = [
    "SRID",
    "Cursor",
    "Latitude",
    "Limit",
    "Longitude",
    "Page",
    "PlaceCreate",
    "PlaceRead",
    "VideoCreate",
    "VideoRead",
    "decode_cursor",
    "encode_cursor",
    "extract_youtube_id",
    "lat_lng_to_point",
    "point_to_lat_lng",
]
