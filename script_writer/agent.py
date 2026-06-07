#!/usr/bin/env python3
import os, sys, re, time, random, subprocess, tempfile, shutil, urllib.request
from datetime import datetime

import ollama
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.align import Align
from rich.syntax import Syntax
from rich import box

VERSION     = "1.0.0"
VERSION_URL = "https://raw.githubusercontent.com/veldan123/ai-agent/main/script_writer/version.txt"
APP_URL     = "https://raw.githubusercontent.com/veldan123/ai-agent/main/script_writer/agent.py"
APP_PATH    = os.path.expanduser("~/script_writer/agent.py")

MODEL        = "gemma3:4b"
console      = Console()
OUTPUT_DIR   = os.path.expanduser("~/scripts")
MAX_ATTEMPTS = 3

LANGUAGES = {
    "1": {"name": "Python",            "ext": "py", "lexer": "python",     "shebang": "#!/usr/bin/env python3", "executable": True},
    "2": {"name": "Bash / Shell",      "ext": "sh", "lexer": "bash",       "shebang": "#!/bin/bash",            "executable": True},
    "3": {"name": "JavaScript (Node)", "ext": "js", "lexer": "javascript", "shebang": None,                     "executable": False},
}


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
        "loading language toolchains",
        "preparing script workspace",
    ]
    for step in steps:
        with console.status(f"[dim magenta]{step}...[/dim magenta]", spinner="dots12"):
            time.sleep(random.uniform(0.35, 0.6))
        console.print(f"  [dim magenta]›[/dim magenta] [dim]{step}[/dim] [bold green]done[/bold green]")
    console.print("  [bold green]✓ all systems online[/bold green]")
    time.sleep(0.3)
    console.print()


def banner():
    console.clear()
    console.print()
    boot_sequence()
    console.print(Panel(
        Align.center(Text("💻  AI Script Writer by Anvil AI", style="bold magenta")),
        subtitle="Describe what you want automated — AI writes the script and saves it",
        box=box.DOUBLE,
        border_style="magenta",
        padding=(1, 4),
    ))
    console.print()


# ── Getting the request ──
def get_request():
    description = Prompt.ask(
        "  [bold]What should the script do?[/bold]\n"
        "  [dim]e.g. \"rename every file in a folder to lowercase\" or\n"
        "  \"fetch a webpage and save its text to a file\"[/dim]\n  "
    ).strip()

    console.print()
    console.print("  [bold]Which language?[/bold]")
    for key, lang in LANGUAGES.items():
        console.print(f"    [magenta]{key}.[/magenta] {lang['name']}")
    console.print()
    choice = Prompt.ask("  Pick one", choices=list(LANGUAGES.keys()), default="1")
    console.print()
    return description, LANGUAGES[choice]


# ── AI code generation ──
def strip_code_fences(text):
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def build_prompt(description, lang, previous_code=None, error=None):
    if previous_code and error:
        return f"""The following {lang['name']} script failed a syntax check:

{previous_code}

The checker reported this error:
{error[:600]}

Fix the script so it's syntactically valid, keeping the same goal
("{description}"). Output ONLY the corrected {lang['name']} code — no
explanations, no markdown code fences, just the raw code starting from
the first line."""

    return f"""You are an expert {lang['name']} programmer. Write a complete, working
{lang['name']} script that does the following:

"{description}"

Rules:
1. The script must be complete and ready to run as-is — no placeholders,
   no "TODO", no "insert your code here"
2. Use only the standard library / built-in modules unless the task
   clearly requires something else
3. Add short comments explaining the key steps
4. Briefly handle the obvious edge cases (missing files, bad input) —
   don't over-engineer it
5. Output ONLY the raw {lang['name']} code — no explanations, no markdown
   code fences, just the code starting from the first line"""


def build_revision_prompt(lang, current_code, feedback):
    return f"""Here is a {lang['name']} script:

{current_code}

The user wants this change: "{feedback}"

Rewrite the script to make that change while keeping everything else
working. Output ONLY the updated {lang['name']} code — no explanations,
no markdown code fences, just the raw code starting from the first line."""


def ask_ai(prompt):
    resp = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
    return strip_code_fences(resp["message"]["content"])


# ── Syntax checking (no execution — just validates the code parses) ──
def check_syntax(code, lang):
    fd, path = tempfile.mkstemp(suffix=f".{lang['ext']}")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)

        if lang["ext"] == "py":
            cmd = [sys.executable, "-c",
                   "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read())", path]
        elif lang["ext"] == "sh":
            cmd = ["bash", "-n", path]
        elif lang["ext"] == "js":
            if not shutil.which("node"):
                return True, ""  # Node isn't installed — skip the check rather than block saving
            cmd = ["node", "--check", path]
        else:
            return True, ""

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        ok = result.returncode == 0
        log = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
        return ok, log
    except Exception as e:
        return True, str(e)  # don't let a missing checker block the workflow
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ── Self-correcting generation loop ──
THINKING_MSGS = [
    "[magenta]⚡ planning the script...[/magenta]",
    "[magenta]⚡ writing the code...[/magenta]",
    "[magenta]⚡ wiring up the logic...[/magenta]",
    "[magenta]⚡ putting the pieces together...[/magenta]",
]
FIXING_MSGS = [
    "[yellow]⚡ reading the syntax error...[/yellow]",
    "[yellow]⚡ patching the script...[/yellow]",
    "[yellow]⚡ rewriting the broken part...[/yellow]",
]
REVISING_MSGS = [
    "[magenta]⚡ applying your changes...[/magenta]",
    "[magenta]⚡ rewriting with your feedback...[/magenta]",
    "[magenta]⚡ updating the script...[/magenta]",
]


def write_script(description, lang):
    previous_code, error, code = None, None, None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        msg = random.choice(THINKING_MSGS if attempt == 1 else FIXING_MSGS)
        label = f"  {msg}" if attempt == 1 else f"  {msg} [dim](attempt {attempt}/{MAX_ATTEMPTS})[/dim]"
        with console.status(label, spinner="dots12"):
            try:
                prompt = build_prompt(description, lang, previous_code, error)
                code = ask_ai(prompt)
            except Exception as e:
                return False, None, f"AI failed to generate code: {e}"

            ok, log = check_syntax(code, lang)

        if ok:
            return True, code, None

        previous_code, error = code, log
        console.print(f"  [yellow]✗ Attempt {attempt} had a syntax issue — asking the AI to fix it...[/yellow]")

    return False, code, error


# ── Display & save ──
def render_code(code, lang, description):
    syntax = Syntax(code, lang["lexer"], theme="monokai", line_numbers=True,
                    word_wrap=True, background_color="default")
    console.print(Panel(
        syntax,
        title=f"💻  {description[:56]}{'…' if len(description) > 56 else ''}",
        subtitle=f"[dim]{lang['name']}[/dim]",
        border_style="magenta",
        box=box.ROUNDED,
        padding=(1, 1),
    ))


def slugify(text):
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
    return s.strip("_")[:40] or "script"


def save_script(description, lang, code):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    slug = slugify(description)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"{slug}_{ts}.{lang['ext']}")

    text = code.strip()
    if lang["shebang"] and not text.startswith("#!"):
        text = lang["shebang"] + "\n" + text

    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")

    if lang["executable"]:
        os.chmod(path, 0o755)

    return path


def main():
    banner()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    console.print(f"  [dim]Scripts are saved as ready-to-run files to {OUTPUT_DIR}[/dim]")
    console.print("  [dim]Python & Bash scripts are saved executable — just double-click or run them.[/dim]\n")

    while True:
        description, lang = get_request()
        if not description:
            continue

        ok, code, error = write_script(description, lang)
        if code is None:
            console.print(f"  [bold red]✗ {error}[/bold red]\n")
            continue

        while True:
            console.print()
            render_code(code, lang, description)
            if not ok:
                console.print(Panel(
                    f"[yellow]⚠ This script may still have a syntax issue after {MAX_ATTEMPTS} attempts:[/yellow]\n"
                    f"[dim]{(error or '')[:300]}[/dim]\n\n"
                    f"[dim]You can save it anyway and fix it by hand, tweak it with feedback,\n"
                    f"or regenerate from scratch.[/dim]",
                    border_style="yellow", box=box.ROUNDED, padding=(1, 2),
                ))
            console.print(
                "  [bold green][A][/bold green]pprove & save   "
                "[bold cyan][T][/bold cyan]weak it   "
                "[bold yellow][R][/bold yellow]egenerate   "
                "[bold red][Q][/bold red]uit"
            )
            action = console.input("  > ").strip().lower()

            if action in ("a", "approve", ""):
                path = save_script(description, lang, code)
                console.print()
                console.print(Panel(
                    f"[bold green]✓ Saved![/bold green]\n\n"
                    f"File: [cyan]{path}[/cyan]\n\n"
                    f"[dim]Open it in any text editor, or run it straight from the\n"
                    f"terminal{' — it’s already executable' if lang['executable'] else ''}.[/dim]",
                    title="💻  Done", border_style="green", box=box.ROUNDED, padding=(1, 2),
                ))
                if Prompt.ask("\n  Open the folder with your scripts?", choices=["y", "n"], default="y") == "y":
                    subprocess.run(["open", OUTPUT_DIR])
                break

            elif action in ("t", "tweak"):
                feedback = Prompt.ask(
                    "  [bold]What should change?[/bold]\n"
                    "  [dim]e.g. \"add error handling\" or \"also print progress as it runs\"[/dim]\n  "
                ).strip()
                if not feedback:
                    continue
                with console.status(f"  {random.choice(REVISING_MSGS)}", spinner="dots12"):
                    try:
                        new_code = ask_ai(build_revision_prompt(lang, code, feedback))
                        ok, error = check_syntax(new_code, lang)
                        code = new_code
                    except Exception as e:
                        console.print(f"  [bold red]✗ AI failed to revise the script: {e}[/bold red]")
                continue

            elif action in ("r", "regenerate"):
                ok, code, error = write_script(description, lang)
                continue

            elif action in ("q", "quit"):
                console.print("\n  [dim]Discarded — nothing was saved.[/dim]\n")
                return

            else:
                console.print("  [dim]Type A, T, R, or Q[/dim]")

        console.print()
        if Prompt.ask("  Write another script?", choices=["y", "n"], default="y") == "n":
            break

    console.print()
    console.print(Panel(Align.center(Text("See you next time! 💻", style="bold magenta")), border_style="magenta", box=box.ROUNDED))
    console.print()


if __name__ == "__main__":
    check_update()
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n  [dim]Goodbye![/dim]\n")
    except Exception as e:
        console.print(f"\n  [bold red]Unexpected error: {e}[/bold red]\n")
