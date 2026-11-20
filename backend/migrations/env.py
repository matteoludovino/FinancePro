from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection

import financepro.models  # noqa: F401  # registers every table on Base.metadata
from financepro.db import Base, get_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


# Tests pass their own connection through `config.attributes`, so migrations run on the test database.
connection = config.attributes.get("connection")
if connection is not None:
    run_migrations(connection)
else:
    with get_engine().connect() as conn:
        run_migrations(conn)
