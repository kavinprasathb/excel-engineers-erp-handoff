# Excel Engineers ERP — one entry point for every command.
# Local dev uses a NATIVE Postgres (no Docker on the dev machine); the Docker
# files in this repo are only ever run on the VPS.

.PHONY: help install tunnel dev-api dev-web migrate revision test test-api test-web lint fmt types check shots

help:
	@echo "install   install backend + frontend dependencies"
	@echo "tunnel    open the SSH tunnel to the VPS Postgres (run this first)"
	@echo "dev-api   run the API   (needs the tunnel)"
	@echo "dev-web   run the web dev server"
	@echo "migrate   alembic upgrade head"
	@echo "test      backend + frontend tests"
	@echo "check     everything CI runs"

install:
	cd backend && uv sync
	cd frontend && npm install

tunnel:
	bash scripts/db-tunnel.sh

dev-api:
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-web:
	cd frontend && npm run dev

migrate:
	cd backend && uv run alembic upgrade head

revision:
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

test-api:
	cd backend && uv run pytest -n 6

test-web:
	cd frontend && npm run test -- --run

test: test-api test-web

# Look at the app. Automated gates cannot see a stylesheet that silently
# failed to load; this catches what they cannot.
shots:
	cd frontend && node scripts/screenshot.mjs ../screenshots

lint:
	cd backend && uv run ruff check .
	cd frontend && npm run lint

fmt:
	cd backend && uv run ruff format .

types:
	cd backend && uv run mypy app
# `tsc -b`, not `tsc --noEmit`: the root tsconfig is a solution file
# (`files: []` plus project references), so `--noEmit` type-checks nothing
# and exits 0. It sat in this Makefile and in CI for the whole project,
# reporting success while checking not one line.
	cd frontend && npx tsc -b

check: lint types test
