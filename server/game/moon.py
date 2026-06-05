from dataclasses import dataclass
from typing import Optional


@dataclass
class Moon:
    id: str
    name: str
    component_yield: str   # which component this moon produces each turn
    yield_per_turn: int    # units produced when controlled
    controlled_by: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "component_yield": self.component_yield,
            "yield_per_turn": self.yield_per_turn,
            "controlled_by": self.controlled_by,
        }
