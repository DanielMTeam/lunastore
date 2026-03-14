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

# header
show_header() {
    echo -e "${CYAN}"
    echo "==================================================="
    echo "LunaStore Installer"
    echo "Made with love by DM Team (fayzetwin & others...)"
    echo "=================================================="
    echo -e "${NC}"
}

# check for required system dependencies
check_dependencies() {
    info "checking system dependencies (docker and docker compose)..."

    if ! command -v docker &> /dev/null; then
        error "docker is not installed. please install docker."
        exit 1
    fi

    # support both 'docker compose' plugin and legacy 'docker-compose'
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
    elif command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        error "docker compose is not installed. please install it."
        exit 1
    fi
    success "docker dependencies verified."
}

# setup .env file
setup_env() {
    if [ ! -f .env ]; then
        warn ".env file not found."
        if [ -f .env.example ]; then
            info "creating .env file based on .env.example..."
            cp .env.example .env
            success ".env file successfully created."
            warn "please check and edit .env if necessary before continuing."
            read -p "press enter to continue..."
        else
            error ".env.example file not found. please create .env manually."
            exit 1
        fi
    else
        info ".env file found, using current settings."
    fi
}

# install local python dependencies
install_local_requirements() {
    if [ -f "requirements.txt" ]; then
        read -p "do you want to install python dependencies locally from requirements.txt (e.g., for ide support)? [y/N]: " install_deps
        if [[ "$install_deps" =~ ^[Yy]$ ]]; then
            info "checking for python3..."
            if command -v python3 &> /dev/null; then
                info "creating virtual environment (.venv)..."
                python3 -m venv .venv

                info "activating virtual environment and installing dependencies..."
                source .venv/bin/activate
                pip install --upgrade pip
                pip install -r requirements.txt

                success "local dependencies installed successfully."
                info "to activate it manually later, run: source .venv/bin/activate"
                deactivate
            else
                warn "python3 is not installed on the host. skipping local dependencies installation."
            fi
        fi
    fi
}

# setup and run dev environment
setup_dev() {
    info "starting development environment setup..."
    setup_env
    install_local_requirements

    info "building images and starting containers in the background..."
    make dev-build
    make dev-up

    info "waiting for database initialization (10 seconds)..."
    sleep 10

    info "applying migrations..."
    make dev-migrate

    info "collecting static files..."
    make dev-collectstatic

    info "creating cache table..."
    make dev-cachetable

    read -p "do you want to create a superuser (admin)? [y/N]: " create_su
    if [[ "$create_su" =~ ^[Yy]$ ]]; then
        info "creating superuser..."
        make dev-superuser
    fi

    success "development environment successfully started!"
    info "web: http://localhost:9088 | admin: http://localhost:8088 | api: http://localhost:7088"
    info "to view logs, use: make dev-logs"
}

# deploy to production
deploy_prod() {
    info "starting production deployment..."
    setup_env

    info "pulling latest images from registry..."
    $DOCKER_COMPOSE_CMD -f docker-compose.yml pull

    info "restarting containers with new changes (graceful update)..."
    make up

    info "waiting for database to be ready (5 seconds)..."
    sleep 5

    info "applying database migrations..."
    make migrate

    info "collecting static files..."
    make collectstatic

    info "creating or updating cache table..."
    make cachetable

    info "restarting nginx to apply new configurations and static files..."
    $DOCKER_COMPOSE_CMD -f docker-compose.yml restart nginx

    success "project successfully deployed to production!"
}

# show help message
show_help() {
    echo -e "usage: $0 [command]"
    echo ""
    echo "commands:"
    echo -e "  ${GREEN}dev${NC}    - full setup, build, and run development environment (uses docker-compose.dev.yml)"
    echo -e "  ${RED}prod${NC}   - deploy/update project in production environment (pulls images, runs migrations, collects static)"
    echo -e "  ${BLUE}help${NC}   - show this message"
}

# main command router
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
        error "unknown command or no command provided."
        echo ""
        show_help
        exit 1
        ;;
esac
