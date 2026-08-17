import pytest
from app import app, socketio, history, online_users


@pytest.fixture(autouse=True)
def reset_state():
    """Clear server state before each test so tests don't bleed into each other."""
    history.clear()
    online_users.clear()
    yield


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
    # Bob should have seen Alice join, then himself join
    assert len(b_events) == 2
    assert "Bob" in b_events[-1]["args"][0]
    assert "Alice" in b_events[-1]["args"][0]


def test_duplicate_name_overwrites_previous(two_clients):
    a, b = two_clients
    a.emit("register", {"user": "Alice"})
    b.emit("register", {"user": "Alice"})
    assert len(online_users) == 1  # only one entry for "Alice"


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
    b.get_received()  # clear B's queue

    a.emit("message", {"user": "Alice", "text": "hello"})
    received = b.get_received()
    msg_event = next(e for e in received if e["name"] == "message")
    # broadcast args come as a dict directly, not wrapped in a list
    assert msg_event["args"]["text"] == "hello"


def test_message_is_stored_in_history(client):
    client.emit("message", {"user": "Alice", "text": "hello"})
    assert len(history) == 1
    assert history[0]["text"] == "hello"


def test_history_is_sent_on_connect(client):
    history.append({"user": "Alice", "text": "old message"})
    new_client = socketio.test_client(app)
    received = new_client.get_received()
    history_event = next(e for e in received if e["name"] == "history")
    assert history_event["args"][0][0]["text"] == "old message"


def test_history_capped_at_50_messages(client):
    for i in range(60):
        client.emit("message", {"user": "Alice", "text": f"msg {i}"})
    assert len(history) == 50
    assert history[0]["text"] == "msg 10"  # oldest 10 were dropped


# --- Direct messages ---

def test_dm_is_received_by_recipient(two_clients):
    a, b = two_clients
    a.emit("register", {"user": "Alice"})
    b.emit("register", {"user": "Bob"})
    b.get_received()  # clear queue

    a.emit("dm", {"from": "Alice", "to": "Bob", "text": "hey"})
    received = b.get_received()
    dm_event = next(e for e in received if e["name"] == "dm")
    assert dm_event["args"][0]["text"] == "hey"


def test_dm_is_echoed_back_to_sender(two_clients):
    a, b = two_clients
    a.emit("register", {"user": "Alice"})
    b.emit("register", {"user": "Bob"})
    a.get_received()  # clear queue

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
    c.get_received()  # clear queue

    a.emit("dm", {"from": "Alice", "to": "Bob", "text": "secret"})
    received = c.get_received()
    dm_events = [e for e in received if e["name"] == "dm"]
    assert len(dm_events) == 0


def test_dm_to_offline_user_does_not_crash(client):
    client.emit("register", {"user": "Alice"})
    client.get_received()
    # Bob is not connected — should not raise an exception
    client.emit("dm", {"from": "Alice", "to": "Bob", "text": "hey"})
