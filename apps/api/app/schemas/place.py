"""`places` DTO. Read / Create 분리 (apps/api/CLAUDE.md)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import SourceModality
from app.schemas.geo import Latitude, Longitude, point_to_lat_lng

__all__ = ["PlaceCreate", "PlaceRead"]


class PlaceBase(BaseModel):
    """Read 와 Create 가 공유하는 필드."""

    name: str = Field(min_length=1, max_length=200, examples=["을지다방"])
    category: str | None = Field(default=None, max_length=100, examples=["cafe"])
    address: str | None = Field(default=None, max_length=300)
    google_place_id: str | None = Field(default=None, max_length=64)
    lat: Latitude | None = None
    lng: Longitude | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    source_modality: SourceModality = SourceModality.VIDEO
    context_start_sec: int = Field(ge=0, examples=[132])
    context_end_sec: int = Field(ge=0, examples=[148])

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if self.context_end_sec < self.context_start_sec:
            raise ValueError("context_end_sec 는 context_start_sec 보다 앞설 수 없습니다")
        # 위도만 있고 경도가 없는 좌표는 지도에 꽂지도, 거리 계산에도 못 쓴다.
        # DB 는 POINT 하나라 애초에 반쪽을 저장할 수 없으므로 여기서 막는다.
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat 과 lng 는 둘 다 있거나 둘 다 없어야 합니다")
        return self


class PlaceCreate(PlaceBase):
    """파이프라인이 적재할 장소. `video_id` 는 경로·호출자가 정한다."""

    raw_extracted_text: str = Field(default="", max_length=2000)


class PlaceRead(PlaceBase):
    """지도 마커 하나.

    `geom` 은 노출하지 않는다 — 클라이언트에 필요한 건 `(lat, lng)` 뿐이고, WKB 를
    흘리면 좌표 순서 해석이 클라이언트마다 갈린다.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video_id: uuid.UUID
    raw_extracted_text: str
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _unpack_geom(cls, data: Any) -> Any:
        """ORM 객체의 `geom`(WKB) 을 `lat`/`lng` 로 펼친다.

        `from_attributes` 는 같은 이름의 속성만 찾으므로, Place ORM 인스턴스에는
        lat/lng 가 없다. dict 로 들어오는 경우(목 응답·테스트)는 그대로 둔다.
        """
        if isinstance(data, dict) or not hasattr(data, "geom"):
            return data
        coords = point_to_lat_lng(data.geom)
        values = {
            name: getattr(data, name)
            for name in (
                "id",
                "video_id",
                "name",
                "category",
                "address",
                "google_place_id",
                "confidence",
                "source_modality",
                "context_start_sec",
                "context_end_sec",
                "raw_extracted_text",
                "created_at",
            )
        }
        values["lat"], values["lng"] = coords if coords is not None else (None, None)
        return values
