#!/bin/sh
# Credentials come from the environment so no password is baked into the image.
# PgBouncer accepts a plaintext userlist entry and performs SCRAM itself.
set -eu
: "${DB_USER:?DB_USER is required}" "${DB_PASSWORD:?DB_PASSWORD is required}"
{
  printf '"%s" "%s"\n' "$DB_USER" "$DB_PASSWORD"
  # Optional second login: the least-privilege role mcp-db runs the model's SQL as.
  if [ -n "${READER_USER:-}" ]; then
    printf '"%s" "%s"\n' "$READER_USER" "${READER_PASSWORD:?READER_PASSWORD is required with READER_USER}"
  fi
} > /etc/pgbouncer/userlist.txt
chmod 600 /etc/pgbouncer/userlist.txt
exec pgbouncer /etc/pgbouncer/pgbouncer.ini
