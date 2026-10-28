"""least-privilege role for mcp-db

Revision ID: 003
Revises: 002
Create Date: 2026-10-28

mcp-db ran the model's SQL as `hive`, the superuser that owns every table. Its
READ ONLY transaction stopped writes but not superuser-only reads:
`SELECT pg_read_file('/etc/hostname')` returned the database server's file.

hive_reader can SELECT the application tables and nothing else, so functions
such as pg_read_file and pg_ls_dir fail with "permission denied" regardless of
what the keyword filter in mcp-db lets through.

The password comes from MCP_DB_PASSWORD, which PgBouncer's userlist must match
(docker-compose passes the same variable to both). Changing it later means
re-running `ALTER ROLE hive_reader PASSWORD ...`; this migration runs once.
"""
import os
from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE = "hive_reader"
# Listed explicitly rather than granted by default privileges: a table added
# later (with credentials or secrets in it, say) should not become readable by
# the model's SQL without someone deciding it should.
TABLES = ("agents", "runs", "steps", "tool_calls", "documents", "embeddings")


def upgrade() -> None:
    op.execute(f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{ROLE}') THEN
                CREATE ROLE {ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
            END IF;
        END $$
    """)
    # Utility statements take no bind parameters, so the literal is escaped by
    # hand, and sent with exec_driver_sql so a ':' in it is not read as a bind.
    password = os.getenv("MCP_DB_PASSWORD", "hivereader").replace("'", "''")
    op.get_bind().exec_driver_sql(f"ALTER ROLE {ROLE} PASSWORD '{password}'")

    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE}")
    op.execute(f"GRANT SELECT ON {', '.join(TABLES)} TO {ROLE}")
    # Session defaults for any client that connects as this role, in addition
    # to the per-transaction settings mcp-db applies itself.
    op.execute(f"ALTER ROLE {ROLE} SET default_transaction_read_only = on")
    op.execute(f"ALTER ROLE {ROLE} SET statement_timeout = '5s'")


def downgrade() -> None:
    op.execute(f"REVOKE SELECT ON {', '.join(TABLES)} FROM {ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {ROLE}")
    op.execute(f"DROP ROLE IF EXISTS {ROLE}")
