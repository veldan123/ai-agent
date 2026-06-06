#!/bin/bash
clear
echo ""
echo "  ╔══════════════════════════════════╗"
echo "  ║   Client Finder AI — Mac Setup   ║"
echo "  ╚══════════════════════════════════╝"
echo ""

# ── Homebrew ──
if ! command -v brew &>/dev/null; then
    echo "  Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    [ -f /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"
fi
echo "  ✓ Homebrew ready"

# ── Python ──
if ! command -v python3 &>/dev/null; then
    echo "  Installing Python..."
    brew install python3
fi
echo "  ✓ Python ready: $(python3 --version)"

# ── Ollama ──
if ! command -v ollama &>/dev/null; then
    echo "  Installing Ollama..."
    brew install ollama
fi
echo "  ✓ Ollama ready"

# ── Start Ollama ──
echo "  Starting Ollama..."
pkill ollama 2>/dev/null; sleep 1
ollama serve &>/dev/null &
sleep 3
echo "  ✓ Ollama running"

# ── AI Model ──
if ! ollama list 2>/dev/null | grep -q "qwen2.5:7b"; then
    echo "  Downloading AI model (~4GB, one-time)..."
    ollama pull qwen2.5:7b
fi
echo "  ✓ Model ready"

# ── Python packages ──
echo "  Installing packages..."
python3 -m pip install -q ollama requests beautifulsoup4 rich duckduckgo-search --break-system-packages
echo "  ✓ Packages installed"

# ── Download agent ──
echo "  Downloading agent..."
mkdir -p ~/contact_finder
curl -fsSL "https://raw.githubusercontent.com/veldan123/ai-agent/main/agent.py" -o ~/contact_finder/agent.py
echo "  ✓ Agent ready"

echo ""
echo "  ✓ Done! Launching Client Finder..."
echo ""
python3 ~/contact_finder/agent.py
