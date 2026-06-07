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
VERSION_URL = "https://raw.githubusercontent.com/veldan123/ai-agent/main/proposal_writer/version.txt"
APP_URL     = "https://raw.githubusercontent.com/veldan123/ai-agent/main/proposal_writer/agent.py"
APP_PATH    = os.path.expanduser("~/proposal_writer/agent.py")

MODEL      = "gemma3:4b"
console    = Console()
OUTPUT_DIR = os.path.expanduser("~/proposals")


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
        "loading proposal & quote templates",
        "preparing document workspace",
    ]
    for step in steps:
        with console.status(f"[dim yellow]{step}...[/dim yellow]", spinner="dots12"):
            time.sleep(random.uniform(0.35, 0.6))
        console.print(f"  [dim yellow]›[/dim yellow] [dim]{step}[/dim] [bold green]done[/bold green]")
    console.print("  [bold green]✓ all systems online[/bold green]")
    time.sleep(0.3)
    console.print()


def banner():
    console.clear()
    console.print()
    boot_sequence()
    console.print(Panel(
        Align.center(Text("🧾  Proposal & Quote Writer by Anvil AI", style="bold yellow")),
        subtitle="Describe the job — AI drafts a client-ready proposal in seconds",
        box=box.DOUBLE,
        border_style="yellow",
        padding=(1, 4),
    ))
    console.print()


# ── AI drafting ──
THINKING_MSGS = [
    "[yellow]⚡ studying the project details...[/yellow]",
    "[yellow]⚡ structuring the proposal...[/yellow]",
    "[yellow]⚡ drafting scope & pricing...[/yellow]",
    "[yellow]⚡ polishing the language...[/yellow]",
]
REVISING_MSGS = [
    "[cyan]⚡ applying your changes...[/cyan]",
    "[cyan]⚡ rewriting with the new direction...[/cyan]",
    "[cyan]⚡ revising the draft...[/cyan]",
]


def build_prompt(sender_name, profession, client_name, description, pricing, timeline):
    pricing_line  = pricing if pricing else "not specified — suggest a fair, realistic price for this kind of work"
    timeline_line = timeline if timeline else "not specified — suggest a realistic timeline"

    return f"""Write a professional, client-ready project proposal / quote.

From (sender):       {sender_name} — {profession}
To (client):         {client_name}
Project description: {description}
Pricing:             {pricing_line}
Timeline:            {timeline_line}

Structure it with these clearly-labeled sections:
1. Opening — a brief, warm line that shows you understand exactly what they need
2. Scope of Work — bullet points of what's included
3. Timeline — a realistic estimate
4. Investment — the price, stated plainly and confidently
5. Next Steps — one simple, low-pressure call to action

Rules:
- Sound professional but human — no corporate buzzwords, no "I hope this email finds you well"
- Be specific to THIS project, not generic filler
- Around 200-320 words total
- PLAIN TEXT ONLY — do not use markdown like **bold**, *italics*, # headers,
  or bullet characters like * or -. For section titles just write the title
  on its own line followed by a colon (e.g. "Scope of Work:"). For lists,
  start each line with a dash-free format like "•" or simply a new line
- Do not include a "Subject:" line — this is a document, not an email
- Output ONLY the proposal text — no explanations, no commentary,
  just the document starting from the opening line"""


def build_revision_prompt(previous, feedback):
    return f"""Here is a draft proposal:

{previous}

The client/sender wants this change applied: "{feedback}"

Rewrite the FULL proposal with that change applied. Keep the same structure,
sender, client, project facts, and overall tone unless the requested change
says otherwise. Output ONLY the revised proposal text — no explanations,
no markdown, no commentary, just the document starting from the opening line."""


def clean_markdown(text):
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)       # # headers
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)                  # **bold**
    text = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", text)         # *italics*
    text = re.sub(r"^[ \t]*[-*]\s+", "• ", text, flags=re.MULTILINE)  # - / * bullets → •
    text = re.sub(r"^Subject:.*\n+", "", text, flags=re.IGNORECASE)
    return text.strip()


def generate_proposal(sender_name, profession, client_name, description, pricing, timeline):
    prompt = build_prompt(sender_name, profession, client_name, description, pricing, timeline)
    resp = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
    return clean_markdown(resp["message"]["content"].strip())


def revise_proposal(previous, feedback):
    prompt = build_revision_prompt(previous, feedback)
    resp = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
    return clean_markdown(resp["message"]["content"].strip())


# ── Saving ──
def slugify(text):
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
    return s.strip("_")[:40] or "client"


def save_proposal(client_name, text):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    slug = slugify(client_name)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"proposal_{slug}_{ts}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def main():
    banner()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    console.print(f"  [dim]Proposals are saved as plain text to {OUTPUT_DIR}[/dim]")
    console.print("  [dim]Copy them into an email, a doc, or send the file as-is.[/dim]\n")

    while True:
        sender_name = Prompt.ask("  [bold]Your name or business name[/bold]").strip()
        profession  = Prompt.ask(
            "  [bold]Your profession / service[/bold]\n"
            "  [dim]e.g. \"freelance web designer\" or \"home cleaning service\"[/dim]\n  "
        ).strip()
        client_name = Prompt.ask("  [bold]Client's name or business[/bold]").strip()
        description = Prompt.ask(
            "  [bold]What does the client need?[/bold]\n"
            "  [dim]e.g. \"a 5-page marketing website with a contact form\"[/dim]\n  "
        ).strip()
        pricing = Prompt.ask(
            "  [bold]Your price or rate for this[/bold] [dim](leave blank — AI will suggest one)[/dim]"
        ).strip()
        timeline = Prompt.ask(
            "  [bold]Timeline or deadline[/bold] [dim](leave blank — AI will suggest one)[/dim]"
        ).strip()

        console.print()
        with console.status(f"  {random.choice(THINKING_MSGS)}", spinner="dots12"):
            try:
                draft = generate_proposal(sender_name, profession, client_name, description, pricing, timeline)
            except Exception as e:
                console.print(f"  [bold red]✗ AI failed to generate a draft: {e}[/bold red]\n")
                continue

        while True:
            console.print()
            console.print(Panel(
                draft,
                title=f"🧾  Proposal for {client_name}",
                border_style="yellow",
                box=box.ROUNDED,
                padding=(1, 2),
            ))
            console.print(
                "  [bold green][A][/bold green]pprove & save   "
                "[bold cyan][T][/bold cyan]weak it   "
                "[bold yellow][R][/bold yellow]egenerate   "
                "[bold red][Q][/bold red]uit"
            )
            action = console.input("  > ").strip().lower()

            if action in ("a", "approve", ""):
                path = save_proposal(client_name, draft)
                console.print()
                console.print(Panel(
                    f"[bold green]✓ Saved![/bold green]\n\n"
                    f"File: [cyan]{path}[/cyan]\n\n"
                    f"[dim]Open it in any text editor, paste it into an email,\n"
                    f"or attach the file directly.[/dim]",
                    title="🧾  Done", border_style="green", box=box.ROUNDED, padding=(1, 2),
                ))
                if Prompt.ask("\n  Open the folder with your proposal?", choices=["y", "n"], default="y") == "y":
                    subprocess.run(["open", OUTPUT_DIR])
                break

            elif action in ("t", "tweak"):
                feedback = Prompt.ask(
                    "  [bold]What should change?[/bold]\n"
                    "  [dim]e.g. \"make it shorter\" or \"raise the price to $800\" or \"sound more casual\"[/dim]\n  "
                ).strip()
                if not feedback:
                    continue
                with console.status(f"  {random.choice(REVISING_MSGS)}", spinner="dots12"):
                    try:
                        draft = revise_proposal(draft, feedback)
                    except Exception as e:
                        console.print(f"  [bold red]✗ AI failed to revise the draft: {e}[/bold red]")
                continue

            elif action in ("r", "regenerate"):
                with console.status(f"  {random.choice(THINKING_MSGS)}", spinner="dots12"):
                    try:
                        draft = generate_proposal(sender_name, profession, client_name, description, pricing, timeline)
                    except Exception as e:
                        console.print(f"  [bold red]✗ AI failed to generate a draft: {e}[/bold red]")
                continue

            elif action in ("q", "quit"):
                console.print("\n  [dim]Discarded — nothing was saved.[/dim]\n")
                return

            else:
                console.print("  [dim]Type A, T, R, or Q[/dim]")

        console.print()
        if Prompt.ask("  Write another proposal?", choices=["y", "n"], default="y") == "n":
            break

    console.print()
    console.print(Panel(Align.center(Text("See you next time! 🧾", style="bold yellow")), border_style="yellow", box=box.ROUNDED))
    console.print()


if __name__ == "__main__":
    check_update()
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n  [dim]Goodbye![/dim]\n")
    except Exception as e:
        console.print(f"\n  [bold red]Unexpected error: {e}[/bold red]\n")
