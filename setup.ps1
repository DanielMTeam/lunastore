param (
    [Parameter(Position=0)]
    [string]$Command = ""
)

function info { param([string]$msg); Write-Host "[info] $msg" -ForegroundColor Cyan }
function success { param([string]$msg); Write-Host "[success] $msg" -ForegroundColor Green }
function warn { param([string]$msg); Write-Host "[warning] $msg" -ForegroundColor Yellow }
function error_msg { param([string]$msg); Write-Host "[error] $msg" -ForegroundColor Red }

function show_header {
    Write-Host "`n=========================================================" -ForegroundColor Cyan
    Write-Host "LunaStore Installer          " -ForegroundColor Cyan
    Write-Host "Developed with love by DM Team (fayzetwin & others..)          " -ForegroundColor Cyan
    Write-Host "=========================================================`n" -ForegroundColor Cyan
}

$script:usePlugin = $false
function invoke-dc {
    $dcArgs = $args
    if ($script:usePlugin) {
        docker compose @dcArgs
    } else {
        docker-compose @dcArgs
    }

    if ($LASTEXITCODE -ne 0) {
        error_msg "docker was exited with error :< (Exit Code: $LASTEXITCODE); so, check if all is ok, and only after do anything with installer"
        exit $LASTEXITCODE
    }
}

function check_dependencies {
    info "checking system dependencies..."
    if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
        error_msg "docker is not installed"
        exit 1
    }

    $dockerComposeTest = docker compose version 2>$null
    if ($LASTEXITCODE -eq 0) {
        $script:usePlugin = $true
    } elseif (Get-Command "docker-compose" -ErrorAction SilentlyContinue) {
        $script:usePlugin = $false
    } else {
        error_msg "docker compose is not installed"
        exit 1
    }
    success "dependencies verified."
}

function setup_env {
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            info "creating .env from example..."
            Copy-Item ".env.example" -Destination ".env"
            warn "please check .env file."
            Read-Host "press enter to continue..."
        } else {
            error_msg ".env.example not found"
            exit 1
        }
    }
}

function install_local_requirements {
    if (Test-Path "requirements.txt") {
        $install_deps = Read-Host "install local python dependencies? [y/N]"
        if ($install_deps -match "^[Yy]$") {
            $pyCmd = if (Get-Command "python" -ErrorAction SilentlyContinue) { "python" } elseif (Get-Command "python3" -ErrorAction SilentlyContinue) { "python3" }
            if ($pyCmd) {
                & $pyCmd -m venv .venv
                $venvPython = ".\.venv\Scripts\python.exe"
                & $venvPython -m pip install --upgrade pip
                & $venvPython -m pip install -r requirements.txt
                if ($LASTEXITCODE -ne 0) { error_msg "python dependencies installation failed :<"; exit 1 }
                success "local dependencies installed"
            }
        }
    }
}

function setup_dev {
    info "starting dev setup..."
    setup_env
    install_local_requirements

    info "building and starting containers..."
    invoke-dc -f docker-compose.dev.yml build
    invoke-dc -f docker-compose.dev.yml up -d --no-deps --force-recreate

    info "waiting for db (10s)..."
    Start-Sleep -Seconds 10

    info "migrations..."
    invoke-dc -f docker-compose.dev.yml exec web python manage.py migrate

    info "static files..."
    invoke-dc -f docker-compose.dev.yml exec web python manage.py collectstatic --noinput

    info "cache table..."
    invoke-dc -f docker-compose.dev.yml exec web python manage.py createcachetable

    if ((Read-Host "create superuser? [y/N]") -match "^[Yy]$") {
        invoke-dc -f docker-compose.dev.yml exec web python manage.py createsuperuser
    }
    success "dev environment ready!"
}

function deploy_prod {
    info "starting production deployment..."
    setup_env

    info "pulling images..."
    invoke-dc -f docker-compose.yml pull

    info "starting containers..."
    invoke-dc -f docker-compose.yml up -d --no-deps --force-recreate

    info "waiting for db..."
    Start-Sleep -Seconds 5

    info "migrations..."
    invoke-dc -f docker-compose.yml exec web python manage.py migrate

    info "static..."
    invoke-dc -f docker-compose.yml exec web python manage.py collectstatic --noinput

    info "cache..."
    invoke-dc -f docker-compose.yml exec web python manage.py createcachetable

    info "restarting nginx..."
    invoke-dc -f docker-compose.yml restart nginx

    success "production deployment finished!"
}

show_header
switch ($Command.ToLower()) {
    "dev"  { check_dependencies; setup_dev }
    "prod" { check_dependencies; deploy_prod }
    default { error_msg "Unknown command."; exit 1 }
}
