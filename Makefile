DEV_COMPOSE = docker-compose.dev.yml
PROD_COMPOSE = docker-compose.yml

#
# development commands
#

dev-migrate: 
	docker compose -f $(DEV_COMPOSE) exec web python manage.py migrate

dev-makemigrations: 
	docker compose -f $(DEV_COMPOSE) exec web python manage.py makemigrations

dev-superuser: 
	docker compose -f $(DEV_COMPOSE) exec web python manage.py createsuperuser

dev-cachetable:
	docker compose -f $(DEV_COMPOSE) exec web python manage.py createcachetable

dev-collectstatic:
	docker compose -f $(DEV_COMPOSE) exec web python manage.py collectstatic --noinput

dev-shell-web: 
	docker compose -f $(DEV_COMPOSE) exec web bash

dev-shell-admin: 
	docker compose -f $(DEV_COMPOSE) exec admin bash

dev-shell-api: 
	docker compose -f $(DEV_COMPOSE) exec api bash

dev-build: 
	docker compose -f $(DEV_COMPOSE) build

dev-up: 
	docker compose -f $(DEV_COMPOSE) up -d --no-deps --force-recreate

dev-down: 
	docker compose -f $(DEV_COMPOSE) down

dev-restart:
	docker compose -f $(DEV_COMPOSE) restart

dev-logs:
	docker compose -f $(DEV_COMPOSE) logs -f

#
# production commands
#

migrate: 
	@echo "Attention: Migrate will be on PRODUCTION database"
	docker compose -f $(PROD_COMPOSE) exec web python manage.py migrate

superuser: 
	@echo "Creating superuser on production server..."
	docker compose -f $(PROD_COMPOSE) exec web python manage.py createsuperuser

cachetable:
	docker compose -f $(PROD_COMPOSE) exec web python manage.py createcachetable

collectstatic:
	docker compose -f $(PROD_COMPOSE) exec web python manage.py collectstatic --noinput

shell-web: 
	@echo "Entering into web-shell on production server..."
	docker compose -f $(PROD_COMPOSE) exec web bash

shell-api: 
	@echo "Entering into api-shell on production server..."
	docker compose -f $(PROD_COMPOSE) exec api bash

build: 
	docker-compose -f $(PROD_COMPOSE) build

up: 
	docker-compose -f $(PROD_COMPOSE) up -d --no-deps --force-recreate

down:
	@echo "Attention: now you will stop your PRODUCTION server"
	docker-compose -f $(PROD_COMPOSE) down

restart: 
	docker-compose -f $(PROD_COMPOSE) restart

logs:
	docker-compose -f $(PROD_COMPOSE) logs -f