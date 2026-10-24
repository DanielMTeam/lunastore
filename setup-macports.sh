#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo " LunaStore: Installing Python 3.13, PostgreSQL 18 & Redis via MacPorts"
echo "======================================================================"
echo ""
echo "Please enter your macOS password for sudo if prompted:"
echo ""

sudo port -N install python313 py313-pip postgresql18-server postgresql18 redis

echo ""
echo ">> Configuring PostgreSQL 18 and Python 3.13 default links..."
sudo port select --set postgresql postgresql18 2>/dev/null || true
sudo port select --set python3 python313 2>/dev/null || true
sudo port select --set python python313 2>/dev/null || true

echo ""
echo ">> Initializing PostgreSQL 18 cluster..."
sudo mkdir -p /opt/local/var/db/postgresql18/defaultdb
sudo chown postgres:postgres /opt/local/var/db/postgresql18/defaultdb
sudo -u postgres /opt/local/lib/postgresql18/bin/initdb -D /opt/local/var/db/postgresql18/defaultdb 2>/dev/null || true

echo ""
echo ">> Starting PostgreSQL 18 and Redis background services..."
sudo port load postgresql18-server 2>/dev/null || true
sudo port load redis 2>/dev/null || true

echo ""
echo "======================================================================"
echo " [+] MacPorts dependencies installed and services started!"
echo "======================================================================"
echo ""
echo "Press any key to close this terminal window and return to Antigravity..."
read -n 1 -s
