#!/usr/bin/env python3
import os, sys, re, subprocess, shutil, time, random, urllib.request
from datetime import datetime

import ollama
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.align import Align
from rich import box

VERSION     = "1.0.0"
VERSION_URL = "https://raw.githubusercontent.com/veldan123/ai-agent/main/model_gen/version.txt"
APP_URL     = "https://raw.githubusercontent.com/veldan123/ai-agent/main/model_gen/agent.py"
APP_PATH    = os.path.expanduser("~/model_gen/agent.py")

MODEL        = "gemma3:4b"
console      = Console()
OUTPUT_DIR   = os.path.expanduser("~/3d_models")
MAX_ATTEMPTS = 4

OPENSCAD_PATHS = [
    "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
    "/opt/homebrew/bin/openscad",
    "/usr/local/bin/openscad",
]


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


def find_openscad():
    found = shutil.which("openscad")
    if found:
        return found
    for path in OPENSCAD_PATHS:
        if os.path.isfile(path):
            return path
    return None


# ── Boot / banner ──
def boot_sequence():
    steps = [
        "linking local AI engine (gemma3:4b)",
        "locating OpenSCAD render engine",
        "preparing model workspace",
    ]
    for step in steps:
        with console.status(f"[dim cyan]{step}...[/dim cyan]", spinner="dots12"):
            time.sleep(random.uniform(0.35, 0.6))
        console.print(f"  [dim cyan]›[/dim cyan] [dim]{step}[/dim] [bold green]done[/bold green]")
    console.print("  [bold green]✓ all systems online[/bold green]")
    time.sleep(0.3)
    console.print()


def banner():
    console.clear()
    console.print()
    boot_sequence()
    console.print(Panel(
        Align.center(Text("🧊  3D Model Generator", style="bold cyan")),
        subtitle="Describe an object — AI designs it and exports a ready-to-print STL",
        box=box.DOUBLE,
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print()


# ── AI code generation ──
def strip_code_fences(text):
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def build_prompt(description, previous_code=None, error=None):
    if previous_code and error:
        return f"""The following OpenSCAD code failed to render:

{previous_code}

OpenSCAD reported this error:
{error[:600]}

Fix the code so it renders successfully, keeping the same design intent
("{description}"). Output ONLY the corrected OpenSCAD code — no explanations,
no markdown code fences, just raw code starting from the first line."""

    return f"""You are an expert OpenSCAD programmer. Write OpenSCAD code for this object:

"{description}"

You may ONLY use these OpenSCAD features:
- Primitives: cube(), cylinder(), sphere(), polygon(), polyhedron()
- Transforms: translate(), rotate(), scale(), mirror(), resize()
- Booleans: union(), difference(), intersection()
- Extrusions: linear_extrude(), rotate_extrude()
- $fn for facet smoothness on curves

Rules:
1. All dimensions in millimeters, sized realistically for a real-world object
   of this kind (e.g. a coffee mug is roughly 80mm tall, a phone stand 100mm wide)
2. Keep the model centered near the origin
3. Use difference() to cut holes, cavities, and cutouts
4. Set $fn = 64; near the top so curved surfaces render smoothly
5. Add short // comments explaining each part
6. Output ONLY valid OpenSCAD code — no explanations, no markdown fences,
   just the raw code starting from the first line"""


def generate_scad_code(description, previous_code=None, error=None):
    prompt = build_prompt(description, previous_code, error)
    resp = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
    return strip_code_fences(resp["message"]["content"])


# ── Rendering ──
def render_to_stl(openscad_bin, scad_path, stl_path):
    try:
        result = subprocess.run(
            [openscad_bin, "-o", stl_path, scad_path],
            capture_output=True, text=True, timeout=180,
        )
        ok = (
            result.returncode == 0
            and os.path.isfile(stl_path)
            and os.path.getsize(stl_path) > 0
        )
        log = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
        return ok, log
    except subprocess.TimeoutExpired:
        return False, "Rendering timed out — the design may be too complex. Try describing something simpler."
    except Exception as e:
        return False, str(e)


def slugify(text):
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
    return s.strip("_")[:40] or "model"


THINKING_MSGS = [
    "[cyan]⚡ sketching the design...[/cyan]",
    "[cyan]⚡ working out dimensions & geometry...[/cyan]",
    "[cyan]⚡ writing CAD code...[/cyan]",
    "[cyan]⚡ assembling the model...[/cyan]",
]
FIXING_MSGS = [
    "[yellow]⚡ debugging the render error...[/yellow]",
    "[yellow]⚡ rewriting the geometry...[/yellow]",
    "[yellow]⚡ patching the design...[/yellow]",
]


def make_model(description, openscad_bin):
    previous_code, error = None, None
    slug = slugify(description)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    scad_path = os.path.join(OUTPUT_DIR, f"{slug}_{ts}.scad")
    stl_path  = os.path.join(OUTPUT_DIR, f"{slug}_{ts}.stl")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        msg = random.choice(THINKING_MSGS if attempt == 1 else FIXING_MSGS)
        label = f"  {msg}" if attempt == 1 else f"  {msg} [dim](attempt {attempt}/{MAX_ATTEMPTS})[/dim]"
        with console.status(label, spinner="dots12"):
            try:
                code = generate_scad_code(description, previous_code, error)
            except Exception as e:
                return False, None, None, f"AI failed to generate code: {e}"

            with open(scad_path, "w", encoding="utf-8") as f:
                f.write(code)

            ok, log = render_to_stl(openscad_bin, scad_path, stl_path)

        if ok:
            return True, scad_path, stl_path, code

        previous_code, error = code, log
        console.print(f"  [yellow]✗ Attempt {attempt} didn't render cleanly — asking the AI to fix it...[/yellow]")

    return False, scad_path, None, error


def main():
    banner()

    openscad_bin = find_openscad()
    if not openscad_bin:
        console.print(Panel(
            "[bold red]OpenSCAD wasn't found on this Mac.[/bold red]\n\n"
            "It's the free engine that turns the AI's design code into an STL file.\n"
            "Install it with:\n\n"
            "  [cyan]brew install --cask openscad[/cyan]\n\n"
            "...then run this tool again.",
            border_style="red", box=box.ROUNDED, padding=(1, 2),
        ))
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    console.print(f"  [dim]Models are saved to {OUTPUT_DIR}[/dim]\n")

    while True:
        description = Prompt.ask(
            "  [bold]Describe the 3D object you want[/bold]\n"
            "  [dim]e.g. \"a phone stand angled at 60 degrees\" or \"a hexagonal pen holder, 9cm tall\"[/dim]\n  "
        ).strip()
        if not description:
            continue

        console.print()
        ok, scad_path, stl_path, result = make_model(description, openscad_bin)

        if ok:
            console.print()
            console.print(Panel(
                f"[bold green]✓ Model ready![/bold green]\n\n"
                f"STL file:    [cyan]{stl_path}[/cyan]\n"
                f"Source code: [dim]{scad_path}[/dim]\n\n"
                f"[dim]Open the .stl in any slicer (Cura, PrusaSlicer, Bambu Studio) to print it,\n"
                f"or the .scad in OpenSCAD to view & tweak the design.[/dim]",
                title="🧊  Done", border_style="green", box=box.ROUNDED, padding=(1, 2),
            ))
            if Prompt.ask("\n  Open the folder with your model?", choices=["y", "n"], default="y") == "y":
                subprocess.run(["open", OUTPUT_DIR])
        else:
            console.print()
            console.print(Panel(
                f"[bold red]✗ Couldn't get this one to render after {MAX_ATTEMPTS} attempts.[/bold red]\n\n"
                f"[dim]Last error:[/dim]\n{(result or '')[:400]}\n\n"
                f"[dim]Tip: try describing the object more simply — fewer features,\n"
                f"clearer shapes (e.g. \"a simple rectangular box with a lid\").[/dim]"
                + (f"\n\n[dim]Draft source saved to: {scad_path}[/dim]" if scad_path else ""),
                title="Render failed", border_style="red", box=box.ROUNDED, padding=(1, 2),
            ))

        console.print()
        if Prompt.ask("  Make another model?", choices=["y", "n"], default="y") == "n":
            break

    console.print()
    console.print(Panel(Align.center(Text("See you next time! 🧊", style="bold cyan")), border_style="cyan", box=box.ROUNDED))
    console.print()


if __name__ == "__main__":
    check_update()
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n  [dim]Goodbye![/dim]\n")
    except Exception as e:
        console.print(f"\n  [bold red]Unexpected error: {e}[/bold red]\n")
