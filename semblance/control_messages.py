from abc import ABC, abstractmethod
from typing import Any


class AbstractControlMessage(ABC):
    value: Any = None  # the value for the message (not all messages will define this)
    generator: str = None  # The component responsible for creating this instance of the message
    name: str = None  # the name of the message (easier to compare than the message class)


class KillMessage(AbstractControlMessage):
    name = "Kill"

    def __init__(self, generator: str) -> None:
        self.generator = generator


class DummyMessage(AbstractControlMessage):
    name = "NOPMessage"

    def __init__(self, generator: str) -> None:
        self.generator = generator