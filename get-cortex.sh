#!/usr/bin/env bash
# Cortex Installer — from zero to running, one command.
# Usage: curl -sL https://raw.githubusercontent.com/.../get-cortex.sh | bash
#
# Or run locally: ./get-cortex.sh
#
# Installs: Homebrew, PostgreSQL 16, uv, bun, Python 3.12, pgvector,
# Cortex backend + WeChat agent, launchd services, and connects WeChat.
#
# Idempotent: safe to re-run. Existing data and config are preserved.
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CORTEX_REPO="${CORTEX_REPO:-https://github.com/cortex-engine/cortex.git}"
WECHAT_REPO="${WECHAT_REPO:-https://github.com/cortex-engine/cortex-wechat.git}"
CORTEX_DIR="$HOME/Projects/cortex"
WECHAT_DIR="$HOME/Projects/cortex-wechat"
ENV_FILE="$HOME/.cortex/env"
DB_NAME="cortex"

export PATH="$HOME/.bun/bin:$HOME/.local/bin:/opt/homebrew/opt/postgresql@16/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; CYAN='\033[0;36m'; NC='\033[0m'
TOTAL_STEPS=8

step()  { echo -e "\n${BOLD}${CYAN}[$1/$TOTAL_STEPS]${NC} ${BOLD}$2${NC}"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}!${NC} $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; exit 1; }
skip()  { echo -e "  ${GREEN}✓${NC} $1 (already done)"; }

need_cmd() { command -v "$1" &>/dev/null; }

_generate_token() {
  openssl rand -hex 32 2>/dev/null || LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c 64
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}  Cortex Installer${NC}"
echo -e "  Personal Knowledge Engine for VCs"
echo -e "  ─────────────────────────────────"
echo ""

# ---------------------------------------------------------------------------
# Step 1: System dependencies
# ---------------------------------------------------------------------------
step 1 "Installing system dependencies..."

[[ "$(uname)" == "Darwin" ]] || fail "This installer only supports macOS."
ok "macOS $(sw_vers -productVersion) ($(uname -m))"

# Xcode CLT
if ! xcode-select -p &>/dev/null; then
  echo "  Installing Xcode Command Line Tools..."
  xcode-select --install 2>/dev/null || true
  echo "  Waiting for installation (this may take a few minutes)..."
  until xcode-select -p &>/dev/null; do sleep 5; done
  ok "Xcode CLT installed"
else
  ok "Xcode CLT"
fi

# Homebrew
if ! need_cmd brew; then
  echo "  Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  [[ -f /opt/homebrew/bin/brew ]] && eval "$(/opt/homebrew/bin/brew shellenv)"
  ok "Homebrew installed"
else
  ok "Homebrew"
fi

# PostgreSQL
if ! need_cmd psql; then
  echo "  Installing PostgreSQL 16..."
  brew install postgresql@16
  ok "PostgreSQL 16 installed"
else
  ok "PostgreSQL $(psql --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)"
fi

# Start PostgreSQL
_pg_ready() { pg_isready -q 2>/dev/null || psql -d postgres -c "SELECT 1" >/dev/null 2>&1; }
if ! _pg_ready; then
  echo "  Starting PostgreSQL..."
  brew services start postgresql@16 2>/dev/null || brew services start postgresql 2>/dev/null || true
  for i in $(seq 1 10); do _pg_ready && break; sleep 1; done
  _pg_ready && ok "PostgreSQL started" || fail "PostgreSQL failed to start. Run: brew services start postgresql@16"
else
  ok "PostgreSQL running"
fi

# uv
if ! need_cmd uv; then
  echo "  Installing uv..."
  brew install uv
  ok "uv installed"
else
  ok "uv $(uv --version 2>/dev/null | head -1)"
fi

# bun
if ! need_cmd bun; then
  echo "  Installing bun..."
  brew install oven-sh/bun/bun 2>/dev/null || curl -fsSL https://bun.sh/install | bash
  [[ -f "$HOME/.bun/bin/bun" ]] && export PATH="$HOME/.bun/bin:$PATH"
  ok "bun installed"
else
  ok "bun $(bun --version 2>/dev/null)"
fi

# pgvector
_pgvector_available() {
  psql -d postgres -tAc "SELECT 1 FROM pg_available_extensions WHERE name='vector'" 2>/dev/null | grep -q 1
}
if ! _pgvector_available; then
  echo "  Installing pgvector (semantic search)..."
  PG_CONFIG="$(command -v pg_config 2>/dev/null || echo /opt/homebrew/opt/postgresql@16/bin/pg_config)"
  if [ -x "$PG_CONFIG" ]; then
    PGVEC_TMP="$(mktemp -d)"
    if (cd "$PGVEC_TMP" && git clone --branch v0.8.0 --depth 1 https://github.com/pgvector/pgvector.git . 2>&1 | tail -1 && make PG_CONFIG="$PG_CONFIG" 2>&1 | tail -3 && make PG_CONFIG="$PG_CONFIG" install 2>&1 | tail -3) 2>/dev/null; then
      ok "pgvector installed (semantic search enabled)"
    else
      warn "pgvector build failed — semantic search will use full-text fallback (功能正常，精度略低)"
    fi
    rm -rf "$PGVEC_TMP"
  else
    warn "pg_config not found — pgvector skipped"
  fi
else
  ok "pgvector available"
fi

# ---------------------------------------------------------------------------
# Step 2: Download Cortex
# ---------------------------------------------------------------------------
step 2 "Downloading Cortex..."

mkdir -p "$HOME/Projects"

if [ -d "$CORTEX_DIR/.git" ]; then
  skip "cortex repo at $CORTEX_DIR"
  (cd "$CORTEX_DIR" && git pull --ff-only 2>/dev/null) || true
else
  echo "  Cloning cortex backend..."
  git clone "$CORTEX_REPO" "$CORTEX_DIR" 2>&1 | tail -1
  ok "cortex cloned"
fi

if [ -d "$WECHAT_DIR/.git" ]; then
  skip "cortex-wechat repo at $WECHAT_DIR"
  (cd "$WECHAT_DIR" && git pull --ff-only 2>/dev/null) || true
else
  echo "  Cloning cortex-wechat..."
  git clone "$WECHAT_REPO" "$WECHAT_DIR" 2>&1 | tail -1
  ok "cortex-wechat cloned"
fi

# Python dependencies
echo "  Installing Python dependencies..."
(cd "$CORTEX_DIR" && uv sync --python 3.12 --extra local-embeddings 2>&1 | tail -3)
ok "Python dependencies"

# Pre-download embedding model
echo "  Loading embedding model (first time may take a minute)..."
(cd "$CORTEX_DIR" && uv run --python 3.12 python -c "
try:
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer('BAAI/bge-small-zh-v1.5')
    print(f'  Loaded: {m.get_sentence_embedding_dimension()}d vectors')
except Exception as e:
    print(f'  Warning: {e}')
" 2>/dev/null)
ok "Embedding model ready"

# Node/bun dependencies for WeChat agent
echo "  Installing WeChat agent dependencies..."
(cd "$WECHAT_DIR" && bun install 2>&1 | tail -3)
ok "WeChat agent dependencies"

# ---------------------------------------------------------------------------
# Step 3: Initialize database
# ---------------------------------------------------------------------------
step 3 "Initializing database..."

if psql -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
  skip "Database '$DB_NAME' exists"
else
  echo "  Creating database '$DB_NAME'..."
  createdb "$DB_NAME"
  ok "Database created"
fi

# Run migrations
echo "  Running migrations..."
MIGRATIONS_DIR="$CORTEX_DIR/migrations"
MIGRATION_COUNT=0
MIGRATION_SKIP=0
HAS_TRACKING=$(psql -d "$DB_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations'" 2>/dev/null || true)
for f in "$MIGRATIONS_DIR"/0*.sql; do
  [ -f "$f" ] || continue
  FNAME="$(basename "$f")"
  VNUM=$(echo "$FNAME" | sed 's/^0*//' | sed 's/_.*//')
  if [ "$HAS_TRACKING" = "1" ]; then
    ALREADY=$(psql -d "$DB_NAME" -tAc "SELECT 1 FROM schema_migrations WHERE version = $VNUM" 2>/dev/null || true)
    if [ "$ALREADY" = "1" ]; then
      MIGRATION_SKIP=$((MIGRATION_SKIP + 1))
      continue
    fi
  fi
  if psql -d "$DB_NAME" -v ON_ERROR_STOP=0 -f "$f" >/dev/null 2>&1; then
    MIGRATION_COUNT=$((MIGRATION_COUNT + 1))
    psql -d "$DB_NAME" -c "INSERT INTO schema_migrations (version, name) VALUES ($VNUM, '$FNAME') ON CONFLICT DO NOTHING" 2>/dev/null || true
  fi
done
ok "$MIGRATION_COUNT applied, $MIGRATION_SKIP already tracked"

# ---------------------------------------------------------------------------
# Step 4: Configure
# ---------------------------------------------------------------------------
step 4 "Configuring..."

mkdir -p "$HOME/.cortex"

if [ -f "$ENV_FILE" ]; then
  skip "Config exists at $ENV_FILE"
  # Ensure all keys present
  for key in LLM_BASE_URL LLM_API_KEY LLM_MODEL CORTEX_API_TOKEN; do
    if ! grep -q "^export $key=" "$ENV_FILE" 2>/dev/null; then
      case $key in
        LLM_BASE_URL)     echo "export LLM_BASE_URL=\"https://api.minimaxi.chat/v1\"" >> "$ENV_FILE" ;;
        LLM_API_KEY)      echo "export LLM_API_KEY=\"\"" >> "$ENV_FILE" ;;
        LLM_MODEL)        echo "export LLM_MODEL=\"MiniMax-M2.7\"" >> "$ENV_FILE" ;;
        CORTEX_API_TOKEN) echo "export CORTEX_API_TOKEN=\"$(_generate_token)\"" >> "$ENV_FILE" ;;
      esac
      warn "Added missing $key"
    fi
  done
else
  GENERATED_TOKEN="$(_generate_token)"
  cat > "$ENV_FILE" << ENVEOF
# Cortex Environment — auto-generated by installer
# Edit values below, then run: cortex restart

# API token (auto-generated, shared between services)
export CORTEX_API_TOKEN="$GENERATED_TOKEN"

# LLM config (enables entity extraction, signals, thesis evaluation)
export LLM_BASE_URL="https://api.minimaxi.chat/v1"
export LLM_API_KEY=""
export LLM_MODEL="MiniMax-M2.7"
ENVEOF
  chmod 600 "$ENV_FILE"
  ok "Generated API token"
fi

# Interactive LLM key prompt (only if empty and terminal is interactive)
if [ -t 0 ] && grep -q 'LLM_API_KEY=""' "$ENV_FILE" 2>/dev/null; then
  echo ""
  echo -e "  ${BOLD}── AI 增强功能（可选）──${NC}"
  echo "  填入 LLM API Key 启用实体提取、信号检测和论点评估。"
  echo "  不填也能用：收录和搜索正常工作，只是没有智能分析。"
  echo "  支持: MiniMax / OpenRouter / Gemini"
  echo ""
  printf "  LLM API Key（回车跳过）: "
  read -r LLM_KEY_INPUT
  if [ -n "$LLM_KEY_INPUT" ]; then
    sed -i.bak "s|^export LLM_API_KEY=\"\"|export LLM_API_KEY=\"$LLM_KEY_INPUT\"|" "$ENV_FILE"
    rm -f "${ENV_FILE}.bak"
    ok "LLM API Key configured"
  else
    ok "Skipped — running in basic mode (can add later via: cortex config)"
  fi
fi

# Create config.local.yaml
LOCAL_CONFIG="$CORTEX_DIR/config.local.yaml"
if [ ! -f "$LOCAL_CONFIG" ]; then
  cat > "$LOCAL_CONFIG" << 'YAMLEOF'
# Local overrides (gitignored). Edit as needed.
YAMLEOF
  ok "Created config.local.yaml"
fi

# ---------------------------------------------------------------------------
# Step 5: Build web console
# ---------------------------------------------------------------------------
step 5 "Building web console..."

CONSOLE_DIR="$CORTEX_DIR/console"
if [ -f "$CONSOLE_DIR/package.json" ]; then
  if need_cmd npm; then
    (cd "$CONSOLE_DIR" && npm ci --ignore-scripts 2>&1 | tail -3 && npm run build 2>&1 | tail -3)
  elif need_cmd bun; then
    (cd "$CONSOLE_DIR" && bun install 2>&1 | tail -3 && bun run build 2>&1 | tail -3)
  else
    echo "  Installing Node.js for console build..."
    brew install node
    (cd "$CONSOLE_DIR" && npm ci --ignore-scripts 2>&1 | tail -3 && npm run build 2>&1 | tail -3)
  fi
  ok "Console built"
else
  warn "Console source not found (API works without web UI)"
fi

# ---------------------------------------------------------------------------
# Step 6: Install services
# ---------------------------------------------------------------------------
step 6 "Installing system services..."

# Source env for wrapper generation
source "$ENV_FILE"

UV_PATH="$(command -v uv)"
BUN_PATH="$(command -v bun)"
BUN_DIR="$(dirname "$BUN_PATH")"
LAUNCHD_DIR="$WECHAT_DIR/scripts/launchd"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
LOG_CORTEX="$HOME/Library/Logs/cortex"
LOG_ILINK="$HOME/Library/Logs/cortex-wechat"

mkdir -p "$LAUNCHD_DIR" "$LAUNCH_AGENTS" "$LOG_CORTEX" "$LOG_ILINK"

# Generate wrapper scripts
cat > "$LAUNCHD_DIR/cortex-serve.sh" << EOF
#!/usr/bin/env bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export HOME="$HOME"
[ -f "$HOME/.cortex/env" ] && source "$HOME/.cortex/env"
export CORTEX_API_TOKEN="\${CORTEX_API_TOKEN:-}"
export LLM_API_KEY="\${LLM_API_KEY:-}"
cd "$CORTEX_DIR" || exit 1
exec "$UV_PATH" run cortex serve
EOF
chmod +x "$LAUNCHD_DIR/cortex-serve.sh"

cat > "$LAUNCHD_DIR/ilink-agent.sh" << EOF
#!/usr/bin/env bash
export PATH="$BUN_DIR:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export HOME="$HOME"
[ -f "$HOME/.cortex/env" ] && source "$HOME/.cortex/env"
export CORTEX_API_TOKEN="\${CORTEX_API_TOKEN:-}"
cd "$WECHAT_DIR" || exit 1
exec "$BUN_PATH" run start:ilink
EOF
chmod +x "$LAUNCHD_DIR/ilink-agent.sh"

# Generate plist files
cat > "$LAUNCHD_DIR/com.cortex.serve.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.cortex.serve</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$LAUNCHD_DIR/cortex-serve.sh</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG_CORTEX/serve.log</string>
  <key>StandardErrorPath</key><string>$LOG_CORTEX/serve.err</string>
</dict>
</plist>
EOF

cat > "$LAUNCHD_DIR/com.cortex.ilink-agent.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.cortex.ilink-agent</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$LAUNCHD_DIR/ilink-agent.sh</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG_ILINK/ilink-agent.log</string>
  <key>StandardErrorPath</key><string>$LOG_ILINK/ilink-agent.err</string>
</dict>
</plist>
EOF

# Install plists
cp "$LAUNCHD_DIR/com.cortex.serve.plist" "$LAUNCH_AGENTS/"
cp "$LAUNCHD_DIR/com.cortex.ilink-agent.plist" "$LAUNCH_AGENTS/"
ok "launchd services installed"

# Install cortex CLI wrapper
CORTEX_CLI="/usr/local/bin/cortex"
SERVICES_SH="$WECHAT_DIR/scripts/cortex-services.sh"
sudo tee "$CORTEX_CLI" > /dev/null << EOF
#!/usr/bin/env bash
# Cortex CLI — thin wrapper around cortex-services.sh
# Installed by get-cortex.sh

SERVICES="$SERVICES_SH"
ENV_FILE="$HOME/.cortex/env"

case "\${1:-}" in
  start|stop|restart|status|logs|install|uninstall)
    exec "\$SERVICES" "\$1"
    ;;
  config)
    echo "Config file: \$ENV_FILE"
    echo ""
    cat "\$ENV_FILE"
    echo ""
    echo "Edit with: nano \$ENV_FILE"
    echo "Then run:  cortex restart"
    ;;
  update)
    echo "Updating Cortex..."
    (cd "$CORTEX_DIR" && git pull --ff-only && uv sync --python 3.12 --extra local-embeddings 2>&1 | tail -3)
    (cd "$WECHAT_DIR" && git pull --ff-only && bun install 2>&1 | tail -3)
    # Run new migrations
    MIGRATIONS_DIR="$CORTEX_DIR/migrations"
    for f in "\$MIGRATIONS_DIR"/0*.sql; do
      [ -f "\$f" ] || continue
      psql -d cortex -v ON_ERROR_STOP=0 -f "\$f" >/dev/null 2>&1 || true
    done
    echo "Update complete. Run: cortex restart"
    ;;
  doctor)
    cd "$WECHAT_DIR" && exec bun run start:ilink -- doctor
    ;;
  *)
    echo "Cortex — Personal Knowledge Engine"
    echo ""
    echo "Usage: cortex <command>"
    echo ""
    echo "Commands:"
    echo "  status    Show service status"
    echo "  start     Start all services"
    echo "  stop      Stop all services"
    echo "  restart   Restart all services"
    echo "  logs      Tail service logs"
    echo "  config    Show/edit configuration"
    echo "  update    Pull latest code and update"
    echo "  doctor    Run health diagnostics"
    echo ""
    echo "Paths:"
    echo "  Config:   $HOME/.cortex/env"
    echo "  Backend:  $CORTEX_DIR"
    echo "  WeChat:   $WECHAT_DIR"
    echo "  Logs:     $HOME/Library/Logs/cortex/"
    ;;
esac
EOF
sudo chmod +x "$CORTEX_CLI"
ok "cortex CLI installed at /usr/local/bin/cortex"

# ---------------------------------------------------------------------------
# Step 7: Start services & verify
# ---------------------------------------------------------------------------
step 7 "Starting services..."

# Start cortex API first
UID_NUM=$(id -u)
launchctl load "$LAUNCH_AGENTS/com.cortex.serve.plist" 2>/dev/null || true
launchctl kickstart "gui/$UID_NUM/com.cortex.serve" 2>/dev/null || true
echo "  Waiting for Cortex API..."

HEALTH_OK=false
for i in $(seq 1 15); do
  if curl -sf http://127.0.0.1:8420/api/v1/health >/dev/null 2>&1; then
    HEALTH_OK=true
    break
  fi
  sleep 1
done

if $HEALTH_OK; then
  ok "Cortex API healthy (http://127.0.0.1:8420)"
else
  warn "Cortex API not ready yet — check logs: cortex logs"
fi

# ---------------------------------------------------------------------------
# Step 8: Connect WeChat
# ---------------------------------------------------------------------------
step 8 "Connecting WeChat..."

# Check if already authenticated
ACCOUNT_PATH="$HOME/.cortex/wechat/account.json"
if [ -f "$ACCOUNT_PATH" ]; then
  skip "WeChat already connected"
  # Start ilink-agent as background service
  launchctl load "$LAUNCH_AGENTS/com.cortex.ilink-agent.plist" 2>/dev/null || true
  launchctl kickstart "gui/$UID_NUM/com.cortex.ilink-agent" 2>/dev/null || true
  ok "WeChat agent started"
else
  if [ -t 0 ]; then
    echo ""
    echo -e "  ${BOLD}扫码连接微信${NC}"
    echo "  WeChat agent 将在前台运行，显示二维码。"
    echo "  扫码成功后按 Ctrl+C，服务将自动后台运行。"
    echo ""
    printf "  按回车开始扫码（输入 skip 跳过）: "
    read -r SCAN_INPUT
    if [ "$SCAN_INPUT" = "skip" ]; then
      warn "Skipped WeChat — connect later: cd $WECHAT_DIR && bun run start:ilink"
    else
      # Run ilink-agent in foreground for QR scan
      echo "  Starting WeChat agent (Ctrl+C after scanning)..."
      echo ""
      (cd "$WECHAT_DIR" && source "$ENV_FILE" && bun run start:ilink) || true
      # After Ctrl+C, start as background service
      if [ -f "$ACCOUNT_PATH" ]; then
        launchctl load "$LAUNCH_AGENTS/com.cortex.ilink-agent.plist" 2>/dev/null || true
        launchctl kickstart "gui/$UID_NUM/com.cortex.ilink-agent" 2>/dev/null || true
        ok "WeChat connected and running in background"
      else
        warn "QR scan may not have completed — retry: cd $WECHAT_DIR && bun run start:ilink"
      fi
    fi
  else
    warn "Non-interactive mode — connect WeChat manually:"
    echo "    cd $WECHAT_DIR && source ~/.cortex/env && bun run start:ilink"
  fi
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${GREEN}  Cortex installed successfully!${NC}"
echo ""
echo -e "  ${BOLD}Quick start:${NC}"
echo "    WeChat: send \"帮助\" to see all commands"
echo "    Console: http://127.0.0.1:8420/console"
echo ""
echo -e "  ${BOLD}Management:${NC}"
echo "    cortex status    — check services"
echo "    cortex logs      — view logs"
echo "    cortex restart   — restart services"
echo "    cortex config    — view/edit config"
echo "    cortex update    — update to latest"
echo "    cortex doctor    — run diagnostics"
echo ""
if grep -q 'LLM_API_KEY=""' "$ENV_FILE" 2>/dev/null; then
  echo -e "  ${YELLOW}!${NC} LLM not configured — running in basic mode."
  echo "    Add key: edit ~/.cortex/env, then cortex restart"
  echo ""
fi
echo -e "  ${BOLD}Documentation:${NC}"
echo "    https://github.com/cortex-engine/cortex"
echo ""
