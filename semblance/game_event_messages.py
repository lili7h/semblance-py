import re

from abc import ABC
from typing import Any

from semblance.steam_id import SteamID, SteamIDException

# Capture groups: [killer] [victim] [weapon] [crit?]
CONSOLE_KILL_REX: re.Pattern = re.compile(r"^(.*)\skilled\s(.*)\swith\s(.*)\.(\s\(crit\))?$")
# Capture groups: [dead?] [team?] [author] [message]
CONSOLE_CHAT_REX: re.Pattern = re.compile(r"^(\*DEAD\*)?\s*(\(TEAM\))?\s*(.*)\s?:\s{1,2}(.*)$")


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


class ConsoleKillMessage(ConsoleEventMessage):
    killer: SteamID | str = None
    victim: SteamID | str = None
    weapon: str = None
    crit: bool = None

    def __init__(self, regex_match: re.Match, source: str, generator: str) -> None:
        super().__init__("Kill Event Regex Match", source, generator)
        _match_groups = regex_match.groups()
        self.killer = _match_groups[0]
        self.victim = _match_groups[1]
        self.weapon = _match_groups[2]
        self.crit = _match_groups[3] is not None

    def __str__(self) -> str:
        return (f"@[KillEvent: '{self.killer}' killed '{self.victim}' with '{self.weapon}' "
                f"{'(crit!)' if self.crit else ''}]")


class ConsoleChatMessage(ConsoleEventMessage):
    author: SteamID | str = None
    content: str = None
    team: bool = None
    dead: bool = None

    def __init__(self, regex_match: re.Match, source: str, generator: str) -> None:
        super().__init__("Chat Message Regex Match", source, generator)
        _match_groups = regex_match.groups()
        self.dead = _match_groups[0] is not None
        self.team = _match_groups[1] is not None
        self.author = _match_groups[2]
        self.content = _match_groups[3]

    def __str__(self):
        return (f"@[ChatMessage: '{self.author}'{' (dead)' if self.dead else ''} says '{self.content}' in "
                f"{'team' if self.team else 'all'} chat]")
