#!/bin/sh
# Bring the database schema up to date, then start the API.
set -e
alembic upgrade head
exec "$@"
