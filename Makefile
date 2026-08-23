DEV_COMPOSE = docker-compose.dev.yml
PROD_COMPOSE = docker-compose.selfhost.yml

#
# development commands
#

dev-migrate:
	@echo "Applying migrations across all services (web, admin, api)..."
	docker compose -f $(DEV_COMPOSE) exec web python manage.py migrate
	docker compose -f $(DEV_COMPOSE) exec admin python manage.py migrate
	docker compose -f $(DEV_COMPOSE) exec api python manage.py migrate

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

dev-test:
	docker compose -f $(DEV_COMPOSE) exec web python manage.py test

#
# development analytics (clickhouse, optional profile)
#

dev-analytics-up:
	docker compose -f $(DEV_COMPOSE) --profile analytics up -d clickhouse

dev-analytics-down:
	docker compose -f $(DEV_COMPOSE) --profile analytics stop clickhouse

dev-analytics-logs:
	docker compose -f $(DEV_COMPOSE) --profile analytics logs -f clickhouse

dev-analytics-migrate:
	docker compose -f $(DEV_COMPOSE) exec web python manage.py analytics_migrate

dev-analytics-ping:
	docker compose -f $(DEV_COMPOSE) exec web python manage.py analytics_ping

#
# production commands
#

migrate:
	@echo "Attention: Migrate will be on PRODUCTION database"
	docker compose -f $(PROD_COMPOSE) exec lunastore python manage.py migrate

superuser:
	@echo "Creating superuser on production server..."
	docker compose -f $(PROD_COMPOSE) exec lunastore python manage.py createsuperuser

cachetable:
	docker compose -f $(PROD_COMPOSE) exec lunastore python manage.py createcachetable

collectstatic:
	docker compose -f $(PROD_COMPOSE) exec lunastore python manage.py collectstatic --noinput

shell:
	@echo "Entering into shell on production server..."
	docker compose -f $(PROD_COMPOSE) exec lunastore bash

build:
	docker compose -f $(PROD_COMPOSE) build

up:
	docker compose -f $(PROD_COMPOSE) up -d --no-deps --force-recreate

down:
	@echo "Attention: now you will stop your PRODUCTION server"
	docker compose -f $(PROD_COMPOSE) down

restart:
	docker compose -f $(PROD_COMPOSE) restart

logs:
	docker compose -f $(PROD_COMPOSE) logs -f

PYTHON ?= python

i18n-make:
	$(PYTHON) manage.py makemessages -a

i18n-compile:
	$(PYTHON) manage.py compilemessages

test:
	docker compose -f $(PROD_COMPOSE) exec lunastore python manage.py test

#
# production analytics (clickhouse, optional profile)
#

analytics-up:
	docker compose -f $(PROD_COMPOSE) --profile analytics up -d clickhouse

analytics-down:
	@echo "Attention: now you will stop PRODUCTION clickhouse"
	docker compose -f $(PROD_COMPOSE) --profile analytics stop clickhouse

analytics-logs:
	docker compose -f $(PROD_COMPOSE) --profile analytics logs -f clickhouse

analytics-migrate:
	@echo "Attention: analytics migrate will run on PRODUCTION clickhouse"
	docker compose -f $(PROD_COMPOSE) exec lunastore python manage.py analytics_migrate

analytics-ping:
	docker compose -f $(PROD_COMPOSE) exec lunastore python manage.py analytics_ping

tolgee-push:
	tolgee push

tolgee-pull:
	tolgee pull

i18n-sync: i18n-make tolgee-push tolgee-pull i18n-compile

#
# javascript (babel) commands
#

js-install:
	npm install

js-build:
	npm run babel:build

js-watch:
	npm run babel:watch
