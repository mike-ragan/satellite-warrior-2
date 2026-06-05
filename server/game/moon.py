from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ResourceType(str, Enum):
    OFFENSIVE = "offensive"
    DEFENSIVE = "defensive"
    BASE = "base"


@dataclass
class Moon:
    id: str
    name: str
    resource_type: ResourceType
    resource_amount: int
    controlled_by: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "resource_type": self.resource_type.value,
            "resource_amount": self.resource_amount,
            "controlled_by": self.controlled_by,
        }
