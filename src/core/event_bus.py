from collections import defaultdict
from typing import Any, Callable


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable[[Any], None]) -> None:
        self._handlers[event].append(handler)

    def publish(self, event: str, payload: Any = None) -> None:
        for handler in self._handlers[event]:
            handler(payload)


event_bus = EventBus()
