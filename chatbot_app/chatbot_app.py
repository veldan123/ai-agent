import threading, json, socket, time, os, sys, sqlite3, hashlib, uuid, urllib.request
from flask import Flask, request, Response, session, jsonify, stream_with_context
import ollama, webview

try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False

VERSION     = "1.5.3"
VERSION_URL = "https://raw.githubusercontent.com/veldan123/ai-agent/main/chatbot_app/version.txt"
APP_URL     = "https://raw.githubusercontent.com/veldan123/ai-agent/main/chatbot_app/chatbot_app.py"
APP_PATH    = os.path.expanduser("~/chatbot_app/chatbot_app.py")

MODEL    = "mistral:7b"
DB_PATH  = os.path.expanduser("~/chatbot_app/chats.db")
KEY_FILE = os.path.expanduser("~/chatbot_app/.secret")

# ── Persist session secret across restarts ──
if os.path.exists(KEY_FILE):
    with open(KEY_FILE) as f:
        SECRET = f.read().strip()
else:
    SECRET = os.urandom(32).hex()
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    with open(KEY_FILE, "w") as f:
        f.write(SECRET)

server = Flask(__name__)
server.secret_key = SECRET

# ── Database ──
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    c = db()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            chat_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    c.commit()
    c.close()

def hash_pw(password, salt=None):
    if not salt:
        salt = os.urandom(16).hex()
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"

def verify_pw(password, stored):
    salt, h = stored.split(":", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == h

# ── Auth routes ──
@server.route("/api/me")
def me():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"logged_in": False})
    c = db()
    row = c.execute("SELECT username FROM users WHERE id=?", (uid,)).fetchone()
    c.close()
    if not row:
        session.clear()
        return jsonify({"logged_in": False})
    return jsonify({"logged_in": True, "username": row["username"]})

@server.route("/api/signup", methods=["POST"])
def signup():
    data = request.json
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    if len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters"}), 400
    uid = str(uuid.uuid4())
    try:
        c = db()
        c.execute("INSERT INTO users(id,username,password) VALUES(?,?,?)",
                  (uid, username, hash_pw(password)))
        c.commit()
        c.close()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already taken"}), 409
    session["user_id"] = uid
    return jsonify({"ok": True, "username": username})

@server.route("/api/login", methods=["POST"])
def login():
    data = request.json
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    c = db()
    row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    c.close()
    if not row or not verify_pw(password, row["password"]):
        return jsonify({"error": "Wrong username or password"}), 401
    session["user_id"] = row["id"]
    return jsonify({"ok": True, "username": username})

@server.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})

# ── Chat routes ──
@server.route("/api/chats")
def get_chats():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Not logged in"}), 401
    c = db()
    rows = c.execute(
        "SELECT id,title,created_at FROM chats WHERE user_id=? ORDER BY created_at DESC",
        (uid,)).fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])

@server.route("/api/chats", methods=["POST"])
def new_chat():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Not logged in"}), 401
    data = request.json
    cid   = str(uuid.uuid4())
    title = (data.get("title") or "New chat")[:60]
    c = db()
    c.execute("INSERT INTO chats(id,user_id,title) VALUES(?,?,?)", (cid, uid, title))
    c.commit()
    c.close()
    return jsonify({"id": cid, "title": title})

@server.route("/api/chats/<cid>", methods=["DELETE"])
def delete_chat(cid):
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Not logged in"}), 401
    c = db()
    c.execute("DELETE FROM messages WHERE chat_id=?", (cid,))
    c.execute("DELETE FROM chats WHERE id=? AND user_id=?", (cid, uid))
    c.commit()
    c.close()
    return jsonify({"ok": True})

@server.route("/api/chats/<cid>/messages")
def get_messages(cid):
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Not logged in"}), 401
    c = db()
    rows = c.execute(
        "SELECT role,content FROM messages WHERE chat_id=? ORDER BY created_at",
        (cid,)).fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])

# ── Version / update check ──
@server.route("/api/check-update")
def check_update_api():
    try:
        with urllib.request.urlopen(VERSION_URL, timeout=5) as r:
            remote = r.read().decode().strip()
        return jsonify({"current": VERSION, "remote": remote, "update_available": remote != VERSION})
    except Exception:
        return jsonify({"current": VERSION, "remote": VERSION, "update_available": False})


# ── Web search ──
@server.route("/api/search")
def web_search():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Not logged in"}), 401
    if not HAS_DDG:
        return jsonify({"error": "duckduckgo-search not installed", "results": []})
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    try:
        results = []
        with DDGS() as ddgs:
            for h in ddgs.text(q, max_results=4):
                results.append({"title": h["title"], "body": h["body"], "url": h["href"], "type": "web"})
            try:
                for h in ddgs.news(q, max_results=3):
                    results.append({"title": h["title"], "body": h["body"], "url": h["url"], "type": "news", "date": h.get("date","")})
            except Exception:
                pass
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e), "results": []})


# ── Streaming chat ──
@server.route("/api/chat", methods=["POST"])
def chat():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Not logged in"}), 401
    data     = request.json
    messages = data.get("messages", [])
    chat_id  = data.get("chat_id")

    def generate():
        full = ""
        try:
            stream = ollama.chat(model=MODEL, messages=messages, stream=True)
            for chunk in stream:
                piece = chunk.message.content or ""
                full += piece
                if piece:
                    yield f"data: {json.dumps({'content': piece})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Save user + assistant messages
        if chat_id and full:
            c = db()
            user_msg = messages[-1]["content"] if messages else ""
            c.execute("INSERT INTO messages(id,chat_id,role,content) VALUES(?,?,?,?)",
                      (str(uuid.uuid4()), chat_id, "user", user_msg))
            c.execute("INSERT INTO messages(id,chat_id,role,content) VALUES(?,?,?,?)",
                      (str(uuid.uuid4()), chat_id, "assistant", full))
            # Update title from first message
            if len(messages) == 1:
                title = user_msg[:55] + ("…" if len(user_msg) > 55 else "")
                c.execute("UPDATE chats SET title=? WHERE id=?", (title, chat_id))
            c.commit()
            c.close()

        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

# ── Main HTML ──
@server.route("/")
def index():
    return HTML

# ── HTML ──
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>AI Chatbot</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0a0a0f;color:#e2e8f0;height:100vh;overflow:hidden}

/* ── Login ── */
#login-screen{display:flex;align-items:center;justify-content:center;height:100vh;background:radial-gradient(ellipse 80% 60% at 50% 0%,#1a0a3a,#0a0a0f)}
.auth-card{background:#0d1117;border:1px solid #1e2a3a;border-radius:20px;padding:40px 36px;width:100%;max-width:380px}
.auth-logo{font-size:2rem;text-align:center;margin-bottom:8px}
.auth-title{font-size:1.4rem;font-weight:800;color:#f1f5f9;text-align:center;margin-bottom:4px}
.auth-sub{font-size:.85rem;color:#64748b;text-align:center;margin-bottom:28px}
.auth-err{background:#2a0a0a;border:1px solid #7f1d1d;color:#f87171;font-size:.83rem;padding:10px 14px;border-radius:8px;margin-bottom:16px;display:none}
.field-label{font-size:.8rem;font-weight:700;color:#94a3b8;margin-bottom:6px;display:block}
.field-input{width:100%;background:#161b22;border:1px solid #1e2a3a;border-radius:10px;padding:11px 14px;color:#e2e8f0;font-size:.93rem;outline:none;transition:border-color .15s;margin-bottom:14px}
.field-input:focus{border-color:#7c3aed}
.auth-btn{width:100%;background:linear-gradient(135deg,#6d28d9,#7c3aed);color:#fff;border:none;border-radius:10px;padding:13px;font-size:.95rem;font-weight:800;cursor:pointer;transition:opacity .15s;margin-top:4px}
.auth-btn:hover{opacity:.85}
.auth-switch{text-align:center;margin-top:18px;font-size:.83rem;color:#64748b}
.auth-switch a{color:#a78bfa;font-weight:600;cursor:pointer;text-decoration:none}

/* ── App ── */
#app-screen{display:none;height:100vh;flex-direction:row}
.sidebar{width:240px;background:#08090f;border-right:1px solid #1e2a3a;display:flex;flex-direction:column;flex-shrink:0;height:100vh}
.sb-top{padding:14px}
.new-btn{width:100%;background:linear-gradient(135deg,#6d28d9,#7c3aed);color:#fff;border:none;border-radius:10px;padding:11px;font-size:13px;font-weight:700;cursor:pointer;transition:opacity .15s}
.new-btn:hover{opacity:.85}
.sb-label{padding:12px 14px 6px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#475569}
.chat-list{flex:1;overflow-y:auto;padding:0 6px}
.chat-list::-webkit-scrollbar{width:3px}
.chat-list::-webkit-scrollbar-thumb{background:#1e2a3a;border-radius:3px}
.chat-item{padding:9px 10px;border-radius:8px;font-size:.82rem;color:#64748b;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transition:background .1s,color .1s;display:flex;align-items:center;justify-content:space-between;gap:6px}
.chat-item:hover{background:#111827;color:#e2e8f0}
.chat-item.active{background:#1a1040;color:#a78bfa}
.chat-item-title{flex:1;overflow:hidden;text-overflow:ellipsis}
.del-btn{opacity:0;font-size:13px;color:#475569;background:none;border:none;cursor:pointer;flex-shrink:0;padding:2px 4px;border-radius:4px;transition:opacity .15s,color .15s}
.chat-item:hover .del-btn{opacity:1}
.del-btn:hover{color:#ef4444}
.sb-foot{padding:12px 14px;border-top:1px solid #1e2a3a;display:flex;align-items:center;justify-content:space-between}
.sb-user{font-size:.83rem;color:#64748b;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.logout-btn{font-size:.78rem;color:#475569;background:none;border:1px solid #1e2a3a;padding:4px 10px;border-radius:6px;cursor:pointer;transition:all .15s;flex-shrink:0}
.logout-btn:hover{border-color:#7c3aed;color:#a78bfa}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.messages{flex:1;overflow-y:auto;padding:24px 0}
.messages::-webkit-scrollbar{width:4px}
.messages::-webkit-scrollbar-thumb{background:#1e2a3a;border-radius:4px}
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:18px;padding:40px}
.empty-title{font-size:1.5rem;font-weight:800;color:#f1f5f9}
.empty-sub{font-size:.88rem;color:#64748b}
.suggestions{display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:520px;width:100%}
.sug{background:#0d1117;border:1px solid #1e2a3a;border-radius:12px;padding:13px 15px;font-size:.82rem;color:#94a3b8;cursor:pointer;text-align:left;line-height:1.5;transition:border-color .15s,color .15s}
.sug:hover{border-color:#7c3aed;color:#e2e8f0}
.msg-row{display:flex;padding:4px 20px;max-width:820px;margin:0 auto;width:100%}
.msg-row.user{justify-content:flex-end}
.bubble{max-width:72%;padding:12px 16px;border-radius:18px;font-size:.92rem;line-height:1.7;white-space:pre-wrap;word-break:break-word}
.user .bubble{background:linear-gradient(135deg,#6d28d9,#7c3aed);color:#fff;border-bottom-right-radius:4px}
.assistant .bubble{background:#0d1117;border:1px solid #1e2a3a;color:#e2e8f0;border-bottom-left-radius:4px}
.cursor{display:inline-block;width:2px;height:1em;background:#a78bfa;border-radius:1px;margin-left:2px;vertical-align:middle;animation:blink .8s step-end infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}
.input-area{padding:14px 20px 20px;border-top:1px solid #1e2a3a;background:#0a0a0f}
.input-wrap{max-width:820px;margin:0 auto;background:#0d1117;border:1px solid #1e2a3a;border-radius:14px;display:flex;align-items:flex-end;gap:10px;padding:10px 12px;transition:border-color .2s}
.input-wrap:focus-within{border-color:#7c3aed}
textarea{flex:1;background:none;border:none;outline:none;color:#e2e8f0;font-size:.93rem;line-height:1.6;resize:none;max-height:160px;font-family:inherit;padding:2px 0}
textarea::placeholder{color:#475569}
.send{width:36px;height:36px;background:linear-gradient(135deg,#6d28d9,#7c3aed);border:none;border-radius:9px;color:#fff;font-size:15px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:opacity .15s}
.send:hover{opacity:.85}
.send:disabled{opacity:.35;cursor:not-allowed}
.web-btn{width:36px;height:36px;background:#0d1117;border:1px solid #1e2a3a;border-radius:9px;color:#475569;font-size:16px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .15s}
.web-btn:hover{border-color:#7c3aed;color:#a78bfa}
.web-btn.active{background:#1a1040;border-color:#7c3aed;color:#a78bfa}
.search-status{max-width:820px;margin:0 auto 6px;font-size:11px;color:#7c3aed;display:none;align-items:center;gap:6px}
.search-dot{width:6px;height:6px;background:#7c3aed;border-radius:50%;animation:pulse 1s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.hint{max-width:820px;margin:6px auto 0;font-size:11px;color:#334155;text-align:center}
.update-banner{background:#1a1200;border-bottom:1px solid #854d0e;padding:9px 20px;font-size:12px;color:#fbbf24;display:none;align-items:center;justify-content:center;gap:10px;text-align:center;line-height:1.5}
.update-banner code{background:#2a1e00;border:1px solid #854d0e;border-radius:5px;padding:2px 7px;font-size:11px;color:#fcd34d;font-family:'SF Mono','Fira Code',monospace;user-select:all}
</style>
</head>
<body>

<!-- ── Login Screen ── -->
<div id="login-screen">
  <div class="auth-card">
    <div class="auth-logo">🤖</div>
    <div class="auth-title" id="auth-title">Welcome back</div>
    <div class="auth-sub" id="auth-sub">Sign in to access your chats</div>
    <div class="auth-err" id="auth-err"></div>
    <label class="field-label">Username</label>
    <input class="field-input" id="auth-user" type="text" placeholder="Your username" autocomplete="username"/>
    <label class="field-label">Password</label>
    <input class="field-input" id="auth-pass" type="password" placeholder="Your password" autocomplete="current-password" onkeydown="if(event.key==='Enter')authSubmit()"/>
    <button class="auth-btn" id="auth-btn" onclick="authSubmit()">Sign in</button>
    <div class="auth-switch" id="auth-switch">
      Don't have an account? <a onclick="toggleAuth()">Sign up</a>
    </div>
  </div>
</div>

<!-- ── App Screen ── -->
<div id="app-screen">
  <div class="sidebar">
    <div class="sb-top">
      <button class="new-btn" onclick="newChat()">+ New Chat</button>
    </div>
    <div class="sb-label">Chats</div>
    <div class="chat-list" id="chatList"></div>
    <div class="sb-foot">
      <div class="sb-user" id="sb-username"></div>
      <button class="logout-btn" onclick="logout()">Sign out</button>
    </div>
  </div>
  <div class="main">
    <div class="update-banner" id="updateBanner">
      ⬆ A new version is available. Re-run the installer to update:&nbsp;
      <code>curl -fsSL https://raw.githubusercontent.com/veldan123/ai-agent/main/chatbot_app/install_mac.sh | bash</code>
    </div>
    <div class="messages" id="msgs"></div>
    <div class="input-area">
      <div class="search-status" id="searchStatus"><div class="search-dot"></div>Searching the web…</div>
      <div class="input-wrap">
        <button class="web-btn" id="webBtn" onclick="toggleWeb()" title="Toggle web search">🌐</button>
        <textarea id="inp" rows="1" placeholder="Message AI..." onkeydown="handleKey(event)" oninput="resize(this)"></textarea>
        <button class="send" id="sendBtn" onclick="sendMsg()">&#10148;</button>
      </div>
      <div class="hint">🌐 Web search &nbsp;·&nbsp; Enter to send &nbsp;·&nbsp; Shift+Enter for new line</div>
    </div>
  </div>
</div>

<script>
let currentChatId = null, msgs = [], streaming = false, isLogin = true, webOn = false;

// ── Boot ──
async function boot() {
  const res = await fetch('/api/me');
  const data = await res.json();
  if (data.logged_in) showApp(data.username);
  else showLogin();
  checkForUpdate();
}
boot();

async function checkForUpdate() {
  try {
    const res = await fetch('/api/check-update');
    const data = await res.json();
    if (data.update_available) {
      document.getElementById('updateBanner').style.display = 'flex';
    }
  } catch(e) {}
}

// ── Auth ──
function showLogin() {
  document.getElementById('login-screen').style.display = 'flex';
  document.getElementById('app-screen').style.display = 'none';
}
function showApp(username) {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app-screen').style.display = 'flex';
  document.getElementById('sb-username').textContent = username;
  loadChats();
  showWelcome();
}
function toggleAuth() {
  isLogin = !isLogin;
  document.getElementById('auth-title').textContent = isLogin ? 'Welcome back' : 'Create account';
  document.getElementById('auth-sub').textContent   = isLogin ? 'Sign in to access your chats' : 'Start chatting for free';
  document.getElementById('auth-btn').textContent   = isLogin ? 'Sign in' : 'Sign up';
  document.getElementById('auth-switch').innerHTML  = isLogin
    ? "Don't have an account? <a onclick='toggleAuth()'>Sign up</a>"
    : "Already have an account? <a onclick='toggleAuth()'>Sign in</a>";
  document.getElementById('auth-err').style.display = 'none';
}
async function authSubmit() {
  const user = document.getElementById('auth-user').value.trim();
  const pass = document.getElementById('auth-pass').value;
  const errEl = document.getElementById('auth-err');
  errEl.style.display = 'none';
  if (!user || !pass) { errEl.textContent = 'Please fill in all fields.'; errEl.style.display = 'block'; return; }
  const endpoint = isLogin ? '/api/login' : '/api/signup';
  const res = await fetch(endpoint, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username:user, password:pass}) });
  const data = await res.json();
  if (data.error) { errEl.textContent = data.error; errEl.style.display = 'block'; return; }
  showApp(data.username);
}
async function logout() {
  await fetch('/api/logout', {method:'POST'});
  currentChatId = null; msgs = [];
  document.getElementById('auth-user').value = '';
  document.getElementById('auth-pass').value = '';
  showLogin();
}

// ── Chats ──
async function loadChats() {
  const res = await fetch('/api/chats');
  const chats = await res.json();
  const list = document.getElementById('chatList');
  list.innerHTML = '';
  chats.forEach(c => {
    const item = document.createElement('div');
    item.className = 'chat-item' + (c.id === currentChatId ? ' active' : '');
    item.dataset.id = c.id;
    item.innerHTML = `<span class="chat-item-title">${esc(c.title)}</span><button class="del-btn" onclick="delChat(event,'${c.id}')">&#10005;</button>`;
    item.onclick = () => openChat(c.id, c.title);
    list.appendChild(item);
  });
}
async function openChat(id, title) {
  currentChatId = id;
  document.querySelectorAll('.chat-item').forEach(el => el.classList.toggle('active', el.dataset.id === id));
  const res = await fetch(`/api/chats/${id}/messages`);
  const messages = await res.json();
  msgs = messages;
  const el = document.getElementById('msgs');
  el.innerHTML = '';
  messages.forEach(m => addBubble(m.role, m.content, false));
  el.scrollTop = el.scrollHeight;
}
async function newChat() {
  const res = await fetch('/api/chats', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({title:'New chat'}) });
  const chat = await res.json();
  currentChatId = chat.id;
  msgs = [];
  await loadChats();
  showWelcome();
  document.getElementById('inp').focus();
}
async function delChat(e, id) {
  e.stopPropagation();
  await fetch(`/api/chats/${id}`, {method:'DELETE'});
  if (currentChatId === id) { currentChatId = null; msgs = []; showWelcome(); }
  loadChats();
}

// ── Messages ──
function showWelcome() {
  document.getElementById('msgs').innerHTML = `
    <div class="empty">
      <div class="empty-title">What can I help with?</div>
      <div class="empty-sub">Your chats are saved automatically.</div>
      <div class="suggestions">
        <button class="sug" onclick="useSug(this)">Write a professional follow-up email</button>
        <button class="sug" onclick="useSug(this)">Explain machine learning simply</button>
        <button class="sug" onclick="useSug(this)">Give me 5 business name ideas</button>
        <button class="sug" onclick="useSug(this)">Write a Python script to rename files</button>
      </div>
    </div>`;
}
function addBubble(role, text, scroll=true) {
  const el = document.getElementById('msgs');
  el.querySelector('.empty')?.remove();
  const row = document.createElement('div');
  row.className = `msg-row ${role}`;
  const b = document.createElement('div');
  b.className = 'bubble';
  b.textContent = text;
  row.appendChild(b);
  el.appendChild(row);
  if (scroll) el.scrollTop = el.scrollHeight;
  return b;
}

// ── Send ──
async function sendMsg(text) {
  const inp = document.getElementById('inp');
  const userText = text || inp.value.trim();
  if (!userText || streaming) return;

  // Create chat if none selected
  if (!currentChatId) {
    const res = await fetch('/api/chats', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({title: userText.slice(0,55)}) });
    const chat = await res.json();
    currentChatId = chat.id;
    await loadChats();
  }

  inp.value = ''; inp.style.height = 'auto';
  msgs.push({role:'user', content:userText});
  addBubble('user', userText);

  // Web search: inject results as system context
  let searchCtx = null;
  if (webOn) {
    document.getElementById('searchStatus').style.display = 'flex';
    document.getElementById('sendBtn').disabled = true;
    try {
      const sr = await fetch('/api/search?q=' + encodeURIComponent(userText));
      const sd = await sr.json();
      if (sd.results && sd.results.length) {
        let ctx = `I just searched the web right now for: "${userText}"\n\nHere are the live search results:\n\n`;
        sd.results.forEach((r,i) => {
          const tag = r.type === 'news' ? `[NEWS${r.date ? ' — '+r.date : ''}]` : '[WEB]';
          ctx += `${i+1}. ${tag} ${r.title}\n   Source: ${r.url}\n   ${r.body}\n\n`;
        });
        ctx += `---\nUsing ONLY the search results above (not your training data), answer this question: ${userText}`;
        searchCtx = ctx;
      }
    } catch(e) {}
    document.getElementById('searchStatus').style.display = 'none';
  }

  const aiBubble = addBubble('assistant', '');
  const cursor = document.createElement('span');
  cursor.className = 'cursor';
  aiBubble.appendChild(cursor);
  streaming = true;
  document.getElementById('sendBtn').disabled = true;

  // Build messages: replace the last user message with search context injected into it
  const payload = searchCtx
    ? [...msgs.slice(0, -1), {role:'user', content: searchCtx}]
    : msgs;

  let full = '';
  try {
    const res = await fetch('/api/chat', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({messages: payload, chat_id: currentChatId})
    });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    while(true) {
      const {done, value} = await reader.read();
      if(done) break;
      const lines = dec.decode(value).split('\\n').filter(l=>l.startsWith('data:'));
      for(const line of lines) {
        const d = line.slice(5).trim();
        if(d==='[DONE]') break;
        try {
          const obj = JSON.parse(d);
          if(obj.error) {
            cursor.remove();
            aiBubble.textContent = '⚠ ' + obj.error;
            return;
          }
          if(obj.content) {
            full += obj.content;
            cursor.remove();
            aiBubble.textContent = full;
            aiBubble.appendChild(cursor);
            document.getElementById('msgs').scrollTop = 1e9;
          }
        } catch{}
      }
    }
  } catch(e) {
    cursor.remove();
    aiBubble.textContent = 'Could not reach Ollama. Make sure it is running.';
  }

  cursor.remove();
  if(full) {
    msgs.push({role:'assistant', content:full});
    loadChats(); // refresh sidebar title
  }
  streaming = false;
  document.getElementById('sendBtn').disabled = false;
  document.getElementById('inp').focus();
}

// ── Web search toggle ──
function toggleWeb() {
  webOn = !webOn;
  const btn = document.getElementById('webBtn');
  btn.classList.toggle('active', webOn);
  btn.title = webOn ? 'Web search ON — click to turn off' : 'Web search OFF — click to turn on';
}

function useSug(btn) { sendMsg(btn.textContent); }
function handleKey(e) { if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg();} }
function resize(el)   { el.style.height='auto'; el.style.height=Math.min(el.scrollHeight,160)+'px'; }
function esc(s)       { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
</script>
</body>
</html>"""


def free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def check_update():
    try:
        with urllib.request.urlopen(VERSION_URL, timeout=5) as r:
            remote = r.read().decode().strip()
        if remote != VERSION:
            print(f"  Updating {VERSION} → {remote}…")
            urllib.request.urlretrieve(APP_URL, APP_PATH)
            os.execv(sys.executable, [sys.executable, APP_PATH])
    except Exception:
        pass  # No internet or GitHub down — just continue


if __name__ == "__main__":
    check_update()
    init_db()
    port = free_port()

    def run():
        server.run(port=port, debug=False, use_reloader=False, threaded=True)

    threading.Thread(target=run, daemon=True).start()
    time.sleep(1)

    webview.create_window("AI Chatbot", f"http://127.0.0.1:{port}",
                          width=1020, height=720, resizable=True, min_size=(600, 420))
    webview.start()
