import random
from dataclasses import dataclass
from typing import List
from .satellite import ComponentType, COMPONENT_SELLERS, COMPONENT_COSTS


@dataclass
class AlienOffer:
    alien_type: str
    components: List[ComponentType]
    prices: dict[ComponentType, int]

    def to_dict(self) -> dict:
        return {
            "alien_type": self.alien_type,
            "components": [c.value for c in self.components],
            "prices": {c.value: p for c, p in self.prices.items()},
        }


def generate_offer() -> AlienOffer:
    alien_type = random.choice(["offensive", "defensive", "base"])
    components = COMPONENT_SELLERS[alien_type]
    prices = {c: int(COMPONENT_COSTS[c] * random.uniform(0.8, 1.2)) for c in components}
    return AlienOffer(alien_type=alien_type, components=components, prices=prices)
