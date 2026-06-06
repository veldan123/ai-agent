import threading, json, socket, time, sys
from flask import Flask, request, Response, stream_with_context
import ollama, webview

MODEL = "qwen2.5:7b"
server = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>AI Chatbot</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0a0a0f;color:#e2e8f0;height:100vh;display:flex;overflow:hidden}
.sidebar{width:220px;background:#08090f;border-right:1px solid #1e2a3a;display:flex;flex-direction:column;flex-shrink:0}
.sidebar-top{padding:14px}
.new-btn{width:100%;background:linear-gradient(135deg,#6d28d9,#7c3aed);color:#fff;border:none;border-radius:10px;padding:11px;font-size:13px;font-weight:700;cursor:pointer;transition:opacity .15s}
.new-btn:hover{opacity:.85}
.sidebar-foot{padding:12px 16px;font-size:11px;color:#334155;border-top:1px solid #1e2a3a;margin-top:auto}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.messages{flex:1;overflow-y:auto;padding:24px 0}
.messages::-webkit-scrollbar{width:4px}
.messages::-webkit-scrollbar-thumb{background:#1e2a3a;border-radius:4px}
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:20px;padding:40px}
.empty-title{font-size:1.5rem;font-weight:800;color:#f1f5f9}
.empty-sub{font-size:.9rem;color:#64748b;text-align:center}
.suggestions{display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:520px;width:100%}
.sug{background:#0d1117;border:1px solid #1e2a3a;border-radius:12px;padding:13px 15px;font-size:.83rem;color:#94a3b8;cursor:pointer;text-align:left;line-height:1.5;transition:border-color .15s,color .15s}
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
.hint{max-width:820px;margin:6px auto 0;font-size:11px;color:#334155;text-align:center}
</style>
</head>
<body>
<div class="sidebar">
  <div class="sidebar-top">
    <button class="new-btn" onclick="newChat()">+ New Chat</button>
  </div>
  <div class="sidebar-foot">AI Chatbot &mdash; Local</div>
</div>
<div class="main">
  <div class="messages" id="msgs"></div>
  <div class="input-area">
    <div class="input-wrap">
      <textarea id="inp" rows="1" placeholder="Message AI..." onkeydown="handleKey(event)" oninput="resize(this)"></textarea>
      <button class="send" id="sendBtn" onclick="send()">&#10148;</button>
    </div>
    <div class="hint">Enter to send &nbsp;&middot;&nbsp; Shift+Enter for new line</div>
  </div>
</div>
<script>
let msgs = [], streaming = false;

function welcome() {
  document.getElementById('msgs').innerHTML = `
    <div class="empty">
      <div class="empty-title">What can I help with?</div>
      <div class="empty-sub">Running privately on your computer &mdash; no internet needed.</div>
      <div class="suggestions">
        <button class="sug" onclick="useSug(this)">Write a professional follow-up email</button>
        <button class="sug" onclick="useSug(this)">Explain machine learning simply</button>
        <button class="sug" onclick="useSug(this)">Give me 5 business name ideas</button>
        <button class="sug" onclick="useSug(this)">Write a Python script to rename files</button>
      </div>
    </div>`;
}

function newChat() { msgs = []; welcome(); document.getElementById('inp').focus(); }
welcome();

function addBubble(role, text) {
  const e = document.getElementById('msgs');
  const empty = e.querySelector('.empty');
  if (empty) empty.remove();
  const row = document.createElement('div');
  row.className = `msg-row ${role}`;
  const b = document.createElement('div');
  b.className = 'bubble';
  b.textContent = text;
  row.appendChild(b);
  e.appendChild(row);
  e.scrollTop = e.scrollHeight;
  return b;
}

async function send(text) {
  const inp = document.getElementById('inp');
  const userText = text || inp.value.trim();
  if (!userText || streaming) return;
  inp.value = ''; inp.style.height = 'auto';
  msgs.push({role:'user', content:userText});
  addBubble('user', userText);
  const aiBubble = addBubble('assistant', '');
  const cursor = document.createElement('span');
  cursor.className = 'cursor';
  aiBubble.appendChild(cursor);
  streaming = true;
  document.getElementById('sendBtn').disabled = true;
  let full = '';
  try {
    const res = await fetch('/chat', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({messages: msgs})
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
          if(obj.content) { full+=obj.content; cursor.remove(); aiBubble.textContent=full; aiBubble.appendChild(cursor); document.getElementById('msgs').scrollTop=1e9; }
          if(obj.error) { cursor.remove(); aiBubble.textContent='Error: '+obj.error; }
        } catch{}
      }
    }
  } catch(e) {
    cursor.remove();
    aiBubble.textContent = 'Could not reach Ollama. Make sure it is running.';
  }
  cursor.remove();
  if(full) msgs.push({role:'assistant', content:full});
  streaming = false;
  document.getElementById('sendBtn').disabled = false;
  document.getElementById('inp').focus();
}

function useSug(btn) { send(btn.textContent); }
function handleKey(e) { if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();} }
function resize(el) { el.style.height='auto'; el.style.height=Math.min(el.scrollHeight,160)+'px'; }
</script>
</body>
</html>"""


@server.route("/")
def index():
    return HTML


@server.route("/chat", methods=["POST"])
def chat():
    messages = request.json.get("messages", [])

    def generate():
        try:
            stream = ollama.chat(model=MODEL, messages=messages, stream=True)
            for chunk in stream:
                content = chunk.message.content or ""
                if content:
                    yield f"data: {json.dumps({'content': content})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


def free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


if __name__ == "__main__":
    port = free_port()

    def run():
        server.run(port=port, debug=False, use_reloader=False, threaded=True)

    threading.Thread(target=run, daemon=True).start()
    time.sleep(1)

    webview.create_window("AI Chatbot", f"http://127.0.0.1:{port}",
                          width=1020, height=720, resizable=True, min_size=(600, 420))
    webview.start()
