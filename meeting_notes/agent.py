#!/usr/bin/env python3
import os, sys, re, time, random, subprocess, urllib.request
from datetime import datetime

import ollama
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.align import Align
from rich import box

VERSION     = "1.0.0"
VERSION_URL = "https://raw.githubusercontent.com/veldan123/ai-agent/main/meeting_notes/version.txt"
APP_URL     = "https://raw.githubusercontent.com/veldan123/ai-agent/main/meeting_notes/agent.py"
APP_PATH    = os.path.expanduser("~/meeting_notes/agent.py")

MODEL        = "gemma3:4b"
console      = Console()
OUTPUT_DIR   = os.path.expanduser("~/meeting_summaries")
MAX_CHARS    = 14000  # keep the transcript within the model's context window


def check_update():
    try:
        with urllib.request.urlopen(VERSION_URL, timeout=5) as r:
            remote = r.read().decode().strip()
        if remote != VERSION:
            console.print(f"  [cyan]⬆ Updating {VERSION} → {remote}...[/cyan]")
            urllib.request.urlretrieve(APP_URL, APP_PATH)
            os.execv(sys.executable, [sys.executable, APP_PATH])
    except Exception:
        pass  # No internet or GitHub down — just continue with current version


# ── Boot / banner ──
def boot_sequence():
    steps = [
        "linking local AI engine (gemma3:4b)",
        "loading transcript parser",
        "preparing summary workspace",
    ]
    for step in steps:
        with console.status(f"[dim blue]{step}...[/dim blue]", spinner="dots12"):
            time.sleep(random.uniform(0.35, 0.6))
        console.print(f"  [dim blue]›[/dim blue] [dim]{step}[/dim] [bold green]done[/bold green]")
    console.print("  [bold green]✓ all systems online[/bold green]")
    time.sleep(0.3)
    console.print()


def banner():
    console.clear()
    console.print()
    boot_sequence()
    console.print(Panel(
        Align.center(Text("📋  Meeting & Call Notes Summarizer", style="bold blue")),
        subtitle="Paste a transcript — AI pulls out the summary, decisions & action items",
        box=box.DOUBLE,
        border_style="blue",
        padding=(1, 4),
    ))
    console.print()


# ── Getting the transcript ──
def get_transcript():
    console.print("  [bold]How do you want to provide the transcript?[/bold]")
    console.print("    [cyan]1.[/cyan] Paste / type it directly")
    console.print("    [cyan]2.[/cyan] Load it from a text file\n")
    choice = Prompt.ask("  Pick one", choices=["1", "2"], default="1")
    console.print()

    if choice == "2":
        path = Prompt.ask("  [bold]Path to the transcript file[/bold] [dim](.txt)[/dim]").strip().strip('"').strip("'")
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            console.print(f"\n  [bold red]File not found: {path}[/bold red]\n")
            return None
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()

    console.print("  [dim]Paste or type the transcript below.[/dim]")
    console.print("  [dim]When you're done, type a line with just END[/dim]\n")
    lines = []
    while True:
        line = console.input("  ")
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


# ── AI summarization ──
THINKING_MSGS = [
    "[blue]⚡ reading through the transcript...[/blue]",
    "[blue]⚡ pulling out the key points...[/blue]",
    "[blue]⚡ identifying decisions & action items...[/blue]",
    "[blue]⚡ structuring the summary...[/blue]",
]

SECTION_ORDER = ["summary", "key_points", "decisions", "action_items"]
SECTION_TITLES = {
    "summary":      "Summary",
    "key_points":   "Key Points",
    "decisions":    "Decisions",
    "action_items": "Action Items",
}


def build_prompt(transcript):
    return f"""Read this meeting/call transcript and extract the key information.

TRANSCRIPT:
{transcript}

Organize your response in EXACTLY this format with these four section headers
in capitals followed by a colon. If a section doesn't apply, write
"Nothing recorded" under it — never invent details that aren't in the transcript.

SUMMARY:
<a 2-4 sentence plain-English overview of what this meeting covered and its outcome>

KEY POINTS:
<the main topics and points discussed — one per line, each starting with •>

DECISIONS:
<any decisions or agreements that were reached — one per line, each starting with •>

ACTION ITEMS:
<specific tasks that came out of this meeting, including who's responsible and
any deadline if mentioned — one per line, each starting with •>

Rules:
- Pull only from what's actually said in the transcript — never invent names,
  numbers, or commitments that aren't there
- Be concise and specific
- Plain text only — no markdown formatting like ** or # or numbered headers
- Output ONLY the four sections above, nothing else"""


def clean_markdown(text):
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", text)
    text = re.sub(r"^[ \t]*[-*]\s+", "• ", text, flags=re.MULTILINE)
    return text


def parse_summary(text):
    text = clean_markdown(text)
    patterns = {
        "summary":      r"SUMMARY:\s*(.*?)(?=\n\s*KEY POINTS:|\Z)",
        "key_points":   r"KEY POINTS:\s*(.*?)(?=\n\s*DECISIONS:|\Z)",
        "decisions":    r"DECISIONS:\s*(.*?)(?=\n\s*ACTION ITEMS:|\Z)",
        "action_items": r"ACTION ITEMS:\s*(.*?)\Z",
    }
    sections = {}
    for key, pat in patterns.items():
        m = re.search(pat, text, re.DOTALL | re.IGNORECASE)
        sections[key] = (m.group(1).strip() if m else "") or "Nothing recorded"
    return sections


def generate_summary(transcript):
    prompt = build_prompt(transcript)
    resp = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"num_ctx": 8192},
    )
    return parse_summary(resp["message"]["content"].strip())


# ── Display & save ──
def render_summary(sections, title):
    body = "\n\n".join(
        f"[bold]{SECTION_TITLES[key]}[/bold]\n{sections[key]}"
        for key in SECTION_ORDER
    )
    console.print(Panel(
        body,
        title=f"📋  {title}",
        border_style="blue",
        box=box.ROUNDED,
        padding=(1, 2),
    ))


def slugify(text):
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
    return s.strip("_")[:40] or "meeting"


def save_summary(title, sections):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    slug = slugify(title or "meeting")
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"summary_{slug}_{ts}.txt")

    lines = [
        (title or "Meeting Summary").upper(),
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 50,
        "",
    ]
    for key in SECTION_ORDER:
        lines.append(SECTION_TITLES[key].upper())
        lines.append(sections[key])
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    return path


def main():
    banner()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    console.print(f"  [dim]Summaries are saved as plain text to {OUTPUT_DIR}[/dim]\n")

    while True:
        title = Prompt.ask("  [bold]Meeting / call title[/bold] [dim](optional — used for the file name)[/dim]").strip()
        console.print()
        transcript = get_transcript()

        if not transcript or not transcript.strip():
            console.print("\n  [yellow]Nothing to summarize — let's try again.[/yellow]\n")
            continue

        if len(transcript) > MAX_CHARS:
            console.print(f"\n  [dim]Transcript is long — using the first ~{MAX_CHARS:,} characters.[/dim]")
            transcript = transcript[:MAX_CHARS]

        console.print()
        with console.status(f"  {random.choice(THINKING_MSGS)}", spinner="dots12"):
            try:
                sections = generate_summary(transcript)
            except Exception as e:
                console.print(f"  [bold red]✗ AI failed to summarize: {e}[/bold red]\n")
                continue

        console.print()
        render_summary(sections, title or "Meeting Summary")

        console.print()
        if Prompt.ask("  Save this summary?", choices=["y", "n"], default="y") == "y":
            path = save_summary(title, sections)
            console.print()
            console.print(Panel(
                f"[bold green]✓ Saved![/bold green]\n\n"
                f"File: [cyan]{path}[/cyan]\n\n"
                f"[dim]Open it in any text editor, paste it into an email,\n"
                f"or share the file directly with your team.[/dim]",
                title="📋  Done", border_style="green", box=box.ROUNDED, padding=(1, 2),
            ))
            if Prompt.ask("\n  Open the folder with your summaries?", choices=["y", "n"], default="y") == "y":
                subprocess.run(["open", OUTPUT_DIR])

        console.print()
        if Prompt.ask("  Summarize another transcript?", choices=["y", "n"], default="y") == "n":
            break

    console.print()
    console.print(Panel(Align.center(Text("See you next time! 📋", style="bold blue")), border_style="blue", box=box.ROUNDED))
    console.print()


if __name__ == "__main__":
    check_update()
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n  [dim]Goodbye![/dim]\n")
    except Exception as e:
        console.print(f"\n  [bold red]Unexpected error: {e}[/bold red]\n")
