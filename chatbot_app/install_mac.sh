#!/bin/bash
clear
echo ""
echo "  ╔══════════════════════════════════╗"
echo "  ║   AI Chatbot — Mac Setup         ║"
echo "  ╚══════════════════════════════════╝"
echo ""

# ── Step 1: Homebrew ──
if ! command -v brew &>/dev/null; then
    echo "  Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for Apple Silicon
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi
echo "  ✓ Homebrew ready"

# ── Step 2: Python ──
if ! command -v python3 &>/dev/null; then
    echo "  Installing Python..."
    brew install python3
fi
echo "  ✓ Python ready: $(python3 --version)"

# ── Step 3: Ollama ──
if ! command -v ollama &>/dev/null; then
    echo "  Installing Ollama..."
    brew install ollama
fi
echo "  ✓ Ollama ready"

# ── Step 4: Start Ollama ──
echo "  Starting Ollama..."
pkill ollama 2>/dev/null
sleep 1
ollama serve &>/dev/null &
sleep 3
echo "  ✓ Ollama running"

# ── Step 5: Pull model ──
echo "  Downloading AI model (qwen2.5:7b, ~4GB — only needed once)..."
ollama pull qwen2.5:7b
echo "  ✓ AI model ready"

# ── Step 6: Python packages ──
echo "  Installing Python packages..."
python3 -m pip install -q customtkinter ollama
echo "  ✓ Packages installed"

echo ""
echo "  ✓ All done! Launching chatbot..."
echo ""

# ── Step 7: Launch ──
python3 "$(dirname "$0")/chatbot_app.py"
