from iip.events import Event, EventBus


def test_event_creation():
    event = Event(type="test.event", payload={"data": "test"})
    assert event.type == "test.event"
    assert event.payload["data"] == "test"


def test_subscribe():
    EventBus.clear()
    calls = []

    def handler(event):
        calls.append(1)

    EventBus.subscribe("simple.test", handler)
    assert EventBus.subscriber_count("simple.test") == 1
    EventBus.clear()


def test_unsubscribe():
    EventBus.clear()

    def handler(event):
        pass

    EventBus.subscribe("unsub.test", handler)
    EventBus.unsubscribe("unsub.test", handler)
    assert EventBus.subscriber_count("unsub.test") == 0
    EventBus.clear()
