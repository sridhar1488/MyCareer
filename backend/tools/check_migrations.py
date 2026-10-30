"""Rehearse migrations only on an explicitly supplied, empty disposable database."""

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url


def main():
    url = os.environ["MI_MIGRATION_REHEARSAL_URL"]
    name = make_url(url).database or ""
    if not name.endswith("_migration_test"):
        raise RuntimeError("Use a newly created disposable database ending _migration_test")
    engine = create_engine(url, hide_parameters=True)
    try:
        if inspect(engine).get_table_names():
            raise RuntimeError(
                "Migration rehearsal refuses any non-empty schema. Create a new disposable database."
            )
    finally:
        engine.dispose()
    previous = os.environ.get("MI_MIGRATION_DATABASE_URL")
    os.environ["MI_MIGRATION_DATABASE_URL"] = url
    try:
        config = Config("alembic.ini")
        command.upgrade(config, "head")
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        command.check(config)
    finally:
        if previous is None:
            os.environ.pop("MI_MIGRATION_DATABASE_URL", None)
        else:
            os.environ["MI_MIGRATION_DATABASE_URL"] = previous
    print("MySQL migration upgrade -> downgrade -> upgrade passed, with no metadata drift.")


if __name__ == "__main__":
    main()
