from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any


class ActuatorTypes(Enum):
    NORMAL = auto()
    ROTARY = auto()
    LINEAR = auto()
    ANY = auto()


class AbstractDeviceMessage(ABC):
    target: Any = None  # abstract definition of a 'target' for this given value
    value: Any = None  # the value for the message (not all messages will define this)
    generator: str = None  # The component responsible for creating this instance of the message
    name: str = None  # the name of the message (easier to compare than the message class)


class NormalActuatorSetIntensityMessage(AbstractDeviceMessage):
    target: ActuatorTypes = ActuatorTypes.NORMAL
    name = "SetNormalActuatorIntensity(?)"

    def __init__(self, value: float, generator: str) -> None:
        self.value = value
        self.generator = generator
        self.name = self.name.replace("?", f"{value}")


class NormalActuatorGetIntensityMessage(AbstractDeviceMessage):
    target: ActuatorTypes = ActuatorTypes.ANY
    name = "GetNormalActuatorIntensity"

    def __init__(self, value: float, generator: str) -> None:
        self.value = value
        self.generator = generator