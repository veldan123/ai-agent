#!/usr/bin/env python3
"""
Client Finder Agent — finds potential clients for your business.
Beautiful terminal UI with animations. Runs locally via Ollama. No API key needed.
"""

import re
import json
import time
import warnings
import urllib.parse
import requests as req
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")
import ollama

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import (
    Progress, SpinnerColumn, BarColumn,
    TextColumn, TimeRemainingColumn, TaskProgressColumn, MofNCompleteColumn
)
from rich.live import Live
from rich.align import Align
from rich import box

console = Console()
MODEL = "qwen2.5:7b"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


# ── Welcome screen ────────────────────────────────────────────────────────────

def show_welcome():
    console.clear()
    time.sleep(0.3)

    title = Text()
    title.append("\n")
    title.append("  ██████╗██╗     ██╗███████╗███╗   ██╗████████╗\n", style="bold cyan")
    title.append("  ██╔════╝██║     ██║██╔════╝████╗  ██║╚══██╔══╝\n", style="bold cyan")
    title.append("  ██║     ██║     ██║█████╗  ██╔██╗ ██║   ██║   \n", style="bold blue")
    title.append("  ██║     ██║     ██║██╔══╝  ██║╚██╗██║   ██║   \n", style="bold blue")
    title.append("  ╚██████╗███████╗██║███████╗██║ ╚████║   ██║   \n", style="bold magenta")
    title.append("   ╚═════╝╚══════╝╚═╝╚══════╝╚═╝  ╚═══╝   ╚═╝  \n", style="bold magenta")
    title.append("\n")
    title.append("        F I N D E R   A G E N T\n", style="bold white")
    title.append("\n")

    panel = Panel(
        Align.center(title),
        subtitle="[dim]AI-powered lead generation • Powered by Ollama • Free[/dim]",
        border_style="cyan",
        box=box.DOUBLE_EDGE,
        padding=(0, 4),
    )
    console.print(panel)
    time.sleep(0.4)

    # Animated startup dots
    with Progress(
        SpinnerColumn("dots2"),
        TextColumn("[cyan]Initialising agent..."),
        transient=True,
    ) as p:
        p.add_task("", total=None)
        time.sleep(1.8)

    console.print()


# ── AI call with spinner ──────────────────────────────────────────────────────

def ai_call(messages: list, temperature: float = 0.3) -> str:
    """Call Ollama and show a spinner while waiting. Returns content string."""
    with Progress(
        SpinnerColumn("dots"),
        TextColumn("[cyan]AI is thinking..."),
        transient=True,
    ) as p:
        p.add_task("", total=None)
        resp = ollama.chat(model=MODEL, messages=messages,
                           options={"temperature": temperature})
    return resp.message.content.strip()


# ── Step 1: Understand the user's business ────────────────────────────────────

def understand_business(raw: str) -> dict:
    history = [
        {
            "role": "system",
            "content": (
                "You help identify someone's business and location to find them potential clients. "
                "Ask short questions one at a time to find out: (1) what they do, (2) where they are. "
                "Once you know both, output ONLY this exact JSON:\n"
                '{"profession": "...", "location": "...", "specialty": "..."}\n'
                "specialty = specific niche (e.g. wedding, sports, commercial). Use 'general' if unknown."
            ),
        },
        {"role": "user", "content": raw},
    ]

    for _ in range(4):
        reply = ai_call(history)
        history.append({"role": "assistant", "content": reply})

        m = re.search(r'\{[^{}]+\}', reply, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group())
                if "profession" in data and "location" in data:
                    console.print()
                    console.print(Panel(
                        f"[bold green]✓[/bold green]  {data.get('specialty','').title()} "
                        f"[cyan]{data['profession']}[/cyan] in [cyan]{data['location']}[/cyan]",
                        title="[bold]Understood[/bold]",
                        border_style="green",
                        padding=(0, 2),
                    ))
                    time.sleep(0.5)
                    return data
            except json.JSONDecodeError:
                pass

        console.print(f"\n  [bold cyan]●[/bold cyan] {reply}")
        answer = console.input("  [bold]You:[/bold] ").strip()
        if not answer:
            break
        history.append({"role": "user", "content": answer})

    return {"profession": raw, "location": "unknown", "specialty": "general"}


# ── Step 2: Brainstorm client types ──────────────────────────────────────────

def brainstorm_clients(profession: str, location: str, specialty: str) -> list:
    prompt = f"""I am a {specialty} {profession} based in {location}.
Who are the types of businesses that would HIRE me? Not other {profession}s — businesses that NEED my services.
Give 10 specific potential client types for a {specialty} {profession} in {location}.
Output ONLY a JSON array of short strings (3-6 words):
["client type 1", "client type 2", ...]"""

    reply = ai_call([{"role": "user", "content": prompt}], temperature=0.7)
    m = re.search(r'\[.*?\]', reply, re.DOTALL)
    if m:
        try:
            clients = json.loads(m.group())
            if isinstance(clients, list) and clients:
                return [str(c) for c in clients[:10]]
        except json.JSONDecodeError:
            pass

    fallbacks = {
        "photographer": ["wedding planners", "event venues", "real estate agents",
                         "restaurants and cafes", "bridal boutiques", "hotels",
                         "corporate event companies", "florists", "catering companies", "sports clubs"],
    }
    for key, val in fallbacks.items():
        if key in profession.lower():
            return val
    return ["local businesses", "event companies", "marketing agencies",
            "hotels", "restaurants", "corporate companies", "schools",
            "retail stores", "fitness studios", "law firms"]


# ── Step 3: Interactive client type selection ─────────────────────────────────

def select_client_types(client_types: list) -> list:
    selected = set(range(1, len(client_types) + 1))

    while True:
        console.print()
        console.print(Panel(
            "[bold]Select which client types to target[/bold]\n"
            "[dim]Type numbers to toggle on/off. Press Enter to confirm.[/dim]",
            border_style="blue", padding=(0, 2),
        ))
        console.print()

        for i, ct in enumerate(client_types, 1):
            if i in selected:
                console.print(f"    [bold green][ ✓ ] {i:>2}.[/bold green]  {ct}")
            else:
                console.print(f"    [dim][   ] {i:>2}.[/dim]  [dim]{ct}[/dim]")

        console.print()
        raw_sel = console.input(
            "  [bold]Toggle numbers [cyan](e.g. 1 3 5)[/cyan] or press [cyan]Enter[/cyan] to confirm:[/bold] "
        ).strip()

        if not raw_sel:
            break

        for n in re.findall(r'\d+', raw_sel):
            n = int(n)
            if 1 <= n <= len(client_types):
                selected.discard(n) if n in selected else selected.add(n)

    chosen = [client_types[i - 1] for i in sorted(selected)]
    if not chosen:
        console.print("[red]Nothing selected. Exiting.[/red]")
        raise SystemExit(1)
    return chosen


# ── Step 4: Choose website limit ──────────────────────────────────────────────

def choose_limit(num_types: int) -> int:
    console.print()
    options = [
        ("1", 25,  "~1 min",   "Quick"),
        ("2", 50,  "~2 mins",  "Normal"),
        ("3", 100, "~4 mins",  "Deep"),
        ("4", None, "",        "Custom"),
    ]

    console.print(Panel(
        "[bold]How many websites should I search?[/bold]\n"
        "[dim]More websites = more contacts, but takes longer.[/dim]",
        border_style="blue", padding=(0, 2),
    ))
    console.print()

    for key, n, est, label in options:
        if n:
            bar = "█" * (n // 10) + "░" * (10 - n // 10)
        else:
            bar = "░░░░░░░░░░"
        sites_str = f"{n} websites" if n else "your choice"
        est_str = f"  [dim]{est}[/dim]" if est else ""
        console.print(f"    [cyan][{key}][/cyan]  [bold]{label:7}[/bold]  {bar}  {sites_str}{est_str}")

    console.print()
    limit_map = {"1": 25, "2": 50, "3": 100}

    while True:
        choice = console.input("  [bold]Choose [cyan](1/2/3/4)[/cyan]:[/bold] ").strip()
        if choice in limit_map:
            site_limit = limit_map[choice]
            break
        elif choice == "4":
            raw = console.input("  [bold]Enter number:[/bold] ").strip()
            if raw.isdigit() and int(raw) > 0:
                site_limit = int(raw)
                break
            console.print("  [red]Please enter a valid number.[/red]")
        else:
            console.print("  [red]Please enter 1, 2, 3 or 4.[/red]")

    secs = site_limit * 3 + num_types * 3 * 2
    mins, s = divmod(secs, 60)
    est = f"{mins}m {s}s" if mins else f"{s}s"

    console.print()
    console.print(Panel(
        f"  Searching up to [bold cyan]{site_limit}[/bold cyan] websites\n"
        f"  Estimated time: [bold yellow]{est}[/bold yellow]",
        border_style="cyan", padding=(0, 2),
    ))
    time.sleep(0.6)
    return site_limit


# ── Email filter ──────────────────────────────────────────────────────────────

_SKIP_PREFIXES = {
    "noreply","no-reply","no_reply","donotreply","do-not-reply","mailer-daemon",
    "postmaster","webmaster","bounce","bounces","unsubscribe","spam","abuse",
    "root","daemon","notifications","notification","alert","alerts","newsletter",
    "wordpress","woocommerce","shopify","cdn","static","assets","example",
    "test","placeholder","dummy",
}
_SKIP_DOMAINS = {
    "example.com","test.com","domain.com","sentry.io","wixpress.com","wix.com",
    "squarespace.com","shopify.com","wordpress.com","googleapis.com","schema.org",
    "w3.org","mailchimp.com","sendgrid.net","mailgun.org","cloudflare.com",
}
_GOOD_PREFIXES = {
    "hello","hi","info","contact","enquiry","enquiries","booking","bookings",
    "hire","connect","reach","mail","studio","team","us",
}


def is_emailable(email: str) -> bool:
    if "@" not in email or "." not in email:
        return False
    prefix, domain = email.rsplit("@", 1)
    prefix, domain = prefix.lower().strip(), domain.lower().strip()
    parts = domain.split(".")
    if len(parts) < 2 or len(parts[-1]) < 2:
        return False
    if domain in _SKIP_DOMAINS:
        return False
    if prefix in _SKIP_PREFIXES or "/" in prefix or len(prefix) > 40:
        return False
    return True


def best_emails(emails: list, site_domain: str) -> list:
    emailable = [e for e in emails if is_emailable(e)]
    if not emailable:
        return []

    def score(e):
        prefix, domain = e.split("@")[0], e.split("@")[1]
        s = 0
        if site_domain and site_domain in domain:
            s += 10
        if prefix in _GOOD_PREFIXES:
            s += 5
        if any(domain.endswith(t) for t in [".sg",".com",".co",".net",".org"]):
            s += 2
        if any(p in domain for p in ["gmail","yahoo","hotmail","outlook"]):
            s += 1
        return s

    return sorted(emailable, key=score, reverse=True)[:2]


# ── Email extraction ──────────────────────────────────────────────────────────

def extract_emails(html: str, soup: BeautifulSoup) -> list:
    found = set()
    bad_ext = (".png",".jpg",".gif",".svg",".css",".js",".woff",".ico",".webp")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?")[0].strip().lower()
            if "@" in email:
                found.add(email)

    for e in re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", html):
        e = e.lower()
        if not any(e.endswith(x) for x in bad_ext):
            found.add(e)

    for o in re.findall(
        r"[a-zA-Z0-9._%+\-]+\s*(?:\[at\]|\(at\)|{at}|\bat\b)\s*[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        soup.get_text(" "), re.IGNORECASE
    ):
        fixed = re.sub(r"\s*(?:\[at\]|\(at\)|{at}|\bat\b)\s*", "@", o, flags=re.IGNORECASE).lower().strip()
        if "@" in fixed:
            found.add(fixed)

    return list(found)


def extract_phones(text: str) -> list:
    return list({p.strip() for p in re.findall(
        r"(?:\+?\d{1,3}[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}", text
    )})


def scrape_site(url: str) -> tuple:
    all_emails, all_phones = set(), set()
    base_m = re.match(r"https?://[^/]+", url)
    base = base_m.group() if base_m else None
    domain_m = re.search(r"https?://(?:www\.)?([^/\.]+\.[^/]+)", url)
    site_domain = domain_m.group(1) if domain_m else ""

    pages = [url]
    if base:
        for sub in ["/contact", "/contact-us", "/about", "/about-us", "/enquiry"]:
            pages.append(base + sub)

    for page_url in pages:
        try:
            resp = req.get(page_url, headers=HEADERS, timeout=8, allow_redirects=True)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                all_emails.update(extract_emails(resp.text, soup))
                all_phones.update(extract_phones(soup.get_text(" ")))
        except Exception:
            pass

    return best_emails(list(all_emails), site_domain), list(all_phones)


# ── Search backend ────────────────────────────────────────────────────────────

def search_startpage(query: str, num: int = 20) -> list:
    try:
        resp = req.get(
            "https://www.startpage.com/sp/search",
            params={"query": query, "language": "english"},
            headers=HEADERS, timeout=15,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        urls, seen = [], set()
        for a in soup.select("a.result-link"):
            href = a.get("href", "")
            if href.startswith("http") and "startpage" not in href and href not in seen:
                seen.add(href)
                urls.append(href)
        return urls[:num]
    except Exception:
        return []


def build_queries(client_type: str, location: str, extra: str = "") -> list:
    extra_term = f' {extra}' if extra else ''
    return [
        f'{client_type} {location}{extra_term} email contact',
        f'{client_type} {location}{extra_term} "@gmail.com" OR "@yahoo.com"',
        f'{client_type} {location}{extra_term} "contact us" email',
    ]


# ── Main gather with progress bar ────────────────────────────────────────────

def gather_contacts(client_types: list, location: str, site_limit: int = 50, extra_context: str = "") -> list:
    all_urls, seen_urls = [], set()

    # Phase 1: collect URLs silently with spinner
    with Progress(
        SpinnerColumn("dots2"),
        TextColumn("[cyan]Collecting websites to scan..."),
        transient=True,
    ) as p:
        p.add_task("", total=None)
        for client_type in client_types:
            if len(all_urls) >= site_limit:
                break
            for query in build_queries(client_type, location, extra_context):
                for url in search_startpage(query):
                    if url not in seen_urls:
                        seen_urls.add(url)
                        all_urls.append((url, client_type))
                if len(all_urls) >= site_limit:
                    break
            time.sleep(0.5)

    all_urls = all_urls[:site_limit]

    if not all_urls:
        return []

    # Phase 2: scrape with animated progress bar
    seen_emails, seen_phones = set(), set()
    contacts = []

    console.print()
    with Progress(
        SpinnerColumn("dots"),
        TextColumn("[bold cyan]Scanning websites[/bold cyan]"),
        BarColumn(bar_width=35, complete_style="cyan", finished_style="green"),
        TaskProgressColumn(),
        TextColumn("•"),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("", total=len(all_urls))

        for url, client_type in all_urls:
            emails, phones = scrape_site(url)
            company_m = re.search(r"https?://(?:www\.)?([^/\.]+)", url)
            company = company_m.group(1).title() if company_m else None

            for email in emails:
                if email not in seen_emails:
                    seen_emails.add(email)
                    contacts.append({
                        "client_type": client_type,
                        "company": company,
                        "email": email,
                        "phone": phones[0] if phones else None,
                        "source": url,
                    })
            if not emails and phones:
                for ph in phones[:2]:
                    if ph not in seen_phones:
                        seen_phones.add(ph)
                        contacts.append({
                            "client_type": client_type, "company": company,
                            "email": None, "phone": ph, "source": url,
                        })

            progress.advance(task)

    return contacts


# ── Save & copy helpers ───────────────────────────────────────────────────────

import csv, io, subprocess, os
from datetime import datetime


def save_csv(contacts: list, profession: str, location: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^a-z0-9]+", "_", f"{profession}_{location}".lower())
    path = os.path.expanduser(f"~/contact_finder/results_{safe}_{ts}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["#","client_type","company","email","phone","source"])
        writer.writeheader()
        for i, c in enumerate(contacts, 1):
            writer.writerow({"#": i, **{k: c.get(k, "") for k in ["client_type","company","email","phone","source"]}})
    return path


def copy_to_clipboard(contacts: list):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["client_type","company","email","phone","source"])
    writer.writeheader()
    for c in contacts:
        writer.writerow({k: c.get(k, "") for k in ["client_type","company","email","phone","source"]})
    try:
        subprocess.run(["pbcopy"], input=buf.getvalue().encode(), check=True)
        return True
    except Exception:
        return False


# ── Results display ───────────────────────────────────────────────────────────

def trunc(s: str, n: int) -> str:
    return (s[:n - 1] + "…") if s and len(s) > n else (s or "–")


def display_results(contacts: list, profession: str, location: str):
    console.print()

    if not contacts:
        console.print(Panel(
            "[bold red]No contacts found.[/bold red]\n\n"
            "[dim]Try selecting more client types or increasing the website limit.[/dim]",
            border_style="red", padding=(1, 4),
        ))
        return

    # Animated reveal
    with Progress(
        SpinnerColumn("aesthetic"),
        TextColumn("[green]Processing results..."),
        transient=True,
    ) as p:
        p.add_task("", total=None)
        time.sleep(1.2)

    n_emails = sum(1 for c in contacts if c.get("email"))
    n_phones = sum(1 for c in contacts if c.get("phone"))

    console.print(Panel(
        f"  [bold green]✓  Found [cyan]{len(contacts)}[/cyan] potential clients![/bold green]\n"
        f"  [dim]{n_emails} emails  •  {n_phones} phone numbers[/dim]",
        border_style="green", padding=(0, 2),
    ))
    time.sleep(0.4)
    console.print()

    # ── Compact table (fits terminal) ─────────────────────────────────────────
    table = Table(
        title=f"Potential Clients — {profession.title()} in {location.title()}",
        header_style="bold cyan",
        border_style="dim",
        box=box.SIMPLE_HEAVY,
        show_lines=False,
        title_style="bold white",
        expand=False,
    )
    table.add_column("#",           style="dim",         width=4,  no_wrap=True)
    table.add_column("Client Type", style="bold yellow", width=22, no_wrap=True)
    table.add_column("Company",     style="white",       width=18, no_wrap=True)
    table.add_column("Email",       style="cyan",        width=30, no_wrap=True)
    table.add_column("Phone",       style="green",       width=15, no_wrap=True)
    table.add_column("Website",     style="dim",         width=25, no_wrap=True)

    for i, c in enumerate(contacts, 1):
        # Extract just the domain for the Website column
        src = c.get("source") or ""
        domain_m = re.search(r"https?://(?:www\.)?([^/]+)", src)
        domain = domain_m.group(1) if domain_m else src

        table.add_row(
            str(i),
            trunc(c.get("client_type") or "", 21),
            trunc(c.get("company") or "", 17),
            trunc(c.get("email") or "", 29),
            trunc(c.get("phone") or "", 14),
            trunc(domain, 24),
        )

    console.print(table)
    console.print()

    # ── Save CSV ──────────────────────────────────────────────────────────────
    with Progress(SpinnerColumn("dots"), TextColumn("[dim]Saving CSV..."), transient=True) as p:
        p.add_task("", total=None)
        csv_path = save_csv(contacts, profession, location)
        time.sleep(0.5)

    # ── Copy to clipboard ─────────────────────────────────────────────────────
    with Progress(SpinnerColumn("dots"), TextColumn("[dim]Copying to clipboard..."), transient=True) as p:
        p.add_task("", total=None)
        copied = copy_to_clipboard(contacts)
        time.sleep(0.4)

    # ── Summary panel ─────────────────────────────────────────────────────────
    clip_line = "[bold green]✓ Copied to clipboard[/bold green]" if copied else "[dim]Clipboard unavailable[/dim]"
    console.print(Panel(
        f"  [bold green]✓ Saved:[/bold green] [cyan]{csv_path}[/cyan]\n"
        f"  {clip_line}  [dim](paste into Excel or Google Sheets)[/dim]\n\n"
        f"  [bold]{len(contacts)} contacts[/bold]  •  [cyan]{n_emails} emails[/cyan]  •  [green]{n_phones} phones[/green]",
        title="[bold green]Done[/bold green]",
        border_style="green",
        padding=(0, 2),
    ))
    console.print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    show_welcome()

    console.print(Panel(
        "[bold]Tell me about your business[/bold]\n"
        "[dim]e.g. 'I do wedding photography in Singapore'[/dim]",
        border_style="cyan", padding=(0, 2),
    ))
    console.print()
    raw = console.input("  [bold cyan]>[/bold cyan] ").strip()
    if not raw:
        raise SystemExit(1)

    console.print()
    info = understand_business(raw)
    profession = info.get("profession", raw)
    location   = info.get("location", "")
    specialty  = info.get("specialty", "general")

    with Progress(
        SpinnerColumn("dots2"),
        TextColumn("[cyan]Brainstorming potential client types..."),
        transient=True,
    ) as p:
        p.add_task("", total=None)
        client_types = brainstorm_clients(profession, location, specialty)

    chosen = select_client_types(client_types)
    site_limit = choose_limit(len(chosen))

    # ── Extra comments before research ───────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold]Do you have any extra comments to make?[/bold]\n"
        "[dim]e.g. 'focus on luxury venues', 'avoid corporate companies', 'I specialise in outdoor shoots'\n"
        "Press Enter to skip.[/dim]",
        border_style="cyan", padding=(0, 2),
    ))
    console.print()
    extra = console.input("  [bold cyan]>[/bold cyan] ").strip()

    if extra:
        with Progress(SpinnerColumn("dots"), TextColumn("[cyan]Noted — refining search..."), transient=True) as p:
            p.add_task("", total=None)
            time.sleep(1.0)
        console.print(Panel(
            f"  [bold green]✓[/bold green]  Got it: [italic]\"{extra}\"[/italic]",
            border_style="green", padding=(0, 2),
        ))
        time.sleep(0.4)
    else:
        with Progress(SpinnerColumn("dots"), TextColumn("[dim]Starting research..."), transient=True) as p:
            p.add_task("", total=None)
            time.sleep(0.8)

    console.print()
    contacts = gather_contacts(chosen, location, site_limit, extra_context=extra)
    display_results(contacts, f"{specialty} {profession}", location)


if __name__ == "__main__":
    main()
