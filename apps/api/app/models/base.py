import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    # sort_order: 믹스인 컬럼은 기본적으로 본문 컬럼 뒤에 붙는다. 양수를 주어 항상
    # 테이블 맨 끝에 오게 하면 생성되는 DDL 과 `\d videos` 출력이 읽기 쉬워진다.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, sort_order=100
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        sort_order=101,
    )


class UUIDMixin:
    # 음수 sort_order → PK 가 항상 첫 컬럼.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, sort_order=-100)
