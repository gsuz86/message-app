# Flask: the web framework — handles HTTP routes and serves the HTML page.
# render_template: reads a file from the /templates folder and returns it as an HTTP response.
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

MAX_HISTORY = 50
history = []


@app.route("/")
def index():
    return render_template("index.html")


# When a client connects, send them the existing message history.
@socketio.on("connect")
def handle_connect():
    emit("history", history)


@socketio.on("message")
def handle_message(data):
    history.append(data)
    if len(history) > MAX_HISTORY:
        history.pop(0)
    emit("message", data, broadcast=True)


# Standard Python entry point: only runs when you execute `python app.py` directly.
if __name__ == "__main__":
    # socketio.run starts the server (not app.run) because we need WebSocket support.
    # host="0.0.0.0" -> listen on all network interfaces (accessible from other devices on your LAN).
    # port=3000     -> the port to listen on.
    # debug=True    -> auto-reload on code changes + show detailed errors.
    socketio.run(app, host="0.0.0.0", port=3000, debug=True, allow_unsafe_werkzeug=True)
