import unittest
from core.events.event_bus import EventBus

class EventBusTests(unittest.TestCase):
    def test_publish_subscribe(self):
        bus = EventBus()
        received = []
        bus.subscribe("x", lambda event: received.append(event.payload))
        bus.publish("x", 42)
        self.assertEqual(received, [42])

if __name__ == "__main__":
    unittest.main()
