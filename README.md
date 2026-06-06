# Client Finder Agent

AI-powered lead generation tool. Tell it your profession — it figures out who needs your service and finds their contact emails automatically.

## Requirements

- Mac (Apple Silicon or Intel)
- Python 3.9+
- [Ollama](https://ollama.com/download) (free local AI)

## Setup

```bash
# 1. Install Ollama from https://ollama.com/download and open the app

# 2. Download the AI model (one-time, ~4GB)
ollama pull qwen2.5:7b

# 3. Install Python dependencies
python3 -m pip install -r requirements.txt

# 4. Run
python3 agent.py
```

## How it works

1. Tell the agent your profession and location
2. It brainstorms who would hire you (not your competitors)
3. You pick which client types to target
4. It searches hundreds of websites and extracts real emails
5. Results saved to CSV and copied to clipboard

## Features

- Thinks like a salesperson — finds clients, not competitors
- Filters junk emails (noreply, bounce, wordpress, etc.)
- Max 2 emails per website
- Exports to CSV + copies to clipboard
- 100% free, runs locally, no API key needed
