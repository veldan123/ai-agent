from flask import Flask, render_template, request, Response, stream_with_context
import ollama, json

app = Flask(__name__)
MODEL = "qwen2.5:7b"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    messages = request.json.get("messages", [])

    def generate():
        stream = ollama.chat(model=MODEL, messages=messages, stream=True)
        for chunk in stream:
            content = chunk.message.content or ""
            if content:
                yield f"data: {json.dumps({'content': content})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

if __name__ == "__main__":
    print("\n  ✓ Chatbot running → open http://localhost:8080 in your browser\n")
    app.run(debug=False, host="127.0.0.1", port=8080)
