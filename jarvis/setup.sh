#!/usr/bin/env bash
set -e

BOLD="\033[1m"
GREEN="\033[32m"
CYAN="\033[36m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

log()  { echo -e "${CYAN}[setup]${RESET} $*"; }
ok()   { echo -e "${GREEN}[✓]${RESET} $*"; }
warn() { echo -e "${YELLOW}[!]${RESET} $*"; }
die()  { echo -e "${RED}[✗]${RESET} $*"; exit 1; }

echo -e "\n${BOLD}  J.A.R.V.I.S — Automated Setup${RESET}\n"

# ── 1. Detect OS ─────────────────────────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
  Darwin) PLATFORM="mac" ;;
  Linux)  PLATFORM="linux" ;;
  *)      die "Unsupported OS: $OS" ;;
esac
ok "Platform: $PLATFORM"

# ── 2. Python 3.9+ ───────────────────────────────────────────────────────────
PYTHON=""
for cmd in python3.11 python3.10 python3.9 python3 python; do
  if command -v "$cmd" &>/dev/null; then
    VER=$("$cmd" -c "import sys; print(sys.version_info >= (3,9))" 2>/dev/null)
    if [ "$VER" = "True" ]; then
      PYTHON="$cmd"
      break
    fi
  fi
done
[ -z "$PYTHON" ] && die "Python 3.9+ not found. Install from https://python.org"
ok "Python: $($PYTHON --version)"

# ── 3. System dependencies ───────────────────────────────────────────────────
install_system_deps() {
  if [ "$PLATFORM" = "mac" ]; then
    if ! command -v brew &>/dev/null; then
      warn "Homebrew not found. Installing..."
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    log "Installing ffmpeg and portaudio via Homebrew..."
    brew install ffmpeg portaudio 2>&1 | grep -E "^(==>|Warning|Error)" || true
  else
    log "Installing ffmpeg and portaudio via apt..."
    sudo apt-get update -qq
    sudo apt-get install -y ffmpeg portaudio19-dev 2>&1 | grep -E "^(Setting up|E:)" || true
  fi
}

MISSING_DEPS=0
command -v ffmpeg &>/dev/null || MISSING_DEPS=1
$PYTHON -c "import pyaudio" 2>/dev/null || MISSING_DEPS=1

if [ "$MISSING_DEPS" = "1" ]; then
  log "Installing system dependencies..."
  install_system_deps
  ok "System dependencies installed"
else
  ok "System dependencies already present"
fi

# ── 4. Python virtual environment ────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  log "Creating virtual environment..."
  $PYTHON -m venv "$VENV_DIR"
  ok "Virtual environment created at .venv"
else
  ok "Virtual environment already exists"
fi

PY="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

log "Installing Python dependencies..."
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet -r "$SCRIPT_DIR/requirements.txt"
ok "Python dependencies installed"

# ── 5. API keys ───────────────────────────────────────────────────────────────
ENV_FILE="$SCRIPT_DIR/.env"

load_env() {
  [ -f "$ENV_FILE" ] && export $(grep -v '^#' "$ENV_FILE" | xargs) 2>/dev/null || true
}

load_env

prompt_key() {
  local VAR="$1"
  local LABEL="$2"
  local CURRENT="${!VAR}"
  if [ -z "$CURRENT" ]; then
    echo -ne "${CYAN}[setup]${RESET} Enter your ${BOLD}$LABEL${RESET}: "
    read -r VALUE
    [ -z "$VALUE" ] && die "$LABEL cannot be empty"
    echo "$VAR=$VALUE" >> "$ENV_FILE"
    export "$VAR"="$VALUE"
  else
    ok "$LABEL already set"
  fi
}

# Create .env if missing
if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" << 'ENVEOF'
ANTHROPIC_API_KEY=
ELEVENLABS_API_KEY=
CLAUDE_MODEL=claude-sonnet-4-6
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
ELEVENLABS_VOICE_ID=UmQN7jS1Ee8B1czsUtQh
ELEVENLABS_MODEL=eleven_turbo_v2
ENVEOF
fi

load_env

# Prompt for missing keys
if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "your_anthropic_api_key_here" ]; then
  echo -ne "${CYAN}[setup]${RESET} Enter your ${BOLD}Anthropic API key${RESET}: "
  read -r VALUE
  [ -z "$VALUE" ] && die "Anthropic API key cannot be empty"
  sed -i.bak "s|ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$VALUE|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
  export ANTHROPIC_API_KEY="$VALUE"
  ok "Anthropic API key saved"
else
  ok "Anthropic API key already set"
fi

if [ -z "$ELEVENLABS_API_KEY" ] || [ "$ELEVENLABS_API_KEY" = "your_elevenlabs_api_key_here" ]; then
  echo -ne "${CYAN}[setup]${RESET} Enter your ${BOLD}ElevenLabs API key${RESET}: "
  read -r VALUE
  [ -z "$VALUE" ] && die "ElevenLabs API key cannot be empty"
  sed -i.bak "s|ELEVENLABS_API_KEY=.*|ELEVENLABS_API_KEY=$VALUE|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
  export ELEVENLABS_API_KEY="$VALUE"
  ok "ElevenLabs API key saved"
else
  ok "ElevenLabs API key already set"
fi

# ── 6. Launch ─────────────────────────────────────────────────────────────────
PORT="${PORT:-5173}"

echo ""
echo -e "${BOLD}  All systems go. Launching Jarvis...${RESET}"
echo -e "  ${CYAN}http://localhost:${PORT}${RESET}  — open this in your browser"
echo -e "  Hold ${BOLD}Space${RESET} or ${BOLD}click${RESET} the sphere to speak"
echo -e "  Press ${BOLD}Ctrl+C${RESET} to shut down\n"

# Auto-open browser
if [ "$PLATFORM" = "mac" ]; then
  sleep 1.5 && open "http://localhost:$PORT" &
elif command -v xdg-open &>/dev/null; then
  sleep 1.5 && xdg-open "http://localhost:$PORT" &
fi

cd "$SCRIPT_DIR"
"$PY" server.py
