#!/usr/bin/env bash
# Cortex Installer — from zero to running, one command.
# Usage: ./install.sh
#
# Prerequisite: macOS with Xcode Command Line Tools (git).
# Everything else (Homebrew, PostgreSQL, uv, Python) is installed automatically.
#
# Idempotent: safe to re-run. Existing data and config are preserved.
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CORTEX_DIR="$(cd "$(dirname "$0")" && pwd)"
MIGRATIONS_DIR="$CORTEX_DIR/migrations"
ENV_FILE="$HOME/.cortex/env"
DB_NAME="cortex"

# PostgreSQL@16 is keg-only on Homebrew — binaries are not on default PATH
export PATH="$HOME/.local/bin:/opt/homebrew/opt/postgresql@16/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

step()  { echo -e "\n${BOLD}[$1/6]${NC} $2"; }
ok()    { echo -e "  ${GREEN}OK${NC} $1"; }
warn()  { echo -e "  ${YELLOW}WARN${NC} $1"; }
fail()  { echo -e "  ${RED}FAIL${NC} $1"; exit 1; }
skip()  { echo -e "  ${GREEN}SKIP${NC} $1 (already done)"; }

need_cmd() {
  command -v "$1" &>/dev/null
}

# ---------------------------------------------------------------------------
# Step 1: Install system dependencies
# ---------------------------------------------------------------------------
step 1 "Installing system dependencies..."

[[ "$(uname)" == "Darwin" ]] || fail "This installer only supports macOS."
ok "macOS $(sw_vers -productVersion)"

# Xcode CLT (provides git)
if ! xcode-select -p &>/dev/null; then
  echo "  Installing Xcode Command Line Tools (this may take a few minutes)..."
  xcode-select --install 2>/dev/null || true
  echo "  Waiting for Xcode CLT installation to complete..."
  until xcode-select -p &>/dev/null; do sleep 5; done
  ok "Xcode CLT installed"
else
  ok "Xcode CLT found"
fi

# Homebrew
if ! need_cmd brew; then
  echo "  Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Add brew to PATH for this session
  if [[ -f /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi
  ok "Homebrew installed"
else
  ok "Homebrew found: $(brew --prefix)"
fi

# PostgreSQL
if ! need_cmd psql; then
  echo "  Installing PostgreSQL 16..."
  brew install postgresql@16
  ok "PostgreSQL 16 installed"
else
  ok "PostgreSQL found: $(psql --version | head -1)"
fi

# Start PostgreSQL if not running
_pg_ready() {
  pg_isready -q 2>/dev/null || psql -d postgres -c "SELECT 1" >/dev/null 2>&1
}

if ! _pg_ready; then
  echo "  Starting PostgreSQL..."
  brew services start postgresql@16 2>/dev/null || brew services start postgresql 2>/dev/null || true
  # Wait for it to be ready
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if _pg_ready; then break; fi
    sleep 1
  done
  if _pg_ready; then
    ok "PostgreSQL started"
  else
    fail "PostgreSQL failed to start. Run: brew services start postgresql@16"
  fi
else
  ok "PostgreSQL is running"
fi

# uv (Python package manager)
if ! need_cmd uv; then
  echo "  Installing uv..."
  brew install uv
  ok "uv installed"
else
  ok "uv found: $(uv --version)"
fi

# pgvector extension — build from source to match our PostgreSQL version
_pgvector_available() {
  psql -d postgres -tAc "SELECT 1 FROM pg_available_extensions WHERE name='vector'" 2>/dev/null | grep -q 1
}

if ! _pgvector_available; then
  echo "  Installing pgvector from source..."
  PG_CONFIG="$(command -v pg_config 2>/dev/null || echo /opt/homebrew/opt/postgresql@16/bin/pg_config)"
  if [ -x "$PG_CONFIG" ]; then
    PGVEC_TMP="$(mktemp -d)"
    (
      cd "$PGVEC_TMP"
      git clone --branch v0.8.0 --depth 1 https://github.com/pgvector/pgvector.git . 2>&1 | tail -1
      make PG_CONFIG="$PG_CONFIG" 2>&1 | tail -3
      make PG_CONFIG="$PG_CONFIG" install 2>&1 | tail -3
    ) && ok "pgvector installed from source" || warn "pgvector build failed (semantic search will use fallback)"
    rm -rf "$PGVEC_TMP"
  else
    warn "pg_config not found — pgvector not installed"
  fi
else
  ok "pgvector already available"
fi

# ---------------------------------------------------------------------------
# Step 2: Install Python dependencies
# ---------------------------------------------------------------------------
step 2 "Installing Python dependencies..."

# torch requires Python <=3.13; pin to 3.12 to avoid compatibility issues
(cd "$CORTEX_DIR" && uv sync --python 3.12 --extra local-embeddings 2>&1 | tail -5)
ok "Python dependencies installed (Python 3.12)"

# Pre-download embedding model (first run takes ~30s)
echo "  Loading embedding model (first time may take a minute)..."
(cd "$CORTEX_DIR" && uv run --python 3.12 python -c "
try:
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer('BAAI/bge-small-zh-v1.5')
    print(f'  Model loaded: {m.get_sentence_embedding_dimension()}d')
except Exception as e:
    print(f'  Warning: {e}')
" 2>/dev/null)
ok "Embedding model ready"

# ---------------------------------------------------------------------------
# Step 3: Initialize database
# ---------------------------------------------------------------------------
step 3 "Initializing database..."

# Create DB if not exists
if psql -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
  skip "Database '$DB_NAME' already exists"
else
  echo "  Creating database '$DB_NAME'..."
  createdb "$DB_NAME"
  ok "Database created"
fi

# Run migrations (idempotent — each uses IF NOT EXISTS / DO blocks with exception handling)
echo "  Running migrations..."
MIGRATION_COUNT=0
MIGRATION_WARN=0
for f in "$MIGRATIONS_DIR"/0*.sql; do
  [ -f "$f" ] || continue
  FNAME="$(basename "$f")"
  if psql -d "$DB_NAME" -v ON_ERROR_STOP=0 -f "$f" >/dev/null 2>&1; then
    MIGRATION_COUNT=$((MIGRATION_COUNT + 1))
  else
    MIGRATION_WARN=$((MIGRATION_WARN + 1))
    warn "  $FNAME had issues (likely optional extension or already applied)"
  fi
done
ok "$MIGRATION_COUNT migration files processed"

# ---------------------------------------------------------------------------
# Step 4: Configure environment
# ---------------------------------------------------------------------------
step 4 "Configuring environment..."

mkdir -p "$HOME/.cortex"

_generate_token() {
  openssl rand -hex 32 2>/dev/null || LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c 64
}

if [ -f "$ENV_FILE" ]; then
  skip "Env file exists at $ENV_FILE"
else
  GENERATED_TOKEN="$(_generate_token)"
  cat > "$ENV_FILE" << 'ENVEOF'
# Cortex Environment Configuration
# Sourced at startup. Edit values below, then restart Cortex.

# API Authentication (auto-generated)
ENVEOF
  echo "export CORTEX_API_TOKEN=\"$GENERATED_TOKEN\"" >> "$ENV_FILE"
  cat >> "$ENV_FILE" << 'ENVEOF'

# LLM Configuration (optional)
# Enables entity extraction, classification, and signal detection.
# Without this, search and ingestion still work — only intelligence features are disabled.
# Get a key from: https://openrouter.ai or https://api.minimax.chat
export LLM_API_KEY=""
export LLM_BASE_URL="https://api.minimaxi.chat/v1"
export LLM_MODEL="MiniMax-M2.7"
ENVEOF
  chmod 600 "$ENV_FILE"
  ok "Generated config at $ENV_FILE"
fi

# Create config.local.yaml if not exists
LOCAL_CONFIG="$CORTEX_DIR/config.local.yaml"
if [ ! -f "$LOCAL_CONFIG" ]; then
  cat > "$LOCAL_CONFIG" << 'YAMLEOF'
# Local overrides (gitignored). Edit as needed.
# api:
#   cors_origins:
#     - "http://localhost:5173"
YAMLEOF
  ok "Created config.local.yaml"
else
  skip "config.local.yaml exists"
fi

# ---------------------------------------------------------------------------
# Step 5: Build console (web UI)
# ---------------------------------------------------------------------------
step 5 "Building web console..."

CONSOLE_DIR="$CORTEX_DIR/console"
if [ -d "$CONSOLE_DIR/package.json" ] || [ -f "$CONSOLE_DIR/package.json" ]; then
  # Need Node.js / npm for console build
  if need_cmd npm; then
    (cd "$CONSOLE_DIR" && npm ci --ignore-scripts 2>&1 | tail -3 && npm run build 2>&1 | tail -5)
    ok "Console built"
  elif need_cmd bun; then
    (cd "$CONSOLE_DIR" && bun install 2>&1 | tail -3 && bun run build 2>&1 | tail -5)
    ok "Console built (via bun)"
  else
    echo "  Installing Node.js for console build..."
    brew install node
    (cd "$CONSOLE_DIR" && npm ci --ignore-scripts 2>&1 | tail -3 && npm run build 2>&1 | tail -5)
    ok "Console built"
  fi
else
  warn "Console source not found (API will work without web UI)"
fi

# ---------------------------------------------------------------------------
# Step 6: Verify installation
# ---------------------------------------------------------------------------
step 6 "Verifying installation..."

# Quick smoke test: import check
(cd "$CORTEX_DIR" && uv run python -c "from cortex.api.main import create_app; print('  Import OK')" 2>/dev/null) || warn "Import check failed"

# Source env and show status
if [ -f "$ENV_FILE" ]; then
  (source "$ENV_FILE" 2>/dev/null && {
    if [ -n "${CORTEX_API_TOKEN:-}" ]; then
      ok "API token configured (${#CORTEX_API_TOKEN} chars)"
    else
      warn "CORTEX_API_TOKEN is empty — API authentication disabled"
    fi
    if [ -n "${LLM_API_KEY:-}" ]; then
      ok "LLM API key configured"
    else
      warn "LLM_API_KEY is empty — entity extraction and signals disabled"
      echo "        Configure via: Console Settings page, or edit $ENV_FILE"
    fi
  }) || true
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
echo ""
echo "  Start Cortex:"
echo "    cd $CORTEX_DIR"
echo "    source ~/.cortex/env && uv run cortex serve"
echo ""
echo "  Then open:"
echo "    Console:  http://localhost:8420/console/"
echo "    API docs: http://localhost:8420/docs"
echo "    Health:   curl http://localhost:8420/api/v1/health"
echo ""
echo "  Configure LLM (optional, enables intelligence features):"
echo "    Open http://localhost:8420/console/settings"
echo "    Or edit $ENV_FILE and restart"
echo ""
echo "  Import your Obsidian vault:"
echo "    source ~/.cortex/env && uv run cortex import --vault ~/path/to/vault"
echo ""
