#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # no color

info() { echo -e "${BLUE}[info]${NC} $1"; }
success() { echo -e "${GREEN}[success]${NC} $1"; }
warn() { echo -e "${YELLOW}[warning]${NC} $1"; }
error() { echo -e "${RED}[error]${NC} $1"; }

run_cmd() {
    "$@"
    local status=$?
    if [ $status -ne 0 ]; then
        error "command '$1' was exited with error :< (code: $status). So, at first, check if all is ok with your configuration & other things."
        exit $status
    fi
}

# header
show_header() {
    echo -e "${CYAN}"
    echo "==================================================="
    echo "LunaStore Installer"
    echo "Made with love by DM Team (fayzetwin & others...)"
    echo "=================================================="
    echo -e "${NC}"
}

check_dependencies() {
    info "checking system dependencies (docker and docker compose)..."
    if ! command -v docker &> /dev/null; then
        error "docker is not installed. please install docker."
        exit 1
    fi

    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
    elif command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        error "docker compose is not installed. please, at first, install it"
        exit 1
    fi
    success "docker dependencies verified"
}

setup_env() {
    if [ ! -f .env ]; then
        warn ".env file not found."
        if [ -f .env.example ]; then
            info "creating .env file based on .env.example..."
            cp .env.example .env
            success ".env file successfully created"
            warn "please check and edit .env if necessary before continuing"
            read -p "press enter to continue..."
        else
            error ".env.example file not found. please create .env manually"
            exit 1
        fi
    else
        info ".env file found, using current settings"
    fi
}

install_local_requirements() {
    if [ -f "requirements.txt" ]; then
        read -p "do you want to install python dependencies locally? [y/N]: " install_deps
        if [[ "$install_deps" =~ ^[Yy]$ ]]; then
            if command -v python3 &> /dev/null; then
                info "creating virtual environment..."
                python3 -m venv .venv
                source .venv/bin/activate
                run_cmd pip install --upgrade pip
                run_cmd pip install -r requirements.txt
                success "local dependencies installed"
                deactivate
            else
                warn "python3 not found. skipping"
            fi
        fi
    fi
}

setup_dev() {
    info "starting development environment setup..."
    setup_env
    install_local_requirements

    info "building images..."
    run_cmd make dev-build

    info "starting containers..."
    run_cmd make dev-up

    info "waiting for database initialization (10 seconds)..."
    sleep 10

    info "applying migrations..."
    run_cmd make dev-migrate

    info "collecting static files..."
    run_cmd make dev-collectstatic

    info "creating cache table..."
    run_cmd make dev-cachetable

    read -p "do you want to create a superuser? [y/N]: " create_su
    if [[ "$create_su" =~ ^[Yy]$ ]]; then
        run_cmd make dev-superuser
    fi

    success "development environment successfully started!"
    info "web: http://localhost:9088 | admin: http://localhost:8088 | api: http://localhost:7088"
}

deploy_prod() {
    info "starting production deployment..."
    setup_env

    info "pulling latest images..."
    run_cmd $DOCKER_COMPOSE_CMD -f docker-compose.yml pull

    info "restarting containers..."
    run_cmd $DOCKER_COMPOSE_CMD -f docker-compose.yml up -d --remove-orphans

    info "waiting for database (5 seconds)..."
    sleep 5

    info "applying database migrations..."
    run_cmd $DOCKER_COMPOSE_CMD -f docker-compose.yml exec -T web python manage.py migrate

    info "collecting static files..."
    run_cmd $DOCKER_COMPOSE_CMD -f docker-compose.yml exec -T web python manage.py collectstatic --noinput

    info "creating cache table..."
    run_cmd $DOCKER_COMPOSE_CMD -f docker-compose.yml exec -T web python manage.py createcachetable

    info "restarting nginx..."
    run_cmd $DOCKER_COMPOSE_CMD -f docker-compose.yml restart nginx

    success "project successfully deployed to production!"
}

show_help() {
    echo -e "usage: $0 [command]"
    echo ""
    echo "commands:"
    echo -e "  ${GREEN}dev${NC}    - build and run development"
    echo -e "  ${RED}prod${NC}   - deploy to production"
}

show_header

case "$1" in
    dev)
        check_dependencies
        setup_dev
        ;;
    prod)
        check_dependencies
        deploy_prod
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        error "unknown command."
        show_help
        exit 1
        ;;
esac
