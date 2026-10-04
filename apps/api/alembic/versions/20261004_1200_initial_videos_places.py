"""initial schema: postgis + videos + places

Phase 1-1. 첫 마이그레이션이라 `autogenerate` 로 뽑지 않고 손으로 썼다 — PostGIS
extension 생성과 `geography` 컬럼은 autogenerate 가 제대로 다루지 못하고(GeoAlchemy2
가 자체 인덱스를 끼워 넣는다), 되돌리기까지 검수해야 하는 부분이기 때문이다.
모델 metadata 가 만드는 DDL 과 이 파일이 만드는 DDL 이 같은지는
`tests/unit/test_models_schema.py` 가 비교한다.

Revision ID: 20261004_1200
Revises:
Create Date: 2026-10-04
"""

from __future__ import annotations

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "20261004_1200"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostGIS. Supabase 프로젝트에는 보통 이미 깔려 있지만, 로컬 Postgres 와
    # 새 프로젝트에서도 같은 마이그레이션 하나로 끝나야 한다.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "videos",
        sa.Column("id", sa.UUID(), nullable=False),
        # auth.users.id 를 가리키지만 FK 는 걸지 않는다 (app/models/video.py 주석 참고).
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("youtube_url", sa.Text(), nullable=False),
        sa.Column("youtube_id", sa.String(length=16), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "youtube_id", name="videos_user_youtube_uniq"),
        sa.CheckConstraint(
            "status IN ('pending', 'downloading', 'analyzing', 'resolving', 'completed', 'failed')",
            name="videos_status_check",
        ),
        sa.CheckConstraint(
            "duration_sec IS NULL OR duration_sec > 0", name="videos_duration_check"
        ),
        sa.CheckConstraint("cost_usd IS NULL OR cost_usd >= 0", name="videos_cost_check"),
    )
    op.create_index("videos_user_id_idx", "videos", ["user_id"])
    op.create_index("videos_youtube_id_idx", "videos", ["youtube_id"])

    op.create_table(
        "places",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("video_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("google_place_id", sa.String(length=64), nullable=True),
        sa.Column(
            "geom",
            geoalchemy2.types.Geography(
                geometry_type="POINT", srid=4326, spatial_index=False, from_text="ST_GeogFromText"
            ),
            nullable=True,
        ),
        sa.Column("source_modality", sa.String(length=8), server_default="video", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("raw_extracted_text", sa.Text(), server_default="", nullable=False),
        sa.Column("context_start_sec", sa.Integer(), nullable=False),
        sa.Column("context_end_sec", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["video_id"], ["videos.id"], name="places_video_id_fkey", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("video_id", "google_place_id", name="places_video_google_uniq"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="places_confidence_check"),
        sa.CheckConstraint("context_start_sec >= 0", name="places_context_start_check"),
        sa.CheckConstraint(
            "context_end_sec >= context_start_sec", name="places_context_order_check"
        ),
        sa.CheckConstraint(
            "source_modality IN ('audio', 'vision', 'text', 'video')",
            name="places_source_modality_check",
        ),
    )
    # 반경 검색용 GIST. 이름을 고정해 supabase/CLAUDE.md 의 규약과 맞춘다.
    op.create_index("places_geom_idx", "places", ["geom"], postgresql_using="gist")
    op.create_index("places_video_id_idx", "places", ["video_id"])
    op.create_index("places_google_place_id_idx", "places", ["google_place_id"])


def downgrade() -> None:
    op.drop_index("places_google_place_id_idx", table_name="places")
    op.drop_index("places_video_id_idx", table_name="places")
    op.drop_index("places_geom_idx", table_name="places", postgresql_using="gist")
    op.drop_table("places")
    op.drop_index("videos_youtube_id_idx", table_name="videos")
    op.drop_index("videos_user_id_idx", table_name="videos")
    op.drop_table("videos")
    # extension 은 지우지 않는다 — 다른 테이블이 쓰고 있을 수 있고, Supabase 프로젝트
    # 에서는 우리가 만든 것이 아닐 수도 있다.
