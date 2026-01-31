#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Run migrations (creates quaero schema + tables, same pattern as Rostra)
alembic upgrade head
