#!/usr/bin/env python3
import os, sys, json, csv, glob, re, smtplib, ssl, time, random
from email.mime.text import MIMEText
from datetime import datetime

import ollama
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich import box

MODEL       = "gemma3:4b"
console     = Console()
CONFIG_PATH = os.path.expanduser("~/email_sender/config.json")
CONTACT_DIR = os.path.expanduser("~/contact_finder")

SMTP_PRESETS = {
    "gmail.com":      ("smtp.gmail.com", 587),
    "googlemail.com": ("smtp.gmail.com", 587),
    "outlook.com":    ("smtp.office365.com", 587),
    "hotmail.com":    ("smtp.office365.com", 587),
    "live.com":       ("smtp.office365.com", 587),
    "yahoo.com":      ("smtp.mail.yahoo.com", 587),
    "icloud.com":     ("smtp.mail.me.com", 587),
    "me.com":         ("smtp.mail.me.com", 587),
}


def boot_sequence():
    steps = [
        "linking local AI engine (gemma3:4b)",
        "establishing secure mail relay",
        "loading contact interface",
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
        Align_center("📧  Auto Email Sender"),
        subtitle="AI writes the draft — you decide what gets sent",
        box=box.DOUBLE,
        border_style="green",
        padding=(1, 4),
    ))
    console.print()


def Align_center(s):
    from rich.align import Align
    return Align.center(Text(s, style="bold green"))


# ── Email account setup ──
def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f)


def setup_email():
    cfg = load_config()
    if cfg:
        console.print(f"  Saved account found: [bold cyan]{cfg['email']}[/bold cyan]")
        use_it = Prompt.ask("  Use this account?", choices=["y", "n"], default="y")
        if use_it == "y":
            return cfg
        console.print()

    email = Prompt.ask("  [bold]Your email address[/bold]").strip()
    domain = email.split("@")[-1].lower() if "@" in email else ""
    host, port = SMTP_PRESETS.get(domain, (None, None))

    if not host:
        console.print(f"  [yellow]Don't recognize '{domain}' — enter SMTP settings manually[/yellow]")
        host = Prompt.ask("  SMTP server (e.g. smtp.gmail.com)").strip()
        port = int(Prompt.ask("  SMTP port", default="587").strip())

    if "gmail" in host:
        console.print()
        console.print(Panel(
            "[yellow]Gmail blocks your normal password for apps like this.[/yellow]\n\n"
            "You need an [bold]App Password[/bold] instead:\n"
            "  1. Go to [cyan]myaccount.google.com/apppasswords[/cyan]\n"
            "  2. Sign in, create an app password for \"Mail\"\n"
            "  3. Copy the 16-character code it gives you and paste it below\n\n"
            "[dim](Your real Gmail password will NOT work here)[/dim]",
            border_style="yellow", box=box.ROUNDED, padding=(1, 2),
        ))
        console.print()

    console.print("  [dim](What you type/paste will be visible — that's normal here, app passwords are safe to show)[/dim]")
    console.print("  [dim](Pasting it with the spaces Google shows — like \"abcd efgh ijkl mnop\" — is fine, they're removed automatically)[/dim]")
    password = re.sub(r"\s+", "", Prompt.ask("  App password / email password"))

    cfg = {"email": email, "password": password, "host": host, "port": port}

    console.print()
    try:
        with console.status("  [cyan]⚡ establishing secure connection...[/cyan]", spinner="arc"):
            ctx = ssl.create_default_context()
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
                server.starttls(context=ctx)
                server.login(cfg["email"], cfg["password"])
        console.print("  [bold green]✓ Connected successfully[/bold green]\n")
    except Exception as e:
        console.print(f"  [bold red]✗ Couldn't connect: {e}[/bold red]")
        console.print("  [dim]Double-check your email, password/app-password, and SMTP settings.[/dim]\n")
        retry = Prompt.ask("  Try again?", choices=["y", "n"], default="y")
        if retry == "y":
            return setup_email()
        sys.exit(1)

    remember = Prompt.ask("  Save these details so you don't re-enter them next time?", choices=["y", "n"], default="y")
    if remember == "y":
        save_config(cfg)
        console.print(f"  [dim]Saved to {CONFIG_PATH}[/dim]")
    return cfg


# ── Contacts ──
def find_contact_csvs():
    if not os.path.isdir(CONTACT_DIR):
        return []
    files = glob.glob(os.path.join(CONTACT_DIR, "results_*.csv")) + glob.glob(os.path.join(CONTACT_DIR, "*.csv"))
    files = sorted(set(files), key=os.path.getmtime, reverse=True)
    return files


def load_contacts(path):
    contacts = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = (row.get("email") or "").strip()
            if email and "@" in email and "." in email.split("@")[-1]:
                contacts.append(row)
    return contacts


def pick_contacts():
    csvs = find_contact_csvs()
    console.print()
    if csvs:
        console.print("  [bold]Found these contact lists:[/bold]\n")
        shown = csvs[:8]
        for i, path in enumerate(shown, 1):
            console.print(f"    [cyan]{i}.[/cyan] {os.path.basename(path)}")
        console.print(f"    [cyan]{len(shown)+1}.[/cyan] [dim]Use a different file (enter a path)[/dim]\n")

        choice = Prompt.ask("  Pick a list", default="1").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(shown):
            path = shown[int(choice) - 1]
        else:
            path = choice.strip().strip('"').strip("'")
            path = os.path.expanduser(path)
    else:
        console.print(f"  [yellow]No CSV files found in {CONTACT_DIR}[/yellow]")
        console.print("  [dim]Tip: run Client Finder AI first — it saves results there automatically.[/dim]\n")
        path = Prompt.ask("  Path to your contacts CSV (must have an 'email' column)").strip().strip('"').strip("'")
        path = os.path.expanduser(path)

    if not os.path.isfile(path):
        console.print(f"\n  [bold red]File not found: {path}[/bold red]\n")
        sys.exit(1)

    with console.status(f"  [cyan]⚡ scanning {os.path.basename(path)}...[/cyan]", spinner="dots12"):
        time.sleep(random.uniform(0.5, 0.9))
        contacts = load_contacts(path)
    return contacts


# ── AI draft generation ──
def generate_draft(contact, goal, sender_name):
    company = contact.get("company") or contact.get("name") or "there"
    ctype   = contact.get("client_type", "")

    prompt = f"""Write a short, warm, professional cold outreach email.

Sender's name / business: {sender_name}
Recipient's business: {company}
Recipient's business type: {ctype}
What the sender wants to achieve: {goal}

Rules:
- Under 130 words
- Sound human and specific to THIS recipient's business type — not generic
- No corporate buzzwords or "I hope this email finds you well"
- End with one simple, low-pressure call to action
- Output in EXACTLY this format and nothing else, no extra commentary:

SUBJECT: <subject line here>
BODY:
<email body here>"""

    resp = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
    text = resp["message"]["content"].strip()

    subject, body = f"Quick note for {company}", text
    m = re.search(r"SUBJECT:\s*(.+)", text)
    if m:
        subject = m.group(1).strip()
    b = re.search(r"BODY:\s*(.*)", text, re.DOTALL)
    if b:
        body = b.group(1).strip()
    return subject, body


# ── Sending ──
def send_email(cfg, to_email, subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"]    = cfg["email"]
    msg["To"]      = to_email

    ctx = ssl.create_default_context()
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
        server.starttls(context=ctx)
        server.login(cfg["email"], cfg["password"])
        server.send_message(msg)


# ── Manual edit ──
def edit_draft(subject, body):
    console.print(f"\n  [bold]New subject[/bold] [dim](blank = keep current)[/dim]")
    new_subject = console.input("  > ").strip()
    if new_subject:
        subject = new_subject

    console.print(f"\n  [bold]New body[/bold] [dim](type your email, then a line with just END — blank first line = keep current)[/dim]")
    first = console.input("  ")
    if first.strip():
        lines = [first]
        while True:
            line = console.input("  ")
            if line.strip() == "END":
                break
            lines.append(line)
        body = "\n".join(lines)
    return subject, body


# ── Log ──
def log_sent(path, to_email, company, subject):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "company", "email", "subject"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), company, to_email, subject])


def main():
    banner()
    cfg = setup_email()

    contacts = pick_contacts()
    if not contacts:
        console.print("\n  [bold red]No contacts with valid email addresses found in that file.[/bold red]\n")
        return
    console.print(f"\n  [bold green]✓ Loaded {len(contacts)} contacts[/bold green]\n")

    sender_name = Prompt.ask("  [bold]Your name or business name[/bold] [dim](used in the emails)[/dim]").strip()
    goal = Prompt.ask(
        "  [bold]What's the goal of this email?[/bold]\n"
        "  [dim]e.g. \"offer my logo design services to small bakeries\"[/dim]\n  "
    ).strip()

    log_path = os.path.join(os.path.expanduser("~/email_sender"), f"sent_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    sent = skipped = failed = 0
    total = len(contacts)

    for i, contact in enumerate(contacts, 1):
        to_email = contact.get("email", "").strip()
        company  = contact.get("company") or contact.get("name") or "Unknown"

        console.print()
        console.rule(f"[bold]Contact {i}/{total} — {company}  [dim]<{to_email}>[/dim][/bold]", style="green")

        thinking_msg = random.choice([
            "[green]⚡ analyzing recipient profile...[/green]",
            "[green]⚡ composing personalized draft...[/green]",
            "[green]⚡ tuning tone & structure...[/green]",
            "[green]⚡ running it through the language model...[/green]",
        ])
        with console.status(f"  {thinking_msg}", spinner="dots12"):
            try:
                subject, body = generate_draft(contact, goal, sender_name)
            except Exception as e:
                console.print(f"  [bold red]✗ AI failed to generate a draft: {e}[/bold red]")
                failed += 1
                continue

        while True:
            console.print()
            console.print(Panel(
                f"[bold]Subject:[/bold] {subject}\n\n{body}",
                title="✉  Draft preview",
                border_style="cyan",
                box=box.ROUNDED,
                padding=(1, 2),
            ))
            console.print(
                "  [bold green][A][/bold green]pprove & send   "
                "[bold yellow][E][/bold yellow]dit   "
                "[bold]\\[S][/bold]kip   "
                "[bold red][Q][/bold red]uit"
            )
            action = console.input("  > ").strip().lower()

            if action in ("a", "approve", ""):
                try:
                    with console.status(f"  [cyan]⚡ transmitting to {to_email}...[/cyan]", spinner="bouncingBar"):
                        send_email(cfg, to_email, subject, body)
                        log_sent(log_path, to_email, company, subject)
                    console.print(f"  [bold green]✓ Sent to {to_email}[/bold green]")
                    sent += 1
                except Exception as e:
                    console.print(f"  [bold red]✗ Failed to send: {e}[/bold red]")
                    failed += 1
                break
            elif action in ("e", "edit"):
                subject, body = edit_draft(subject, body)
                continue
            elif action in ("s", "skip"):
                console.print(f"  [yellow]– Skipped {to_email}[/yellow]")
                skipped += 1
                break
            elif action in ("q", "quit"):
                console.print()
                console.print(Panel(
                    f"Sent: [bold green]{sent}[/bold green]   "
                    f"Skipped: [bold yellow]{skipped}[/bold yellow]   "
                    f"Failed: [bold red]{failed}[/bold red]   "
                    f"Remaining: [dim]{total - i}[/dim]\n\n"
                    f"[dim]Log saved to: {log_path if sent else '(nothing sent yet)'}[/dim]",
                    title="Stopped early", border_style="yellow", box=box.ROUNDED,
                ))
                console.print()
                return
            else:
                console.print("  [dim]Type A, E, S, or Q[/dim]")

    with console.status("  [cyan]⚡ syncing logs & closing connection...[/cyan]", spinner="dots12"):
        time.sleep(0.6)

    console.print()
    console.print(Panel(
        f"[bold green]✓ All done![/bold green]\n\n"
        f"Sent:    [bold green]{sent}[/bold green]\n"
        f"Skipped: [bold yellow]{skipped}[/bold yellow]\n"
        f"Failed:  [bold red]{failed}[/bold red]\n\n"
        f"[dim]Log saved to: {log_path}[/dim]",
        border_style="green", box=box.DOUBLE, padding=(1, 2),
    ))
    console.print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n  [dim]Goodbye![/dim]\n")
    except Exception as e:
        console.print(f"\n  [bold red]Unexpected error: {e}[/bold red]\n")
