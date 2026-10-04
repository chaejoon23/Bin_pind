"""커서 기반 페이지네이션 (루트 CLAUDE.md: offset 금지).

offset 을 쓰면 두 가지가 깨진다. 페이지를 넘기는 사이에 행이 추가되면 항목이
건너뛰어지거나 중복되고, 뒤쪽 페이지로 갈수록 Postgres 가 버린 행까지 세느라
느려진다. 커서는 "이 값 다음부터"라 둘 다 생기지 않는다.

커서 값은 **불투명한 문자열**로 다룬다. 지금은 정렬 키를 base64 로 감싼 것이지만,
클라이언트가 그 안을 들여다보고 의존하기 시작하면 정렬 기준을 못 바꾼다.
"""

from __future__ import annotations

import base64
import binascii
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "Cursor",
    "Limit",
    "Page",
    "decode_cursor",
    "encode_cursor",
]

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

Limit = Annotated[int, Field(ge=1, le=MAX_LIMIT)]
Cursor = Annotated[str | None, Field(description="이전 응답의 next_cursor. 첫 페이지는 생략.")]

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """한 페이지 분량의 결과.

    `next_cursor` 가 None 이면 마지막 페이지다. 총 개수(`total`)는 넣지 않는다 —
    커서 페이지네이션에서 전체를 세려면 매 요청마다 COUNT 를 돌려야 하고, 지도
    화면에서 총 개수를 쓸 일이 없다.
    """

    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    next_cursor: str | None = None


def encode_cursor(value: str) -> str:
    """정렬 키를 불투명 커서로 감싼다 (패딩 없는 urlsafe base64)."""
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> str | None:
    """커서를 정렬 키로 되돌린다. 형식이 깨졌으면 None.

    호출하는 쪽이 400 으로 바꿀지 첫 페이지로 떨어뜨릴지 정한다 — 여기서 예외를
    던지면 손으로 URL 을 고친 사용자가 500 을 보게 된다.
    """
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
