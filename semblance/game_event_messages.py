from abc import ABC, abstractmethod
from typing import Any


class AbstractGameEventMessage(ABC):
    value: Any = None  # the value for the message (not all messages will define this)
    generator: str = None  # The component responsible for creating this instance of the message
    name: str = None  # the name of the message (easier to compare than the message class)
    source: str = None  # the source of the game event message content


class ConsoleEventMessage(AbstractGameEventMessage):
    value: str = None  # The string of the console event
    name = "ConsoleEventMessage(?)"

    def __init__(self, message: str, source: str, generator: str) -> None:
        self.generator = generator
        self.value = message
        self.source = source

        self.name = self.name.replace("?", self.generator)

    def __str__(self) -> str:
        return f"({self.source}) {self.name}::'{self.value}'"
