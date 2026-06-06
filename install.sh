#!/bin/bash

echo ""
echo "================================================"
echo "   Client Finder Agent — Installer"
echo "================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo "Download it from https://python.org/downloads"
    exit 1
fi

echo "✓ Python 3 found"

# Create folder
mkdir -p ~/contact_finder
cd ~/contact_finder

# Download agent files
echo ""
echo "Downloading agent files..."
curl -fsSL https://raw.githubusercontent.com/GITHUB_USERNAME/REPO_NAME/main/agent.py -o agent.py
curl -fsSL https://raw.githubusercontent.com/GITHUB_USERNAME/REPO_NAME/main/requirements.txt -o requirements.txt

# Install dependencies
echo ""
echo "Installing dependencies..."
python3 -m pip install -r requirements.txt -q

echo ""
echo "================================================"
echo "   Installation complete!"
echo "================================================"
echo ""
echo "NEXT STEP — Install Ollama (the free AI):"
echo "  1. Go to https://ollama.com/download"
echo "  2. Download and open the Mac app"
echo "  3. Then run this command to download the AI model:"
echo ""
echo "     ollama pull qwen2.5:7b"
echo ""
echo "Then start the agent:"
echo ""
echo "     python3 ~/contact_finder/agent.py"
echo ""
