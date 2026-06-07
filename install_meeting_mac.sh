#!/bin/bash
clear
echo ""
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║  Meeting & Call Notes Summarizer — Setup   ║"
echo "  ╚═══════════════════════════════════════════╝"
echo ""
echo "  Note: this installs an AI model (a few GB), so the first run"
echo "  can take a while. If something errors out partway through,"
echo "  just run this same command again — it almost always works"
echo "  the 2nd time."
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
echo "  Waiting for Ollama to be ready..."
for i in $(seq 1 30); do
    ollama list &>/dev/null && break
    sleep 1
done
echo "  ✓ Ollama running"

# ── AI Model ──
if ! ollama list 2>/dev/null | grep -q "gemma3:4b"; then
    echo "  Downloading AI model (~3GB, one-time)..."
    ollama pull gemma3:4b
fi
echo "  ✓ Model ready"

# ── Python packages ──
echo "  Installing packages..."
python3 -m pip install -q ollama rich --break-system-packages
echo "  ✓ Packages installed"

# ── Download agent ──
echo "  Downloading Meeting & Call Notes Summarizer..."
mkdir -p ~/meeting_notes
curl -fsSL "https://raw.githubusercontent.com/veldan123/ai-agent/main/meeting_notes/agent.py" -o ~/meeting_notes/agent.py
echo "  ✓ Ready"

echo ""
echo "  ✓ Done! Launching Meeting & Call Notes Summarizer..."
echo ""
python3 ~/meeting_notes/agent.py || {
    echo ""
    echo "  ⚠️  Something didn't finish cleanly on this run."
    echo "  This is common on a first-time install — please run the"
    echo "  install command again and it should work the second time."
    echo ""
}
