#!/bin/sh
# Credentials come from the environment so no password is baked into the image.
# PgBouncer accepts a plaintext userlist entry and performs SCRAM itself.
set -eu
: "${DB_USER:?DB_USER is required}" "${DB_PASSWORD:?DB_PASSWORD is required}"
printf '"%s" "%s"\n' "$DB_USER" "$DB_PASSWORD" > /etc/pgbouncer/userlist.txt
chmod 600 /etc/pgbouncer/userlist.txt
exec pgbouncer /etc/pgbouncer/pgbouncer.ini
