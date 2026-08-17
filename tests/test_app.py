import pytest
from app import app, socketio, online_users, init_db, load_history, save_message, DB_PATH
import os


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    """Use a fresh temp database and clear in-memory state before each test."""
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr("app.DB_PATH", test_db)
    online_users.clear()
    init_db()
    yield
    online_users.clear()


@pytest.fixture
def client():
    return socketio.test_client(app)


@pytest.fixture
def two_clients():
    a = socketio.test_client(app)
    b = socketio.test_client(app)
    return a, b


# --- Register ---

def test_register_adds_user_to_online_list(client):
    client.emit("register", {"user": "Alice"})
    received = client.get_received()
    users_event = next(e for e in received if e["name"] == "users")
    assert "Alice" in users_event["args"][0]


def test_register_notifies_all_connected_clients(two_clients):
    a, b = two_clients
    a.emit("register", {"user": "Alice"})
    b.emit("register", {"user": "Bob"})

    b_events = [e for e in b.get_received() if e["name"] == "users"]
    assert len(b_events) == 2
    assert "Bob" in b_events[-1]["args"][0]
    assert "Alice" in b_events[-1]["args"][0]


def test_duplicate_name_is_rejected(two_clients):
    a, b = two_clients
    a.emit("register", {"user": "Alice"})
    b.emit("register", {"user": "Alice"})

    received = b.get_received()
    error_event = next((e for e in received if e["name"] == "register_error"), None)
    assert error_event is not None
    assert "Alice" in error_event["args"][0]["message"]


def test_changing_name_frees_old_name(client, two_clients):
    a, b = two_clients
    a.emit("register", {"user": "Sandra"})
    a.emit("register", {"user": "Jesus"})  # Sandra changes name
    # Sandra should now be available
    b.emit("register", {"user": "Sandra"})
    assert online_users.get("Sandra") is not None
    assert online_users.get("Jesus") is not None


def test_duplicate_name_does_not_overwrite_original(two_clients):
    a, b = two_clients
    a.emit("register", {"user": "Alice"})
    original_sid = online_users["Alice"]
    b.emit("register", {"user": "Alice"})
    assert online_users["Alice"] == original_sid


# --- Disconnect ---

def test_disconnect_removes_user(client):
    client.emit("register", {"user": "Alice"})
    client.disconnect()
    assert "Alice" not in online_users


# --- Public messages ---

def test_message_is_broadcast_to_all(two_clients):
    a, b = two_clients
    a.emit("register", {"user": "Alice"})
    b.emit("register", {"user": "Bob"})
    b.get_received()

    a.emit("message", {"user": "Alice", "text": "hello"})
    received = b.get_received()
    msg_event = next(e for e in received if e["name"] == "message")
    # broadcast args come as a dict directly, not wrapped in a list
    assert msg_event["args"]["text"] == "hello"


def test_message_is_stored_in_history(client):
    client.emit("message", {"user": "Alice", "text": "hello"})
    history = load_history()
    assert len(history) == 1
    assert history[0]["text"] == "hello"


def test_history_is_sent_on_connect(client):
    save_message("Alice", "old message")
    new_client = socketio.test_client(app)
    received = new_client.get_received()
    history_event = next(e for e in received if e["name"] == "history")
    assert history_event["args"][0][0]["text"] == "old message"


def test_history_capped_at_50_messages(client):
    for i in range(60):
        client.emit("message", {"user": "Alice", "text": f"msg {i}"})
    history = load_history()
    assert len(history) == 50
    assert history[0]["text"] == "msg 10"


# --- Direct messages ---

def test_dm_is_received_by_recipient(two_clients):
    a, b = two_clients
    a.emit("register", {"user": "Alice"})
    b.emit("register", {"user": "Bob"})
    b.get_received()

    a.emit("dm", {"from": "Alice", "to": "Bob", "text": "hey"})
    received = b.get_received()
    dm_event = next(e for e in received if e["name"] == "dm")
    assert dm_event["args"][0]["text"] == "hey"


def test_dm_is_echoed_back_to_sender(two_clients):
    a, b = two_clients
    a.emit("register", {"user": "Alice"})
    b.emit("register", {"user": "Bob"})
    a.get_received()

    a.emit("dm", {"from": "Alice", "to": "Bob", "text": "hey"})
    received = a.get_received()
    dm_event = next(e for e in received if e["name"] == "dm")
    assert dm_event["args"][0]["text"] == "hey"


def test_dm_is_not_received_by_third_party(two_clients):
    a, b = two_clients
    c = socketio.test_client(app)
    a.emit("register", {"user": "Alice"})
    b.emit("register", {"user": "Bob"})
    c.emit("register", {"user": "Carol"})
    c.get_received()

    a.emit("dm", {"from": "Alice", "to": "Bob", "text": "secret"})
    received = c.get_received()
    assert not any(e["name"] == "dm" for e in received)


def test_dm_to_offline_user_does_not_crash(client):
    client.emit("register", {"user": "Alice"})
    client.get_received()
    client.emit("dm", {"from": "Alice", "to": "Bob", "text": "hey"})
