import os
from logging.config import fileConfig

from alembic import context

from app.core.config import Settings
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import make_engine

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

settings = Settings()
if os.environ.get("MI_MIGRATION_DATABASE_URL"):
    settings = Settings(database_url=os.environ["MI_MIGRATION_DATABASE_URL"])
if context.is_offline_mode():
    context.configure(
        url=settings.database_url.get_secret_value(),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(settings)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
