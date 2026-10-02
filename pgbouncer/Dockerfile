# PgBouncer from Alpine's package, configured in-repo rather than via a
# third-party image's environment-variable conventions.
FROM alpine:3.20
RUN apk add --no-cache pgbouncer \
 && (id pgbouncer >/dev/null 2>&1 || adduser -D -H -s /sbin/nologin pgbouncer) \
 && mkdir -p /etc/pgbouncer \
 && chown -R pgbouncer /etc/pgbouncer
COPY pgbouncer.ini /etc/pgbouncer/pgbouncer.ini
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
USER pgbouncer
EXPOSE 6432
HEALTHCHECK --interval=5s --timeout=3s --retries=10 CMD nc -z 127.0.0.1 6432 || exit 1
ENTRYPOINT ["/entrypoint.sh"]
