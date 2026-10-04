"""SQLAlchemy 모델.

Alembic 의 `target_metadata` 와 relationship 문자열 해소가 둘 다 "모든 모델이 한 번은
임포트돼 있음"을 전제한다. 그래서 여기서 전부 재노출한다 — 새 모델을 만들면 반드시
이 목록에 추가해야 autogenerate 가 테이블을 인식한다.
"""

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import SourceModality, VideoStatus
from app.models.place import Place
from app.models.video import Video

__all__ = [
    "Base",
    "Place",
    "SourceModality",
    "TimestampMixin",
    "UUIDMixin",
    "Video",
    "VideoStatus",
]
