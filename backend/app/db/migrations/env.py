from alembic import context
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.models import Prompt, Agent
from app.db.base_class import Base

# Alembic config
config = context.config
fileConfig(config.config_file_name)

# Override with sync connection string for simplicity
sync_url = settings.SQLALCHEMY_DATABASE_URI.replace("asyncpg", "psycopg2")
config.set_main_option("sqlalchemy.url", sync_url)

# Target metadata (used by autogenerate)
target_metadata = Base.metadata

def run_migrations_offline():
    """Offline migrations (without DB connection)"""
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Online migrations (with DB connection)"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

# Entrypoint - make sure we only run once
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()