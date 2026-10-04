"""모델 선언과 마이그레이션이 같은 스키마를 말하는지 (app/models, alembic/versions).

DB 없이 도는 테스트다. 노리는 실패는 두 가지다.

1. **모델만 고치고 마이그레이션을 빼먹는 것.** 루트 CLAUDE.md 가 금지한 바로 그 일인데,
   사람이 지키기로만 두면 반드시 한 번은 샌다. 두 쪽에서 DDL 을 뽑아 문장 단위로 비교한다.
2. **StrEnum 과 DB CHECK 제약의 드리프트.** 열거형에 값을 추가하고 CHECK 를 안 고치면
   INSERT 가 런타임에 터진다. 열거형을 진실 원천으로 삼아 제약문을 검사한다.
"""

from __future__ import annotations

import io
import re
from contextlib import redirect_stdout
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.models import Base, Place, SourceModality, Video, VideoStatus

API_DIR = Path(__file__).resolve().parents[2]


# ── DDL 비교 ──────────────────────────────────────────────────────────────────


def _split_top_level(body: str) -> list[str]:
    """괄호 depth 0 의 쉼표로만 쪼갠다 (`NUMERIC(8, 4)` 안쪽은 건드리지 않음)."""
    parts, depth, current = [], 0, ""
    for char in body:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
            continue
        current += char
    if current.strip():
        parts.append(current.strip())
    return parts


def _canonical(text: str) -> str:
    """CREATE TABLE 의 컬럼·제약 나열 순서를 정렬해 비교 가능한 형태로 만든다.

    모델 metadata 와 Alembic 은 같은 제약을 다른 순서로 뱉는다(예: FK 를 UNIQUE 앞에
    둘지 뒤에 둘지). 순서 차이로 테스트가 깨지면 아무도 안 보게 되므로, 의미가 같은
    것은 같다고 보고 **내용의 차이만** 잡는다.
    """
    match = re.match(r"(CREATE TABLE \w+) \((.*)\)$", text)
    if not match:
        return text
    head, body = match.groups()
    return f"{head} ({', '.join(sorted(_split_top_level(body)))})"


def _normalize(statements: list[str]) -> set[str]:
    """공백·주석·개행·나열 순서 차이를 지운 문장 집합."""
    cleaned = set()
    for raw in statements:
        text = re.sub(r"--[^\n]*", " ", raw)
        text = re.sub(r"\s+", " ", text).strip().rstrip(";").strip()
        if text:
            cleaned.add(_canonical(text))
    return cleaned


def _ddl_from_metadata() -> set[str]:
    collected: list[str] = []

    def collect(sql: sa.schema.ExecutableDDLElement, *_: object, **__: object) -> None:
        collected.append(str(sql.compile(dialect=engine.dialect)))

    engine = sa.create_mock_engine("postgresql://", collect)
    Base.metadata.create_all(engine, checkfirst=False)
    return _normalize(collected)


def _ddl_from_migration() -> set[str]:
    config = Config()
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        command.upgrade(config, "head", sql=True)
    statements = buffer.getvalue().split(";")
    # alembic 자신의 버전 테이블과 트랜잭션 제어는 비교 대상이 아니다.
    return {
        s
        for s in _normalize(statements)
        if "alembic_version" not in s and s not in {"COMMIT", "BEGIN"}
    }


def test_migration_matches_model_metadata() -> None:
    """마이그레이션이 만드는 테이블·인덱스·제약이 모델 선언과 일치한다."""
    from_models = _ddl_from_metadata()
    from_migration = _ddl_from_migration()
    # PostGIS extension 은 모델 쪽에 대응물이 없다 (마이그레이션에만 있는 선행 조건).
    from_migration = {s for s in from_migration if "CREATE EXTENSION" not in s}

    only_in_models = from_models - from_migration
    only_in_migration = from_migration - from_models
    assert not only_in_models, f"마이그레이션에 빠진 DDL: {sorted(only_in_models)}"
    assert not only_in_migration, f"모델에 없는 DDL: {sorted(only_in_migration)}"


def test_migration_creates_postgis_extension() -> None:
    assert any("CREATE EXTENSION IF NOT EXISTS postgis" in s for s in _ddl_from_migration())


# ── 열거형 ↔ CHECK 제약 ───────────────────────────────────────────────────────


def _check_clause(table: sa.Table, name: str) -> str:
    for constraint in table.constraints:
        if constraint.name == name:
            assert isinstance(constraint, sa.CheckConstraint)
            return str(constraint.sqltext)
    pytest.fail(f"{table.name}: {name} 제약이 없습니다")


@pytest.mark.parametrize(
    ("table_name", "constraint", "enum_type"),
    [
        ("videos", "videos_status_check", VideoStatus),
        ("places", "places_source_modality_check", SourceModality),
    ],
)
def test_check_constraint_covers_every_enum_value(
    table_name: str, constraint: str, enum_type: type[VideoStatus] | type[SourceModality]
) -> None:
    clause = _check_clause(Base.metadata.tables[table_name], constraint)
    quoted = set(re.findall(r"'([^']+)'", clause))
    assert quoted == {member.value for member in enum_type}


def test_video_defaults_to_pending() -> None:
    assert Video.__table__.c.status.server_default is not None
    assert str(Video.__table__.c.status.server_default.arg) == VideoStatus.PENDING


# ── 공간 컬럼과 인덱스 ────────────────────────────────────────────────────────


def test_geom_is_geography_4326() -> None:
    geom = Place.__table__.c.geom
    assert geom.type.geometry_type == "POINT"
    assert geom.type.srid == 4326
    # geometry 가 아니라 geography — 미터 단위 반경 질의를 투영 없이 쓰기 위해.
    assert geom.type.__class__.__name__ == "Geography"
    assert geom.nullable, "지오코딩 실패 장소는 좌표 없이 남는다"


def test_exactly_one_gist_index_on_geom() -> None:
    """GeoAlchemy2 의 자동 인덱스와 우리가 선언한 인덱스가 겹치지 않는다."""
    geom_indexes = [
        index
        for index in Place.__table__.indexes
        if any(col.name == "geom" for col in index.columns)
    ]
    assert len(geom_indexes) == 1, [i.name for i in geom_indexes]
    index = geom_indexes[0]
    assert index.name == "places_geom_idx"
    assert index.dialect_options["postgresql"]["using"] == "gist"


# ── 인덱스·제약 존재 확인 ─────────────────────────────────────────────────────


def test_indexes_present() -> None:
    assert {i.name for i in Video.__table__.indexes} == {
        "videos_user_id_idx",
        "videos_youtube_id_idx",
    }
    assert {i.name for i in Place.__table__.indexes} == {
        "places_geom_idx",
        "places_video_id_idx",
        "places_google_place_id_idx",
    }


def test_place_video_fk_cascades_and_is_named() -> None:
    fk = next(iter(Place.__table__.c.video_id.foreign_keys))
    assert fk.column is Video.__table__.c.id
    assert fk.ondelete == "CASCADE"
    assert fk.constraint is not None
    assert fk.constraint.name == "places_video_id_fkey"


def test_videos_user_id_has_no_db_level_fk() -> None:
    """auth.users 는 Supabase 소유 — Alembic 이 FK 를 걸면 로컬 Postgres 에서 깨진다."""
    assert not Video.__table__.c.user_id.foreign_keys


def test_same_video_cannot_be_submitted_twice_by_one_user() -> None:
    names = {c.name for c in Video.__table__.constraints}
    assert "videos_user_youtube_uniq" in names


def test_timestamps_are_timezone_aware() -> None:
    for table in (Video.__table__, Place.__table__):
        for column in ("created_at", "updated_at"):
            assert table.c[column].type.timezone is True, f"{table.name}.{column}"
