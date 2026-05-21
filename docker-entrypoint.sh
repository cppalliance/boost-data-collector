#!/bin/sh
set -e
# Dev compose sets ALLOW_ROOT_ENTRYPOINT=1 so root can chown bind-mounted volumes.
if [ "$(id -u)" = 0 ] && [ "${ALLOW_ROOT_ENTRYPOINT:-0}" = 1 ]; then
  chown -R appuser:appuser /app/workspace /app/logs 2>/dev/null || true
  [ -d /app/celerybeat ] && chown -R appuser:appuser /app/celerybeat 2>/dev/null || true
  exec gosu appuser "$@"
fi
exec "$@"
