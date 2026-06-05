from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional
import uuid


class ComponentType(str, Enum):
    HEAD = "head"
    TOROID = "toroid"
    GRABBER = "grabber"
    MISSILE = "missile"
    PLASMA_GUN = "plasma_gun"
    ARMOR = "armor"
    ECM = "ecm"
    SHIELD = "shield"


COMPONENT_COSTS: dict[ComponentType, int] = {
    ComponentType.HEAD: 100,
    ComponentType.TOROID: 50,
    ComponentType.GRABBER: 75,
    ComponentType.MISSILE: 90,
    ComponentType.PLASMA_GUN: 80,
    ComponentType.ARMOR: 60,
    ComponentType.ECM: 65,
    ComponentType.SHIELD: 70,
}

COMPONENT_SELLERS: dict[str, list[ComponentType]] = {
    "offensive": [ComponentType.GRABBER, ComponentType.MISSILE, ComponentType.PLASMA_GUN],
    "defensive": [ComponentType.ARMOR, ComponentType.ECM, ComponentType.SHIELD],
    "base": [ComponentType.HEAD, ComponentType.TOROID],
}

MAX_COMPONENTS_PER_HEAD = 7


@dataclass
class Satellite:
    owner_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    components: List[ComponentType] = field(default_factory=lambda: [ComponentType.HEAD])
    moon_id: Optional[str] = None
    stability: int = 100

    def can_add_component(self) -> bool:
        heads = self.components.count(ComponentType.HEAD)
        return len(self.components) < heads * (MAX_COMPONENTS_PER_HEAD + 1)

    def add_component(self, component: ComponentType) -> bool:
        if component == ComponentType.HEAD or self.can_add_component():
            self.components.append(component)
            return True
        return False

    def is_mobile(self) -> bool:
        return ComponentType.TOROID in self.components

    def attack_power(self) -> dict:
        return {
            "close": self.components.count(ComponentType.GRABBER),
            "medium": self.components.count(ComponentType.PLASMA_GUN),
            "long": self.components.count(ComponentType.MISSILE),
        }

    def defense_power(self) -> dict:
        return {
            "close": self.components.count(ComponentType.ARMOR),
            "medium": self.components.count(ComponentType.SHIELD),
            "long": self.components.count(ComponentType.ECM),
        }

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "components": [c.value for c in self.components],
            "moon_id": self.moon_id,
            "stability": self.stability,
        }
