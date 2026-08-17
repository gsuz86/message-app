# Flask: the web framework — handles HTTP routes and serves the HTML page.
# render_template: reads a file from the /templates folder and returns it as an HTTP response.
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

MAX_HISTORY = 50
history = []

# Maps username -> socket id so we can target specific people.
online_users = {}


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("connect")
def handle_connect():
    emit("history", history)


# Client emits "register" after picking a name so the server knows who they are.
@socketio.on("register")
def handle_register(data):
    online_users[data["user"]] = request.sid
    # Broadcast the updated user list to everyone.
    emit("users", list(online_users.keys()), broadcast=True)


@socketio.on("disconnect")
def handle_disconnect():
    # Remove the user that just left and notify everyone.
    user = next((u for u, sid in online_users.items() if sid == request.sid), None)
    if user:
        del online_users[user]
        emit("users", list(online_users.keys()), broadcast=True)


@socketio.on("message")
def handle_message(data):
    history.append(data)
    if len(history) > MAX_HISTORY:
        history.pop(0)
    emit("message", data, broadcast=True)


# Direct message: only delivered to sender and recipient.
@socketio.on("dm")
def handle_dm(data):
    recipient_sid = online_users.get(data["to"])
    payload = {"from": data["from"], "to": data["to"], "text": data["text"]}
    if recipient_sid:
        emit("dm", payload, to=recipient_sid)
    # Always echo back to sender so they see their own DM.
    emit("dm", payload, to=request.sid)


# Standard Python entry point: only runs when you execute `python app.py` directly.
if __name__ == "__main__":
    # socketio.run starts the server (not app.run) because we need WebSocket support.
    # host="0.0.0.0" -> listen on all network interfaces (accessible from other devices on your LAN).
    # port=3000     -> the port to listen on.
    # debug=True    -> auto-reload on code changes + show detailed errors.
    socketio.run(app, host="0.0.0.0", port=3000, debug=True, allow_unsafe_werkzeug=True)
