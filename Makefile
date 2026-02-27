.PHONY: setup-db migrate deploy deploy-sync

setup-db:
	./scripts/start_db.sh

migrate:
	uv run python scripts/migrate.py
	uv run python scripts/setup_store_table.py

deploy:
	./deploy.sh $(ARGS)

deploy-sync:
	./deploy.sh sync
