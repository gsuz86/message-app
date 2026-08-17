import sqlite3
from flask import Flask, render_template, request, g
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

MAX_HISTORY = 50
online_users = {}

DB_PATH = "chat.db"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    with app.app_context():
        db = sqlite3.connect(DB_PATH)
        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                text TEXT NOT NULL,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()
        db.close()


def load_history():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT user, text FROM messages ORDER BY id DESC LIMIT ?", (MAX_HISTORY,)
    ).fetchall()
    db.close()
    return [{"user": r["user"], "text": r["text"]} for r in reversed(rows)]


def save_message(user, text):
    db = sqlite3.connect(DB_PATH)
    db.execute("INSERT INTO messages (user, text) VALUES (?, ?)", (user, text))
    # Keep only the last MAX_HISTORY rows to avoid unbounded growth.
    db.execute("""
        DELETE FROM messages WHERE id NOT IN (
            SELECT id FROM messages ORDER BY id DESC LIMIT ?
        )
    """, (MAX_HISTORY,))
    db.commit()
    db.close()


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("connect")
def handle_connect():
    emit("history", load_history())


@socketio.on("register")
def handle_register(data):
    name = data["user"]
    if name in online_users:
        emit("register_error", {"message": f'"{name}" is already taken. Pick another.'})
        return
    online_users[name] = request.sid
    emit("users", list(online_users.keys()), broadcast=True)


@socketio.on("disconnect")
def handle_disconnect():
    user = next((u for u, sid in online_users.items() if sid == request.sid), None)
    if user:
        del online_users[user]
        emit("users", list(online_users.keys()), broadcast=True)


@socketio.on("message")
def handle_message(data):
    save_message(data["user"], data["text"])
    emit("message", data, broadcast=True)


@socketio.on("dm")
def handle_dm(data):
    recipient_sid = online_users.get(data["to"])
    payload = {"from": data["from"], "to": data["to"], "text": data["text"]}
    if recipient_sid:
        emit("dm", payload, to=recipient_sid)
    emit("dm", payload, to=request.sid)


if __name__ == "__main__":
    init_db()
    socketio.run(app, host="0.0.0.0", port=3000, debug=True, allow_unsafe_werkzeug=True)
