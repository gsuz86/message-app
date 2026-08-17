# Flask: the web framework — handles HTTP routes and serves the HTML page.
# render_template: reads a file from the /templates folder and returns it as an HTTP response.
from flask import Flask, render_template
# Flask-SocketIO: adds WebSocket support on top of Flask.
# SocketIO: the main object that manages real-time connections.
# emit: sends an event (with data) back to clients.
from flask_socketio import SocketIO, emit

# Create the Flask application instance.
# __name__ tells Flask where to look for templates/static files (relative to this file).
app = Flask(__name__)

# Wrap the Flask app with SocketIO to enable WebSocket communication.
# cors_allowed_origins="*" lets clients from any origin connect.
# (Fine for local testing; you'd restrict this in production.)
socketio = SocketIO(app, cors_allowed_origins="*")


# HTTP route: when a browser visits http://localhost:3000/, serve index.html.
@app.route("/")
def index():
    return render_template("index.html")


# WebSocket event handler: runs whenever a client emits an event named "message".
# `data` is the payload sent by the client (in our case: { user, text }).
@socketio.on("message")
def handle_message(data):
    # Re-emit the "message" event to ALL connected clients (including the sender).
    # This is what makes the chat real-time: every browser tab receives it instantly.
    emit("message", data, broadcast=True)


# Standard Python entry point: only runs when you execute `python app.py` directly.
if __name__ == "__main__":
    # socketio.run starts the server (not app.run) because we need WebSocket support.
    # host="0.0.0.0" -> listen on all network interfaces (accessible from other devices on your LAN).
    # port=3000     -> the port to listen on.
    # debug=True    -> auto-reload on code changes + show detailed errors.
    socketio.run(app, host="0.0.0.0", port=3000, debug=True, allow_unsafe_werkzeug=True)
