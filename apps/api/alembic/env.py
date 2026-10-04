from logging.config import fileConfig

from alembic import context

# base 가 아니라 패키지를 임포트한다 — app/models/__init__.py 가 모든 모델을 로드하므로
# Base.metadata 에 테이블이 전부 등록된다. base 만 임포트하면 빈 metadata 가 된다.
from app.models import Base
from app.settings import settings
from sqlalchemy import create_engine, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# DATABASE_URL을 ConfigParser를 거치지 않고 직접 사용.
# set_main_option은 ConfigParser 내부에서 % 문자를 interpolation으로 파싱하므로
# 비밀번호에 % 가 포함된 경우 ValueError가 발생함.
_db_url = settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_db_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
