#!/bin/sh
# Postgres lives inside the container: data resets on restart and each visitor's demo copy is rebuilt on demand.
set -e
PGBIN=$(ls -d /usr/lib/postgresql/*/bin | head -1)
"$PGBIN/initdb" -D "$PGDATA" -U app --auth=trust >/dev/null
"$PGBIN/pg_ctl" -D "$PGDATA" -o "-k /tmp -c listen_addresses=127.0.0.1" -l /tmp/pg.log -w start
"$PGBIN/createdb" -h 127.0.0.1 -U app invocarbon
export DATABASE_URL="postgresql+psycopg://app@127.0.0.1:5432/invocarbon"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-7860}"
