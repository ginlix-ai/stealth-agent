.PHONY: setup-db migrate

setup-db:
	./scripts/start_db.sh

migrate:
	uv run python scripts/migrate.py
