import customtkinter as ctk
import threading
import ollama

ctk.set_appearance_mode("dark")

MODEL = "qwen2.5:7b"
PURPLE = "#7c3aed"
SURFACE = "#0d1117"
DARK = "#08090f"
BORDER = "#1e2a3a"
TEXT = "#e2e8f0"
MUTED = "#64748b"
ACCENT = "#a78bfa"
PINK = "#f472b6"


class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Chatbot")
        self.geometry("980x700")
        self.minsize(640, 460)
        self.configure(fg_color="#0a0a0f")

        self.messages = []
        self.is_streaming = False

        self._build()
        self.after(200, self._check_ollama)

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ──
        sb = ctk.CTkFrame(self, width=220, fg_color=DARK, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_rowconfigure(1, weight=1)
        sb.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            sb, text="＋  New Chat", height=42,
            fg_color=PURPLE, hover_color="#5b21b6",
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=10, command=self._new_chat
        ).grid(row=0, column=0, padx=14, pady=(18, 10), sticky="ew")

        ctk.CTkLabel(
            sb, text="Model", text_color="#334155",
            font=ctk.CTkFont(size=10, weight="bold")
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 2))

        ctk.CTkLabel(
            sb, text="qwen2.5:7b",
            text_color=MUTED, font=ctk.CTkFont(size=11)
        ).grid(row=3, column=0, sticky="w", padx=16, pady=(0, 12))

        self.status_label = ctk.CTkLabel(
            sb, text="● Connecting...",
            text_color=MUTED, font=ctk.CTkFont(size=11)
        )
        self.status_label.grid(row=4, column=0, sticky="w", padx=16, pady=(0, 16))

        # ── Main ──
        main = ctk.CTkFrame(self, fg_color="#0a0a0f", corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # Chat area
        self.chat = ctk.CTkTextbox(
            main, state="disabled", wrap="word",
            fg_color=SURFACE, text_color=TEXT,
            font=ctk.CTkFont(family="SF Pro Text", size=14),
            corner_radius=0, border_width=0,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color="#2d3748"
        )
        self.chat.grid(row=0, column=0, sticky="nsew")

        # Text tags
        t = self.chat._textbox
        t.tag_configure("you", foreground=ACCENT, font=("SF Pro Text", 12, "bold"))
        t.tag_configure("ai",  foreground=PINK,   font=("SF Pro Text", 12, "bold"))
        t.tag_configure("msg", foreground=TEXT,    font=("SF Pro Text", 14))
        t.tag_configure("dim", foreground=MUTED,   font=("SF Pro Text", 13), justify="center")
        t.tag_configure("err", foreground="#ef4444", font=("SF Pro Text", 13))
        t.tag_configure("code", foreground="#56d4dd", font=("Courier New", 13),
                        background="#161b22")

        # Input bar
        bar = ctk.CTkFrame(main, fg_color=SURFACE, corner_radius=0)
        bar.grid(row=1, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        self.input_box = ctk.CTkTextbox(
            bar, height=72, fg_color="#161b22",
            border_color=BORDER, border_width=1,
            text_color=TEXT,
            font=ctk.CTkFont(size=14),
            corner_radius=12, wrap="word"
        )
        self.input_box.grid(row=0, column=0, padx=(16, 8), pady=14, sticky="ew")
        self.input_box.bind("<Return>", self._on_enter)

        self.send_btn = ctk.CTkButton(
            bar, text="Send", width=90, height=46,
            fg_color=PURPLE, hover_color="#5b21b6",
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=10, command=self._send
        )
        self.send_btn.grid(row=0, column=1, padx=(0, 16), pady=14)

        ctk.CTkLabel(
            bar, text="Enter to send  ·  Shift+Enter for new line",
            text_color="#334155", font=ctk.CTkFont(size=10)
        ).grid(row=1, column=0, columnspan=2, pady=(0, 8))

        self._show_welcome()

    def _show_welcome(self):
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.insert("end", "\n\n\n\n")
        self.chat.insert("end", "            🤖  AI Chatbot\n\n", "dim")
        self.chat.insert("end", "            Ask me anything — I'm running privately on your computer.\n\n", "dim")
        self.chat.insert("end", "            Try:  Write me a business email\n", "dim")
        self.chat.insert("end", "                   Explain machine learning simply\n", "dim")
        self.chat.insert("end", "                   Give me 5 business name ideas\n\n", "dim")
        self.chat.configure(state="disabled")

    def _new_chat(self):
        self.messages = []
        self.is_streaming = False
        self.send_btn.configure(state="normal", text="Send")
        self._show_welcome()
        self.input_box.focus()

    def _write(self, text, tag="msg"):
        self.chat.configure(state="normal")
        self.chat.insert("end", text, tag)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _on_enter(self, event):
        if not (event.state & 0x1):
            self._send()
            return "break"

    def _send(self):
        if self.is_streaming:
            return
        text = self.input_box.get("1.0", "end").strip()
        if not text:
            return

        self.input_box.delete("1.0", "end")
        self.messages.append({"role": "user", "content": text})

        # Clear welcome screen on first message
        content = self.chat.get("1.0", "end")
        if "Ask me anything" in content:
            self.chat.configure(state="normal")
            self.chat.delete("1.0", "end")
            self.chat.configure(state="disabled")

        self._write("\n  You\n", "you")
        self._write(f"  {text}\n\n", "msg")
        self._write("  AI\n", "ai")

        self.is_streaming = True
        self.send_btn.configure(state="disabled", text="  ●  ")

        threading.Thread(target=self._stream, daemon=True).start()

    def _stream(self):
        full = ""
        try:
            stream = ollama.chat(model=MODEL, messages=self.messages, stream=True)
            for chunk in stream:
                piece = chunk.message.content or ""
                full += piece
                self.after(0, lambda p=piece: self._write("  " + p if not full.replace(piece, "").endswith("\n") else p, "msg"))
        except Exception:
            self.after(0, lambda: self._write(
                "\n  ⚠  Could not reach Ollama.\n"
                "  Open a terminal and run:  ollama serve\n\n", "err"
            ))
            self.after(0, self._done)
            return

        self.messages.append({"role": "assistant", "content": full})
        self.after(0, lambda: self._write("\n\n", "msg"))
        self.after(0, self._done)

    def _done(self):
        self.is_streaming = False
        self.send_btn.configure(state="normal", text="Send")

    def _check_ollama(self):
        try:
            ollama.list()
            self.status_label.configure(text="● Online", text_color="#22c55e")
        except Exception:
            self.status_label.configure(text="● Offline", text_color="#ef4444")
            self.chat.configure(state="normal")
            self.chat.delete("1.0", "end")
            self.chat.insert("end", "\n\n\n")
            self.chat.insert("end", "  ⚠  Ollama is not running\n\n", "err")
            self.chat.insert("end", "  Open a terminal and type:\n\n", "dim")
            self.chat.insert("end", "       ollama serve\n\n", "ai")
            self.chat.insert("end", "  Then restart this app.\n\n", "dim")
            self.chat.configure(state="disabled")


if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()
