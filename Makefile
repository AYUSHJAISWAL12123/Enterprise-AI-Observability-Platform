.PHONY: build up down simulate test

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

simulate:
	uv run scripts/simulate_traffic.py

test:
	uv run pytest services/*/tests -v
