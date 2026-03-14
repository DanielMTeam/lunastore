param (
    [Parameter(Position=0)]
    [string]$Command = ""
)

function info {
    param([string]$msg)
    Write-Host "[info] $msg" -ForegroundColor Cyan
}

function success {
    param([string]$msg)
    Write-Host "[success] $msg" -ForegroundColor Green
}

function warn {
    param([string]$msg)
    Write-Host "[warning] $msg" -ForegroundColor Yellow
}

function error_msg {
    param([string]$msg)
    Write-Host "[error] $msg" -ForegroundColor Red
}

# header
function show_header {
    Write-Host ""
    Write-Host "=========================================================" -ForegroundColor Cyan
    Write-Host "                  LunaStore Installer                  " -ForegroundColor Cyan
    Write-Host "   Made with love by DM Team (fayzetwin & others...)" -ForegroundColor Cyan
    Write-Host "=========================================================" -ForegroundColor Cyan
    Write-Host ""
}

# helper to execute docker compose commands
$script:usePlugin = $false
function invoke-dc {
    if ($script:usePlugin) {
        docker compose $args
    } else {
        docker-compose $args
    }
}

# check for required system dependencies
function check_dependencies {
    info "checking system dependencies (docker and docker compose)..."

    if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
        error_msg "docker is not installed. please install docker desktop for windows."
        exit 1
    }

    # support both 'docker compose' plugin and legacy 'docker-compose'
    $dockerComposeTest = docker compose version 2>$null
    if ($LASTEXITCODE -eq 0) {
        $script:usePlugin = $true
    } elseif (Get-Command "docker-compose" -ErrorAction SilentlyContinue) {
        $script:usePlugin = $false
    } else {
        error_msg "docker compose is not installed. please install it."
        exit 1
    }

    success "docker dependencies verified."
}

# setup .env file
function setup_env {
    if (-not (Test-Path ".env")) {
        warn ".env file not found."
        if (Test-Path ".env.example") {
            info "creating .env file based on .env.example..."
            Copy-Item ".env.example" -Destination ".env"
            success ".env file successfully created."
            warn "please check and edit .env if necessary before continuing."
            Read-Host "press enter to continue..."
        } else {
            error_msg ".env.example file not found. please create .env manually."
            exit 1
        }
    } else {
        info ".env file found, using current settings."
    }
}

# install local python dependencies
function install_local_requirements {
    if (Test-Path "requirements.txt") {
        $install_deps = Read-Host "do you want to install python dependencies locally from requirements.txt (e.g., for ide support)? [y/N]"
        if ($install_deps -match "^[Yy]$") {
            info "checking for python..."

            $pyCmd = $null
            if (Get-Command "python" -ErrorAction SilentlyContinue) {
                $pyCmd = "python"
            } elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
                $pyCmd = "python3"
            }

            if ($pyCmd) {
                info "creating virtual environment (.venv)..."
                & $pyCmd -m venv .venv

                info "installing dependencies..."
                $venvPython = ".\.venv\Scripts\python.exe"
                & $venvPython -m pip install --upgrade pip
                & $venvPython -m pip install -r requirements.txt

                success "local dependencies installed successfully."
                info "to activate it manually later, run: .\.venv\Scripts\Activate.ps1"
            } else {
                warn "python is not installed on the host. skipping local dependencies installation."
            }
        }
    }
}

function setup_dev {
    info "starting development environment setup..."
    setup_env
    install_local_requirements

    info "building images and starting containers in the background..."
    invoke-dc -f docker-compose.dev.yml build
    invoke-dc -f docker-compose.dev.yml up -d --no-deps --force-recreate

    info "waiting for database initialization (10 seconds)..."
    Start-Sleep -Seconds 10

    info "applying migrations..."
    invoke-dc -f docker-compose.dev.yml exec web python manage.py migrate

    info "collecting static files..."
    invoke-dc -f docker-compose.dev.yml exec web python manage.py collectstatic --noinput

    info "creating cache table..."
    invoke-dc -f docker-compose.dev.yml exec web python manage.py createcachetable

    $create_su = Read-Host "do you want to create a superuser (admin)? [y/N]"
    if ($create_su -match "^[Yy]$") {
        info "creating superuser..."
        invoke-dc -f docker-compose.dev.yml exec web python manage.py createsuperuser
    }

    success "development environment successfully started!"
    info "web: http://localhost:9088 | admin: http://localhost:8088 | api: http://localhost:7088"
    info "to view logs, use: $(if($script:usePlugin){"docker compose"}else{"docker-compose"}) -f docker-compose.dev.yml logs -f"
}

# deploy to production
function deploy_prod {
    info "starting production deployment..."
    setup_env

    info "pulling latest images from registry..."
    invoke-dc -f docker-compose.yml pull

    info "restarting containers with new changes (graceful update)..."
    invoke-dc -f docker-compose.yml up -d --no-deps --force-recreate

    info "waiting for database to be ready (5 seconds)..."
    Start-Sleep -Seconds 5

    info "applying database migrations..."
    invoke-dc -f docker-compose.yml exec web python manage.py migrate

    info "collecting static files..."
    invoke-dc -f docker-compose.yml exec web python manage.py collectstatic --noinput

    info "creating or updating cache table..."
    invoke-dc -f docker-compose.yml exec web python manage.py createcachetable

    info "restarting nginx to apply new configurations and static files..."
    invoke-dc -f docker-compose.yml restart nginx

    success "project successfully deployed to production!"
}

# show help message
function show_help {
    Write-Host "usage: .\setup.ps1 [command]"
    Write-Host ""
    Write-Host "commands:"
    Write-Host "  dev    - full setup, build, and run development environment" -ForegroundColor Green
    Write-Host "  prod   - deploy/update project in production environment" -ForegroundColor Red
    Write-Host "  help   - show this message" -ForegroundColor Cyan
}

# main command router
show_header

switch ($Command.ToLower()) {
    "dev" {
        check_dependencies
        setup_dev
    }
    "prod" {
        check_dependencies
        deploy_prod
    }
    "help" {
        show_help
    }
    "-h" {
        show_help
    }
    "--help" {
        show_help
    }
    default {
        error_msg "unknown command or no command provided."
        Write-Host ""
        show_help
        exit 1
    }
}
