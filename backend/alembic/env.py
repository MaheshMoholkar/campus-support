from alembic import context
from sqlalchemy import Connection, create_engine, pool

from app.core.config import settings
from app.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


# Tests pass their own connection (schema `test`); the CLI connects from settings.
supplied = config.attributes.get("connection")
if supplied is not None:
    run_migrations(supplied)
else:
    engine = create_engine(settings.sqlalchemy_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        run_migrations(connection)
