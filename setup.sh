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

show_header() {
    echo -e "${CYAN}"
    echo "==================================================="
    echo "LunaStore Interactive Installer (Self-Hosting)"
    echo "Made with love by DM Team"
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

generate_password() {
    # Generate a random 32-character password
    cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1
}

setup_env_dev() {
    if [ ! -f .env ]; then
        warn ".env file not found."
        if [ -f .env.example ]; then
            info "creating .env file based on .env.example for DEVELOPMENT..."
            cp .env.example .env
            
            # Set default debug values for dev
            sed -i 's/DB_PASSWORD = "..."/DB_PASSWORD = "password"/' .env
            sed -i "s/SECRET_KEY='...'/SECRET_KEY='dev-secret-key-do-not-use-in-prod'/" .env
            sed -i 's/LUNASPIRE_SECRET_KEY = "supersecretkey"/LUNASPIRE_SECRET_KEY = "dev-spire-secret"/' .env
            
            success "Development .env file successfully created"
        else
            error ".env.example file not found. please create .env manually"
            exit 1
        fi
    else
        info ".env file found, using current settings"
    fi
}

setup_env_prod() {
    info "Setting up PRODUCTION (Self-Hosting) environment..."
    
    if [ -f .env ]; then
        warn ".env already exists."
        read -p "Do you want to overwrite it with new secure credentials? [y/N]: " overwrite_env
        if [[ ! "$overwrite_env" =~ ^[Yy]$ ]]; then
            info "Keeping existing .env file."
            return
        fi
    fi

    if [ ! -f .env.example ]; then
        error ".env.example file not found!"
        exit 1
    fi

    read -p "Enter your base domain or IP address (e.g. lunastore.app or 192.168.1.10): " DOMAIN

    info "Generating secure passwords..."
    DB_PASS=$(generate_password)
    SECRET=$(generate_password)
    SPIRE_SECRET=$(generate_password)

    cp .env.example .env

    # Apply Production settings
    sed -i 's/DEBUG = "True"/DEBUG = "False"/' .env
    sed -i "s/DB_PASSWORD = \"...\"/DB_PASSWORD = \"$DB_PASS\"/" .env
    sed -i "s/SECRET_KEY='...'/SECRET_KEY='$SECRET'/" .env
    sed -i "s/LUNASPIRE_SECRET_KEY = \"supersecretkey\"/LUNASPIRE_SECRET_KEY = \"$SPIRE_SECRET\"/" .env
    
    sed -i "s/ALLOWED_HOSTS = \"192.168.1.10;192.168.1.1\"/ALLOWED_HOSTS = \"$DOMAIN;127.0.0.1;localhost\"/" .env
    sed -i "s/CORS_ALLOWED_ORIGINS = \"http:\/\/192.168.1.10;http:\/\/192.168.1.1\"/CORS_ALLOWED_ORIGINS = \"https:\/\/$DOMAIN;http:\/\/$DOMAIN\"/" .env
    sed -i "s/CSRF_TRUSTED_ORIGINS = \"https:\/\/lunastore.app\"/CSRF_TRUSTED_ORIGINS = \"https:\/\/$DOMAIN;http:\/\/$DOMAIN\"/" .env
    sed -i "s/SESSION_COOKIE_DOMAIN = \".lunastore.app\"/SESSION_COOKIE_DOMAIN = \"$DOMAIN\"/" .env
    sed -i "s/CSRF_COOKIE_DOMAIN = \".lunastore.app\"/CSRF_COOKIE_DOMAIN = \"$DOMAIN\"/" .env

    success "Production .env file generated successfully!"
    info "Please remember to set up a reverse proxy (e.g., Caddy or Nginx) to route your domain traffic to ports 9088 (web), 8088 (admin), 7088 (api), 6080 (lunaspire)."
}

setup_dev() {
    info "starting development environment setup..."
    setup_env_dev

    info "building and starting development containers..."
    run_cmd $DOCKER_COMPOSE_CMD -f docker-compose.dev.yml up -d --build --remove-orphans

    info "waiting for database initialization (10 seconds)..."
    sleep 10

    info "applying migrations..."
    run_cmd $DOCKER_COMPOSE_CMD -f docker-compose.dev.yml exec -T web python manage.py migrate

    info "collecting static files..."
    run_cmd $DOCKER_COMPOSE_CMD -f docker-compose.dev.yml exec -T web python manage.py collectstatic --noinput

    info "creating cache table..."
    run_cmd $DOCKER_COMPOSE_CMD -f docker-compose.dev.yml exec -T web python manage.py createcachetable

    read -p "do you want to create a superuser? [y/N]: " create_su
    if [[ "$create_su" =~ ^[Yy]$ ]]; then
        run_cmd $DOCKER_COMPOSE_CMD -f docker-compose.dev.yml exec web python manage.py createsuperuser
    fi

    success "development environment successfully started!"
    info "web: http://localhost:9088 | admin: http://localhost:8088 | api: http://localhost:7088 | lunaspire: http://localhost:6080"
}

setup_selfhost_prod() {
    info "starting production self-hosting deployment..."
    setup_env_prod

    info "building and starting production containers..."
    run_cmd $DOCKER_COMPOSE_CMD -f docker-compose.selfhost.yml up -d --build --remove-orphans

    info "waiting for database and application startup (15 seconds)..."
    sleep 15

    read -p "do you want to create an admin superuser? [y/N]: " create_su
    if [[ "$create_su" =~ ^[Yy]$ ]]; then
        run_cmd $DOCKER_COMPOSE_CMD -f docker-compose.selfhost.yml exec -it lunastore python manage.py createsuperuser
    fi

    success "project successfully deployed for self-hosting!"
    info "Services are now running on ports:"
    info "  - Web: 9088"
    info "  - Admin: 8088"
    info "  - API: 7088"
    info "  - LunaSpire: 6080"
    info "You should now configure your reverse proxy (Nginx, Caddy, Apache) to point your domain to these ports."
}

show_help() {
    echo -e "usage: $0 [command]"
    echo ""
    echo "commands:"
    echo -e "  ${GREEN}dev${NC}       - setup for local development (debug enabled)"
    echo -e "  ${RED}prod${NC}      - setup for production self-hosting (generates secure passwords)"
    echo -e "  ${BLUE}wizard${NC}    - interactive mode (default if no command provided)"
}

wizard() {
    echo ""
    echo "Please select the installation mode:"
    echo "1) Development (Local, Debug=True, No secure passwords)"
    echo "2) Production Self-Hosting (Server, Debug=False, Secure passwords generated)"
    echo "3) Exit"
    read -p "Enter choice [1-3]: " choice

    case $choice in
        1) setup_dev ;;
        2) setup_selfhost_prod ;;
        3) exit 0 ;;
        *) error "Invalid choice"; exit 1 ;;
    esac
}

show_header
check_dependencies

case "$1" in
    dev) setup_dev ;;
    prod) setup_selfhost_prod ;;
    help|--help|-h) show_help ;;
    "") wizard ;;
    *) error "unknown command."; show_help; exit 1 ;;
esac
