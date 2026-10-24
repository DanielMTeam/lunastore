#!/usr/bin/env bash
# ==============================================================================
# LunaStore Local Development Runner (macOS / No-Docker)
# DM Team (fayzetwin & team)
#
# Unified Single-Window & Multi-Window runner adapted for macOS.
# Supports native MacPorts and Homebrew environments.
# Services: Web (:9088), Admin (:8088), API (:7088), Babel Watcher,
#           LunaSpire CDN (:8080), and Background Redis Task Worker.
#
# Usage:
#   ./run-dev.sh setup-mac    # Instructions & helper to install dependencies via MacPorts / Brew
#   ./run-dev.sh              # Full start in ONE console window (Default)
#   ./run-dev.sh fast         # Instant start (no checks, installs, or migrations)
#   ./run-dev.sh stop         # Stop all running LunaStore services
#   ./run-dev.sh restart      # Restart all services
#   ./run-dev.sh status       # Check status of ports and services
#   ./run-dev.sh services     # Start/stop background PostgreSQL and Redis
#   ./run-dev.sh migrate      # Run Django database migrations
#   ./run-dev.sh makemigrations # Generate new Django migrations
#   ./run-dev.sh build-js     # Compile JS for IE6 via Babel
#   ./run-dev.sh watch-js     # Start Babel JS watcher
#   ./run-dev.sh install      # Install Python venv & npm dependencies
#   ./run-dev.sh superuser    # Create Django superuser
#   ./run-dev.sh test         # Run Django test suite
#   ./run-dev.sh --separate-windows  # Open each service in its own Terminal window
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Automatically add MacPorts and Homebrew paths if present
for p in \
    "/opt/local/bin" \
    "/opt/local/sbin" \
    "/opt/local/lib/postgresql18/bin" \
    "/opt/local/lib/postgresql17/bin" \
    "/opt/local/lib/postgresql16/bin" \
    "/opt/homebrew/bin" \
    "/opt/homebrew/sbin" \
    "/opt/homebrew/opt/python@3.13/libexec/bin" \
    "/opt/homebrew/opt/postgresql@16/bin" \
    "/opt/homebrew/opt/postgresql@17/bin" \
    "/usr/local/bin" \
    "/usr/local/opt/python@3.13/libexec/bin" \
    "/usr/local/opt/postgresql@16/bin"; do
    if [ -d "$p" ] && [[ ":$PATH:" != *":$p:"* ]]; then
        export PATH="$p:$PATH"
    fi
done

# Colors & Formatting
COLOR_RESET="\033[0m"
COLOR_CYAN="\033[0;36m"
COLOR_DARKCYAN="\033[0;34m"
COLOR_GREEN="\033[0;32m"
COLOR_YELLOW="\033[1;33m"
COLOR_RED="\033[0;31m"
COLOR_MAGENTA="\033[0;35m"
COLOR_PURPLE="\033[0;35m"
COLOR_DARKMAGENTA="\033[0;35m"
COLOR_GRAY="\033[0;90m"
COLOR_WHITE="\033[1;37m"

log_info()    { echo -e "${COLOR_CYAN} [i] $1${COLOR_RESET}"; }
log_success() { echo -e "${COLOR_GREEN} [+] $1${COLOR_RESET}"; }
log_warn()    { echo -e "${COLOR_YELLOW} [!] $1${COLOR_RESET}"; }
log_error()   { echo -e "${COLOR_RED} [-] $1${COLOR_RESET}"; }

show_banner() {
    clear 2>/dev/null || true
    echo -e "${COLOR_DARKCYAN}======================================================================${COLOR_RESET}"
    echo -e "${COLOR_DARKCYAN}  _                              ____  _                  ${COLOR_RESET}"
    echo -e "${COLOR_DARKCYAN} | |   _   _ _ __   __ _        / ___|| |_ ___  _ __ ___  ${COLOR_RESET}"
    echo -e "${COLOR_DARKCYAN} | |  | | | | '_ \ / _\` | _____ \\___ \\| __/ _ \\| '__/ _ \\ ${COLOR_RESET}"
    echo -e "${COLOR_DARKCYAN} | |__| |_| | | | | (_| ||_____| ___) | || (_) | | |  __/ ${COLOR_RESET}"
    echo -e "${COLOR_DARKCYAN} |_____\\__,_|_| |_|\\__,_|       |____/ \\__\\___/|_|  \\___| ${COLOR_RESET}"
    echo -e "${COLOR_DARKCYAN}                                                          ${COLOR_RESET}"
    echo -e "${COLOR_CYAN} >> LunaStore Local Dev Environment (macOS / No-Docker)${COLOR_RESET}"
    echo -e "${COLOR_DARKCYAN} >> DM Team (fayzetwin & team)${COLOR_RESET}"
    echo -e "${COLOR_DARKCYAN}======================================================================${COLOR_RESET}"
}

# 1. Detect Python binary (.venv, venv, MacPorts or system python)
get_python_path() {
    if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
        echo "$SCRIPT_DIR/.venv/bin/python"
        return 0
    elif [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
        echo "$SCRIPT_DIR/venv/bin/python"
        return 0
    elif [ -x "$SCRIPT_DIR/.venv/bin/python3" ]; then
        echo "$SCRIPT_DIR/.venv/bin/python3"
        return 0
    elif [ -x "$SCRIPT_DIR/venv/bin/python3" ]; then
        echo "$SCRIPT_DIR/venv/bin/python3"
        return 0
    fi

    for candidate in \
        /opt/local/bin/python3.13 \
        /opt/local/bin/python3.12 \
        /opt/local/bin/python3 \
        python3.13 \
        /opt/homebrew/bin/python3.13 \
        python3.12 \
        python3.11 \
        python3 \
        /usr/local/bin/python3 \
        python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

get_system_python() {
    for candidate in \
        /opt/local/bin/python3.13 \
        /opt/local/bin/python3.12 \
        python3.13 \
        /opt/homebrew/bin/python3.13 \
        python3.12 \
        python3.11 \
        /opt/local/bin/python3 \
        python3 \
        /usr/local/bin/python3 \
        python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

# 2. Test TCP port listening
test_port_listening() {
    local host="${1:-127.0.0.1}"
    local port="$2"
    nc -z -w 1 "$host" "$port" >/dev/null 2>&1
    return $?
}

# 3. Install Python requirements and npm dependencies
install_all_dependencies() {
    log_info "Installing Python and Node.js dependencies..."

    local py
    py=$(get_python_path)

    local venv_exists=0
    if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
        local venv_ver
        venv_ver=$("$SCRIPT_DIR/.venv/bin/python" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        if [[ "$venv_ver" =~ ^3\.[0-9]$|^3\.1[01]$ ]]; then
            log_warn "Existing .venv uses Python $venv_ver (< 3.12, Django requires >= 3.12). Recreating .venv..."
            rm -rf "$SCRIPT_DIR/.venv"
            venv_exists=0
        else
            venv_exists=1
        fi
    fi

    if [ "$venv_exists" -eq 0 ] || [ "$FORCE_INSTALL" -eq 1 ]; then
        log_info "Creating virtual environment (.venv)..."
        local sys_py
        sys_py=$(get_system_python)
        if [ -z "$sys_py" ]; then
            log_error "Python 3 is not installed or not found in PATH!"
            log_info "Tip: Run './run-dev.sh setup-mac' for instructions on installing Python 3.13, PostgreSQL, and Redis."
            return 1
        fi

        # If .venv exists from Windows (Scripts/ instead of bin/), clean up Windows binaries
        if [ -d "$SCRIPT_DIR/.venv" ] && [ ! -d "$SCRIPT_DIR/.venv/bin" ]; then
            log_warn "Detected existing .venv created on Windows (contains Scripts/ instead of bin/). Recreating for macOS..."
            rm -rf "$SCRIPT_DIR/.venv/Include" "$SCRIPT_DIR/.venv/Lib" "$SCRIPT_DIR/.venv/Scripts" "$SCRIPT_DIR/.venv/pyvenv.cfg" 2>/dev/null
        fi

        "$sys_py" -m venv "$SCRIPT_DIR/.venv"
        py="$SCRIPT_DIR/.venv/bin/python"
    fi

    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        log_info "Upgrading pip and installing requirements.txt..."
        "$py" -m pip install --upgrade pip
        "$py" -m pip install -r "$SCRIPT_DIR/requirements.txt"
        if [ $? -eq 0 ]; then
            log_success "Python dependencies (requirements.txt) installed successfully."
        else
            log_error "Failed to install some dependencies from requirements.txt."
        fi
    else
        log_warn "requirements.txt not found!"
    fi

    if command -v npm >/dev/null 2>&1; then
        log_info "Installing Node.js dependencies (package.json)..."
        npm install
        if [ $? -eq 0 ]; then
            log_success "Node.js dependencies installed successfully."
        fi
    else
        log_warn "Node.js / npm not found. Babel compilation will be skipped."
    fi
}

# 4. Verify and prepare environment (.env, venv, requirements, npm, postgres, redis, lunaspire)
ensure_environment() {
    show_banner
    log_info "Checking dependencies and environment..."

    # Check .env
    local env_file="$SCRIPT_DIR/.env"
    if [ ! -f "$env_file" ]; then
        local env_example="$SCRIPT_DIR/.env.example"
        if [ -f "$env_example" ]; then
            log_warn "File .env not found. Creating from .env.example..."
            cp "$env_example" "$env_file"

            local sys_py
            sys_py=$(get_system_python)
            if [ -n "$sys_py" ]; then
                "$sys_py" -c '
import re, getpass

env_file = ".env"
with open(env_file, "r", encoding="utf-8") as f:
    content = f.read()

cur_user = getpass.getuser()

replacements = [
    (r"DB_HOST\s*=\s*\"db\"", "DB_HOST=\"127.0.0.1\""),
    (r"DB_HOST\s*=\s*\"\.\.\.\"", "DB_HOST=\"127.0.0.1\""),
    (r"DB_PORT\s*=\s*\"\.\.\.\"", "DB_PORT=\"5432\""),
    (r"DB_NAME\s*=\s*\"\.\.\.\"", "DB_NAME=\"lunastore_dev\""),
    (r"DB_USER\s*=\s*\"db\"", "DB_USER=\"postgres\""),
    (r"DB_PASSWORD\s*=\s*\"\.\.\.\"", "DB_PASSWORD=\"password\""),
    (r"SECRET_KEY\s*=\s*'\.\.\.'", "SECRET_KEY=\"dev-local-insecure-secret-key-for-lunastore\""),
    (r"ADMIN_URL\s*=\s*\"\.\.\"", "ADMIN_URL=\"admin\""),
    (r"ALLOWED_HOSTS\s*=.*", "ALLOWED_HOSTS=\"127.0.0.1;localhost;testserver\""),
    (r"LUNASPIRE_URL\s*=.*", "LUNASPIRE_URL=\"http://127.0.0.1:8080\""),
    (r"API_URL\s*=.*", "API_URL=\"http://127.0.0.1:7088\""),
    (r"SESSION_COOKIE_DOMAIN\s*=.*", "SESSION_COOKIE_DOMAIN=\"\""),
    (r"CSRF_COOKIE_DOMAIN\s*=.*", "CSRF_COOKIE_DOMAIN=\"\""),
    (r"CORS_ALLOWED_ORIGINS\s*=.*", "CORS_ALLOWED_ORIGINS=\"http://127.0.0.1:9088;http://localhost:9088;http://127.0.0.1:8088;http://localhost:8088;http://127.0.0.1:7088;http://localhost:7088;http://127.0.0.1:8080;http://localhost:8080\""),
    (r"CSRF_TRUSTED_ORIGINS\s*=.*", "CSRF_TRUSTED_ORIGINS=\"http://127.0.0.1:9088;http://localhost:9088;http://127.0.0.1:8088;http://localhost:8088;http://127.0.0.1:7088;http://localhost:7088;http://127.0.0.1:8080;http://localhost:8080;https://lunastore.app\""),
]

for pattern, repl in replacements:
    content = re.sub(pattern, repl, content)

if "REDIS_HOST" not in content:
    content += "\n\n# Local Redis Config\nREDIS_HOST=127.0.0.1\nREDIS_PORT=6379\nREDIS_URL=redis://127.0.0.1:6379/1\n"

# By default, disable Meilisearch in local standalone dev unless configured
content = re.sub(r"MEILISEARCH_ENABLED\s*=.*", "MEILISEARCH_ENABLED = \"False\"", content)

with open(env_file, "w", encoding="utf-8") as f:
    f.write(content)
'
            fi
            log_success "Created .env configured for localhost."
        else
            log_error ".env.example not found! Please create .env manually."
            exit 1
        fi
    fi

    # Check Python and virtualenv
    local py
    py=$(get_python_path)
    if [ -z "$py" ] || [ ! -x "$SCRIPT_DIR/.venv/bin/python" ] || [ "$FORCE_INSTALL" -eq 1 ]; then
        log_warn "Virtual environment (.venv) not found. Setting up..."
        install_all_dependencies
        py=$(get_python_path)
    else
        # Check if core dependencies are installed in venv
        local missing_core=0
        "$py" -c "import django, django_redis, safedelete, unfold" 2>/dev/null || missing_core=1

        if [ "$missing_core" -eq 1 ]; then
            log_warn "Core dependencies missing in virtual environment. Installing requirements.txt..."
            install_all_dependencies
        else
            log_success "Python virtual environment & core dependencies verified."
        fi
    fi

    # Check Node.js and npm modules
    if command -v npm >/dev/null 2>&1; then
        if [ ! -d "$SCRIPT_DIR/node_modules" ]; then
            log_info "Installing npm dependencies for Babel..."
            npm install
            log_success "npm dependencies installed."
        fi
    else
        log_warn "Node.js/npm not found. IE6 Babel auto-compilation will be skipped."
    fi

    # Check PostgreSQL and initialize database if needed
    if test_port_listening "127.0.0.1" 5432; then
        log_success "PostgreSQL detected on 127.0.0.1:5432"
        local db_init_res
        db_init_res=$("$py" -c '
import os, psycopg, getpass
from dotenv import load_dotenv
load_dotenv()
db_name = os.getenv("DB_NAME", "lunastore_dev")
db_user = os.getenv("DB_USER", "postgres")
db_pwd = os.getenv("DB_PASSWORD", "password")
db_host = os.getenv("DB_HOST", "127.0.0.1")
db_port = os.getenv("DB_PORT", "5432")
cur_user = getpass.getuser()

def try_connect():
    try:
        return psycopg.connect(dbname="postgres", user=db_user, password=db_pwd, host=db_host, port=db_port)
    except Exception:
        pass
    try:
        return psycopg.connect(dbname="postgres", user=cur_user, host=db_host, port=db_port)
    except Exception:
        pass
    try:
        return psycopg.connect(dbname="postgres", user="postgres", host=db_host, port=db_port)
    except Exception:
        pass
    return None

conn = try_connect()
if conn:
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        row = cur.fetchone()
        if not row:
            cur.execute(f"CREATE DATABASE \"{db_name}\"")
            print("created_db")
        cur.close()
        conn.close()
    except Exception:
        pass
' 2>/dev/null)
        if echo "$db_init_res" | grep -q "created_db"; then
            log_success "Created PostgreSQL database 'lunastore_dev'."
        fi
    else
        log_warn "PostgreSQL is NOT responding on 127.0.0.1:5432!"
        echo -e "${COLOR_YELLOW}       -> Run './run-dev.sh setup-mac' for instructions on setting up PostgreSQL and Redis without Docker.${COLOR_RESET}"
    fi

    # Check Redis
    if test_port_listening "127.0.0.1" 6379; then
        log_success "Redis detected on 127.0.0.1:6379"
    else
        log_warn "Redis is NOT responding on 127.0.0.1:6379!"
        echo -e "${COLOR_YELLOW}       -> Run './run-dev.sh setup-mac' to set up Redis.${COLOR_RESET}"
    fi

    # Check LunaSpire Git Submodule
    local lunaspire_dir="$SCRIPT_DIR/lunaspire"
    local has_spire_files=0
    if [ -f "$lunaspire_dir/src/main.go" ] || [ -f "$lunaspire_dir/main.go" ]; then
        has_spire_files=1
    fi

    if [ "$has_spire_files" -eq 0 ] && command -v git >/dev/null 2>&1; then
        log_info "Initializing LunaSpire git submodule..."
        git submodule update --init --recursive
        if [ $? -eq 0 ]; then
            log_success "LunaSpire submodule initialized."
        fi
    fi

    # Check LunaSpire .env
    local spire_env="$lunaspire_dir/.env"
    if [ ! -f "$spire_env" ] && [ -d "$lunaspire_dir" ]; then
        local spire_env_ex="$lunaspire_dir/.env.example"
        if [ -f "$spire_env_ex" ]; then
            log_info "Creating lunaspire/.env from example..."
            cp "$spire_env_ex" "$spire_env"
        fi
    fi
}

# 5. Stop running LunaStore dev processes
stop_lunastore_services() {
    log_info "Searching for and stopping LunaStore processes..."
    local stopped_count=0
    local pids=()

    local patterns=(
        "manage\.py runserver"
        "manage\.py run_tasks_worker"
        "manage\.py run_redis_tasks"
        "babel.*watch"
        "go run.*main\.go"
        "lunaspire"
    )

    for pat in "${patterns[@]}"; do
        while read -r p; do
            if [ -n "$p" ] && [ "$p" != "$$" ] && [ "$p" != "$PPID" ]; then
                pids+=("$p")
            fi
        done < <(pgrep -f "$pat" 2>/dev/null)
    done

    # Also check processes listening on dev ports
    for port in 9088 8088 7088 8080; do
        while read -r p; do
            if [ -n "$p" ] && [ "$p" != "$$" ] && [ "$p" != "$PPID" ]; then
                pids+=("$p")
            fi
        done < <(lsof -ti :"$port" 2>/dev/null)
    done

    local unique_pids=()
    if [ ${#pids[@]} -gt 0 ]; then
        while read -r u; do
            [ -n "$u" ] && unique_pids+=("$u")
        done < <(printf "%s\n" "${pids[@]}" | sort -u)
    fi

    for pid in "${unique_pids[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            local cmd_name
            cmd_name=$(ps -p "$pid" -o comm= 2>/dev/null | xargs basename 2>/dev/null || echo "process")
            pkill -TERM -P "$pid" 2>/dev/null || true
            kill -TERM "$pid" 2>/dev/null || true
            sleep 0.1
            if kill -0 "$pid" 2>/dev/null; then
                pkill -KILL -P "$pid" 2>/dev/null || true
                kill -KILL "$pid" 2>/dev/null || true
            fi
            log_success "Stopped process PID $pid: $cmd_name"
            ((stopped_count++))
        fi
    done

    if [ "$stopped_count" -eq 0 ]; then
        log_info "No running LunaStore processes found."
    else
        log_success "All LunaStore processes stopped ($stopped_count processes)."
    fi
}

kill_tree() {
    local pid="$1"
    local sig="${2:-TERM}"
    if [ -z "$pid" ]; then return; fi
    pkill -"$sig" -P "$pid" 2>/dev/null || true
    kill -"$sig" "$pid" 2>/dev/null || true
}

# 6. Build JS via Babel for IE6
build_babel_js() {
    log_info "Compiling JS via Babel to static/js/ (Target: IE6)..."
    if command -v npm >/dev/null 2>&1; then
        npm run babel:build
        if [ $? -eq 0 ]; then
            log_success "Babel build completed."
        else
            log_error "Babel build failed!"
        fi
    else
        log_warn "npm not found. Skipping Babel build."
    fi
}

# 7. Apply database migrations
invoke_migrations() {
    local py
    py=$(get_python_path)
    if [ -z "$py" ]; then
        log_error "Python not found!"
        return 1
    fi
    log_info "Applying database migrations..."
    "$py" manage.py migrate
    if [ $? -eq 0 ]; then
        log_success "Database migrations applied successfully."
    fi
}

# 8. Managed Process Launcher & Multiplexer
MANAGED_PIDS=()

start_stream_process() {
    local tag="$1"
    local color="$2"
    local work_dir="$3"
    shift 3

    (
        cd "$work_dir" || exit 1
        export PYTHONUNBUFFERED=1
        exec "$@"
    ) > >(awk -v t="$tag" -v c="$color" -v r="$COLOR_RESET" '{ printf "%s[%s]%s %s\n", c, t, r, $0; fflush(); }') 2>&1 &

    local pid=$!
    MANAGED_PIDS+=("$pid")
}

launch_terminal_window() {
    local title="$1"
    local command="$2"

    if command -v osascript >/dev/null 2>&1; then
        local escaped_cmd
        escaped_cmd=$(printf '%s' "$command" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g')
        osascript <<EOF >/dev/null 2>&1
tell application "Terminal"
    activate
    do script "cd '$SCRIPT_DIR' && printf '\\\033]2;$title\\\007' && $escaped_cmd"
end tell
EOF
    else
        log_warn "osascript not available. Running in background..."
        (
            cd "$SCRIPT_DIR" || exit 1
            eval "$command"
        ) &
    fi
}

cleanup_live() {
    trap - SIGINT SIGTERM EXIT
    echo ""
    log_warn "Stopping all LunaStore processes..."
    for pid in "${MANAGED_PIDS[@]}"; do
        kill_tree "$pid" TERM
    done
    sleep 0.5
    for pid in "${MANAGED_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill_tree "$pid" KILL
        fi
    done
    stop_lunastore_services
    log_success "All services stopped cleanly."
    exit 0
}

# 9. Core Process Launcher
launch_core_processes() {
    local py="$1"

    if [ "$SEPARATE_WINDOWS" -eq 1 ]; then
        log_info "Starting LunaStore processes in separate windows..."

        # 1. Web (:9088)
        launch_terminal_window "LunaStore Web (:9088)" "\"$py\" manage.py runserver ${BIND_HOST}:9088"

        # 2. Admin (:8088)
        launch_terminal_window "LunaStore Admin (:8088)" "export DJANGO_ROOT_URLCONF=lunastore.urls_private && \"$py\" manage.py runserver ${BIND_HOST}:8088"

        # 3. API (:7088)
        launch_terminal_window "LunaStore API (:7088)" "export DJANGO_ROOT_URLCONF=lunastore.urls_api && \"$py\" manage.py runserver ${BIND_HOST}:7088"

        # 4. Babel Watcher
        if [ "$NO_BABEL_WATCH" -eq 0 ] && command -v npm >/dev/null 2>&1; then
            launch_terminal_window "LunaStore Babel Watcher" "npm run babel:watch"
        fi

        # 5. LunaSpire CDN (Go engine)
        if [ "$NO_LUNASPIRE" -eq 0 ]; then
            local lunaspire_dir="$SCRIPT_DIR/lunaspire"
            local spire_main=""
            if [ -f "$lunaspire_dir/src/main.go" ]; then
                spire_main="./src/main.go"
            elif [ -f "$lunaspire_dir/main.go" ]; then
                spire_main="main.go"
            fi
            if command -v go >/dev/null 2>&1 && [ -n "$spire_main" ]; then
                log_info "Starting Go engine LunaSpire (:8080)..."
                launch_terminal_window "LunaStore LunaSpire CDN (:8080)" "cd '$lunaspire_dir' && go run $spire_main"
            fi
        fi

        # 6. Redis Task Worker
        if [ "$NO_WORKER" -eq 0 ]; then
            launch_terminal_window "LunaStore Redis Worker" "\"$py\" manage.py run_tasks_worker --continuous --interval 1.0"
        fi

        sleep 2
        check_services_status
    else
        # Unified Single-Window mode
        log_info "Starting all services in unified single-window console (Listening on $BIND_HOST)..."

        # 1. Web (:9088)
        start_stream_process "WEB" "$COLOR_CYAN" "$SCRIPT_DIR" "$py" manage.py runserver "${BIND_HOST}:9088"

        # 2. Admin (:8088)
        start_stream_process "ADMIN" "$COLOR_MAGENTA" "$SCRIPT_DIR" env DJANGO_ROOT_URLCONF="lunastore.urls_private" "$py" manage.py runserver "${BIND_HOST}:8088"

        # 3. API (:7088)
        start_stream_process "API" "$COLOR_YELLOW" "$SCRIPT_DIR" env DJANGO_ROOT_URLCONF="lunastore.urls_api" "$py" manage.py runserver "${BIND_HOST}:7088"

        # 4. Babel Watcher
        if [ "$NO_BABEL_WATCH" -eq 0 ]; then
            if command -v npx >/dev/null 2>&1; then
                start_stream_process "BABEL" "$COLOR_GREEN" "$SCRIPT_DIR" npx babel staticfiles/js/ --out-dir static/js/ --extensions .js --copy-files --watch --verbose
            elif command -v npm >/dev/null 2>&1; then
                start_stream_process "BABEL" "$COLOR_GREEN" "$SCRIPT_DIR" npm run babel:watch
            fi
        fi

        # 5. LunaSpire CDN (Go engine)
        if [ "$NO_LUNASPIRE" -eq 0 ]; then
            local lunaspire_dir="$SCRIPT_DIR/lunaspire"
            local spire_main=""
            if [ -f "$lunaspire_dir/src/main.go" ]; then
                spire_main="./src/main.go"
            elif [ -f "$lunaspire_dir/main.go" ]; then
                spire_main="main.go"
            fi
            if command -v go >/dev/null 2>&1 && [ -n "$spire_main" ]; then
                start_stream_process "SPIRE" "$COLOR_DARKCYAN" "$lunaspire_dir" go run "$spire_main"
            fi
        fi

        # 6. Redis Task Worker
        if [ "$NO_WORKER" -eq 0 ]; then
            start_stream_process "WORKER" "$COLOR_DARKMAGENTA" "$SCRIPT_DIR" "$py" manage.py run_tasks_worker --continuous --interval 1.0
        fi

        sleep 2
        check_services_status

        echo -e "${COLOR_YELLOW} [i] Live unified console active. Press Ctrl+C to stop all services.${COLOR_RESET}"
        echo -e "${COLOR_GRAY}----------------------------------------------------------------------${COLOR_RESET}"

        trap cleanup_live SIGINT SIGTERM

        while true; do
            sleep 1
        done
    fi
}

# 10. Standard Full Start (with checks, build, migrations)
start_lunastore_services() {
    ensure_environment

    # Check if ports already occupied
    if test_port_listening "127.0.0.1" 9088 || test_port_listening "127.0.0.1" 8088 || test_port_listening "127.0.0.1" 7088; then
        log_warn "Some LunaStore ports are already in use. Restarting processes..."
        stop_lunastore_services
        sleep 2
    fi

    local py
    py=$(get_python_path)

    # Build Babel JS
    build_babel_js

    # Run migrations
    invoke_migrations

    launch_core_processes "$py"
}

# 11. Fast Immediate Start (skips checks, installs, builds and migrations)
fast_start_lunastore_services() {
    show_banner
    log_info "Fast launch mode (skipping checks, installations, migrations & builds)..."

    local py
    py=$(get_python_path)
    if [ -z "$py" ]; then
        log_error "Python not found (.venv or system python)! Run './run-dev.sh start' first."
        return 1
    fi

    # Free ports if occupied
    if test_port_listening "127.0.0.1" 9088 || test_port_listening "127.0.0.1" 8088 || test_port_listening "127.0.0.1" 7088; then
        log_warn "Ports are currently in use. Stopping old processes..."
        stop_lunastore_services
        sleep 1
    fi

    launch_core_processes "$py"
}

# 12. Check services status
check_services_status() {
    echo ""
    echo -e "${COLOR_CYAN}======================================================================${COLOR_RESET}"
    echo -e "${COLOR_CYAN}                   LUNASTORE SERVICES STATUS                          ${COLOR_RESET}"
    echo -e "${COLOR_CYAN}======================================================================${COLOR_RESET}"

    local lan_ips
    lan_ips=$(ifconfig 2>/dev/null | awk '/inet / && !/127\.0\.0\.1/ && !/169\.254\./ {print $2}')
    local primary_lan=""
    if [ -n "$lan_ips" ]; then
        local ips_joined
        ips_joined=$(echo "$lan_ips" | tr '\n' ',' | sed 's/,$//' | sed 's/,/, /g')
        echo -e "${COLOR_DARKCYAN} [i] Network / VM IP Addresses: ${ips_joined}${COLOR_RESET}"
        echo -e "${COLOR_GRAY}----------------------------------------------------------------------${COLOR_RESET}"
        primary_lan=$(echo "$lan_ips" | head -n 1)
    fi

    local services=(
        "Web Frontend   |9088||Main UI (IE6/Retro compatible)"
        "Admin Panel    |8088|/admin/|Unfold Moderation Dashboard"
        "API & Swagger  |7088|/|REST API v2, RPC v1 & Swagger UI"
        "LunaSpire CDN  |8080|/|Go Storage & Push notifications"
        "PostgreSQL DB  |5432||Primary Database (Required)"
        "Redis Cache    |6379||Cache, Tasks, Rate Limits (Required)"
        "Meilisearch    |7700||Search Engine (Optional - ORM fallback)"
    )

    for item in "${services[@]}"; do
        IFS="|" read -r name port path desc <<< "$item"
        if test_port_listening "127.0.0.1" "$port"; then
            printf " ${COLOR_GREEN}[ONLINE]${COLOR_RESET}  ${COLOR_WHITE}%s -> ${COLOR_RESET}" "$name"
            if [ "$port" = "5432" ] || [ "$port" = "6379" ] || [ "$port" = "7700" ]; then
                printf "${COLOR_CYAN}127.0.0.1:%s ${COLOR_RESET}" "$port"
            else
                local lan_url=""
                if [ -n "$primary_lan" ]; then
                    lan_url=" | http://${primary_lan}:${port}${path}"
                fi
                printf "${COLOR_CYAN}http://127.0.0.1:%s%s%s ${COLOR_RESET}" "$port" "$path" "$lan_url"
            fi
            printf "${COLOR_GRAY}(%s)${COLOR_RESET}\n" "$desc"
        else
            printf " ${COLOR_RED}[OFFLINE]${COLOR_RESET} ${COLOR_WHITE}%s -> ${COLOR_RESET}" "$name"
            printf "${COLOR_YELLOW}Port %s not responding ${COLOR_RESET}" "$port"
            printf "${COLOR_GRAY}(%s)${COLOR_RESET}\n" "$desc"
        fi
    done

    local worker_running=0
    if pgrep -f "manage.py run_tasks_worker" >/dev/null 2>&1; then
        worker_running=1
    fi

    if [ "$worker_running" -eq 1 ]; then
        printf " ${COLOR_GREEN}[ONLINE]${COLOR_RESET}  ${COLOR_WHITE}Task Worker    -> ${COLOR_RESET}"
        printf "${COLOR_CYAN}Active (manage.py run_tasks_worker) ${COLOR_RESET}"
        printf "${COLOR_GRAY}(Background Redis queue worker)${COLOR_RESET}\n"
    else
        printf " ${COLOR_RED}[OFFLINE]${COLOR_RESET} ${COLOR_WHITE}Task Worker    -> ${COLOR_RESET}"
        printf "${COLOR_YELLOW}Not running ${COLOR_RESET}"
        printf "${COLOR_GRAY}(Background Redis queue worker)${COLOR_RESET}\n"
    fi
    echo -e "${COLOR_CYAN}======================================================================${COLOR_RESET}"
    echo ""
}

# 13. macOS Stack Setup Guide & Helper
setup_mac_stack() {
    show_banner
    log_info "Configuring macOS local development environment without Docker..."

    if command -v port >/dev/null 2>&1 || [ -x "/opt/local/bin/port" ]; then
        echo ""
        echo -e "${COLOR_GREEN}======================================================================${COLOR_RESET}"
        echo -e "${COLOR_GREEN}                 MacPorts detected on this system!                    ${COLOR_RESET}"
        echo -e "${COLOR_GREEN}======================================================================${COLOR_RESET}"
        echo "To install Python 3.13, PostgreSQL 18, and Redis, run the following in your terminal:"
        echo ""
        echo -e "${COLOR_YELLOW}# 1. Install packages via MacPorts:${COLOR_RESET}"
        echo "sudo port install python313 py313-pip postgresql18-server postgresql18 redis"
        echo ""
        echo -e "${COLOR_YELLOW}# 2. Initialize PostgreSQL 18 database instance:${COLOR_RESET}"
        echo "sudo port select --set postgresql postgresql18"
        echo "sudo mkdir -p /opt/local/var/db/postgresql18/defaultdb"
        echo "sudo chown postgres:postgres /opt/local/var/db/postgresql18/defaultdb"
        echo "sudo -u postgres /opt/local/lib/postgresql18/bin/initdb -D /opt/local/var/db/postgresql18/defaultdb"
        echo ""
        echo -e "${COLOR_YELLOW}# 3. Start PostgreSQL and Redis background services:${COLOR_RESET}"
        echo "sudo port load postgresql18-server"
        echo "sudo port load redis"
        echo ""
        echo -e "${COLOR_YELLOW}# 4. Once started, run this command to configure Django & start:${COLOR_RESET}"
        echo "./run-dev.sh start"
        echo -e "${COLOR_GREEN}======================================================================${COLOR_RESET}"
        return 0
    fi

    # Fallback: Homebrew
    echo "To set up services via Homebrew (Intel/AMD Mac):"
    echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo "  brew install postgresql@16 redis python@3.13"
    echo "  brew services start postgresql@16 redis"
}

# Manage background services
manage_services() {
    local cmd="${1:-status}"
    if command -v port >/dev/null 2>&1 || [ -x "/opt/local/bin/port" ]; then
        case "$cmd" in
            start)
                log_info "Starting PostgreSQL and Redis services via MacPorts..."
                sudo port load postgresql18-server 2>/dev/null || sudo port load postgresql16-server 2>/dev/null || true
                sudo port load redis 2>/dev/null || true
                log_success "Services started."
                ;;
            stop)
                log_info "Stopping PostgreSQL and Redis services via MacPorts..."
                sudo port unload postgresql18-server 2>/dev/null || sudo port unload postgresql16-server 2>/dev/null || true
                sudo port unload redis 2>/dev/null || true
                log_success "Services stopped."
                ;;
            status|*)
                check_services_status
                ;;
        esac
    elif command -v brew >/dev/null 2>&1; then
        case "$cmd" in
            start)
                brew services start postgresql@16 2>/dev/null || brew services start postgresql 2>/dev/null || true
                brew services start redis 2>/dev/null || true
                ;;
            stop)
                brew services stop postgresql@16 2>/dev/null || brew services stop postgresql 2>/dev/null || true
                brew services stop redis 2>/dev/null || true
                ;;
            status|*)
                brew services list
                ;;
        esac
    else
        check_services_status
    fi
}

show_help() {
    show_banner
    echo -e "${COLOR_YELLOW}Usage: ./run-dev.sh [command] [options]${COLOR_RESET}"
    echo ""
    echo -e "${COLOR_WHITE}Available commands:${COLOR_RESET}"
    echo "  setup-mac      - Show exact MacPorts / Brew commands to set up DB, Redis & Python 3.13"
    echo "  services       - Manage background services: ./run-dev.sh services [start|stop|status]"
    echo "  fast / run     - Instant start in ONE single console window [FASTEST]"
    echo "  start          - Full start in ONE single console window (Default)"
    echo "  stop           - Stop all running LunaStore services"
    echo "  restart        - Stop and start all services"
    echo "  status         - Check health and ports of all services"
    echo "  install        - Install / update requirements.txt and npm dependencies"
    echo "  migrate        - Apply database migrations"
    echo "  makemigrations - Generate new migrations"
    echo "  build-js       - Build Babel JS bundle for IE6"
    echo "  watch-js       - Start Babel JS watcher"
    echo "  superuser      - Create Django superuser"
    echo "  test           - Run Django test suite"
    echo "  help           - Show this help message"
    echo ""
    echo -e "${COLOR_WHITE}Options:${COLOR_RESET}"
    echo "  --separate-windows, --tabs  - Open each service in its own separate Terminal window"
    echo "  --no-babel-watch            - Do not run Babel JS watcher"
    echo "  --no-lunaspire              - Do not run LunaSpire Go engine"
    echo "  --no-worker                 - Do not run background Redis tasks worker"
    echo "  --force-install             - Force reinstallation of dependencies"
    echo "  --host <ip>                 - Bind host address (default: 0.0.0.0)"
    echo "  --fast, -f                  - Alias for 'fast' command"
}

# Parse Arguments
ACTION=""
SUB_ARG=""
BIND_HOST=""
FAST=0
SEPARATE_WINDOWS=0
NO_BABEL_WATCH=0
NO_LUNASPIRE=0
NO_WORKER=0
FORCE_INSTALL=0

while [ $# -gt 0 ]; do
    case "$1" in
        --fast|-f|-Fast)
            FAST=1
            ;;
        --quick|-q|-Quick)
            FAST=1
            ;;
        --separate-windows|--multi-window|-SeparateWindows|-MultiWindow|--tabs)
            SEPARATE_WINDOWS=1
            ;;
        --no-babel-watch|-NoBabelWatch)
            NO_BABEL_WATCH=1
            ;;
        --no-lunaspire|-NoLunaSpire)
            NO_LUNASPIRE=1
            ;;
        --no-worker|-NoWorker)
            NO_WORKER=1
            ;;
        --force-install|-ForceInstall)
            FORCE_INSTALL=1
            ;;
        --host)
            shift
            BIND_HOST="$1"
            ;;
        --help|-h|-help)
            ACTION="help"
            ;;
        -*)
            echo "Unknown option: $1"
            ACTION="help"
            ;;
        *)
            if [ -z "$ACTION" ]; then
                ACTION="$1"
            elif [ -z "$SUB_ARG" ]; then
                SUB_ARG="$1"
            elif [ -z "$BIND_HOST" ]; then
                BIND_HOST="$1"
            fi
            ;;
    esac
    shift
done

ACTION="${ACTION:-start}"
BIND_HOST="${BIND_HOST:-0.0.0.0}"
if [ "$FAST" -eq 1 ]; then
    ACTION="fast"
fi

# Command Dispatcher
case "$(echo "$ACTION" | tr '[:upper:]' '[:lower:]')" in
    setup-mac|setup_mac|setup)
        setup_mac_stack
        ;;
    services|service)
        manage_services "$SUB_ARG"
        ;;
    start)
        start_lunastore_services
        ;;
    fast|quick|run|up)
        fast_start_lunastore_services
        ;;
    stop)
        show_banner
        stop_lunastore_services
        ;;
    restart)
        show_banner
        stop_lunastore_services
        sleep 2
        start_lunastore_services
        ;;
    status)
        show_banner
        check_services_status
        ;;
    install|install-deps|requirements)
        show_banner
        install_all_dependencies
        ;;
    migrate)
        show_banner
        invoke_migrations
        ;;
    makemigrations)
        show_banner
        py=$(get_python_path)
        "$py" manage.py makemigrations
        ;;
    build-js)
        show_banner
        build_babel_js
        ;;
    watch-js)
        show_banner
        npm run babel:watch
        ;;
    superuser)
        show_banner
        py=$(get_python_path)
        "$py" manage.py createsuperuser
        ;;
    test)
        show_banner
        py=$(get_python_path)
        "$py" manage.py test
        ;;
    help)
        show_help
        ;;
    *)
        echo "Unknown command: $ACTION"
        show_help
        exit 1
        ;;
esac
