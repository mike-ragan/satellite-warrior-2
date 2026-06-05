import uuid
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .satellite import Satellite, ComponentType, COMPONENT_COSTS
from .moon import Moon, ResourceType
from .aliens import AlienOffer, generate_offer
from .combat import run_battle


class GamePhase(str, Enum):
    WAITING = "waiting"
    TRADING = "trading"
    DEPLOYMENT = "deployment"
    COMBAT = "combat"
    GAME_OVER = "game_over"


@dataclass
class Player:
    player_id: str
    name: str
    cash: int = 500
    satellites: List[Satellite] = field(default_factory=list)
    ready: bool = False

    def get_satellite(self, sat_id: str) -> Optional[Satellite]:
        return next((s for s in self.satellites if s.id == sat_id), None)

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "name": self.name,
            "cash": self.cash,
            "satellites": [s.to_dict() for s in self.satellites],
            "ready": self.ready,
        }


MOON_CONFIGS = [
    ("Alpha",   ResourceType.OFFENSIVE, 3),
    ("Beta",    ResourceType.DEFENSIVE, 2),
    ("Gamma",   ResourceType.BASE,      4),
    ("Delta",   ResourceType.OFFENSIVE, 2),
    ("Epsilon", ResourceType.DEFENSIVE, 3),
]


class GameEngine:
    def __init__(self):
        self.game_id: str = str(uuid.uuid4())[:6].upper()
        self.players: Dict[str, Player] = {}
        self.phase: GamePhase = GamePhase.WAITING
        self.turn_number: int = 0
        self.moons: List[Moon] = [
            Moon(id=f"m{i}", name=name, resource_type=rt, resource_amount=amt)
            for i, (name, rt, amt) in enumerate(MOON_CONFIGS)
        ]
        self.alien_offer: Optional[AlienOffer] = None
        self.combat_log: List[dict] = []

    # ------------------------------------------------------------------ setup

    def add_player(self, player_id: str, name: str) -> bool:
        if len(self.players) >= 2:
            return False
        player = Player(player_id=player_id, name=name)
        player.satellites.append(Satellite(owner_id=player_id))
        self.players[player_id] = player
        if len(self.players) == 2:
            self._start()
        return True

    def _start(self) -> None:
        self.turn_number = 1
        self._begin_trading()

    # ----------------------------------------------------------------- phases

    def _begin_trading(self) -> None:
        self.phase = GamePhase.TRADING
        self.alien_offer = generate_offer()
        self.combat_log = []

    def _advance(self) -> None:
        if self.phase == GamePhase.TRADING:
            self.phase = GamePhase.DEPLOYMENT

        elif self.phase == GamePhase.DEPLOYMENT:
            self._resolve_combat()          # sets phase to COMBAT
            self._collect_resources()
            if self._check_winner():
                self.phase = GamePhase.GAME_OVER

        elif self.phase == GamePhase.COMBAT:
            self.turn_number += 1
            self._begin_trading()

    # ----------------------------------------------------------------- actions

    def buy(self, player_id: str, component: str, qty: int) -> dict:
        if self.phase != GamePhase.TRADING:
            return {"ok": False, "error": "Not in trading phase"}
        player = self.players.get(player_id)
        if not player:
            return {"ok": False, "error": "Player not found"}
        if not self.alien_offer:
            return {"ok": False, "error": "No alien offer available"}

        try:
            comp = ComponentType(component)
        except ValueError:
            return {"ok": False, "error": f"Unknown component: {component}"}

        if comp not in self.alien_offer.components:
            return {"ok": False, "error": "This alien doesn't sell that"}

        cost = self.alien_offer.prices[comp] * qty
        if player.cash < cost:
            return {"ok": False, "error": f"Need {cost} cash, have {player.cash}"}

        player.cash -= cost
        sat = player.satellites[0]
        for _ in range(qty):
            if not sat.add_component(comp):
                # Satellite is full — create a new head automatically if buying a HEAD
                if comp == ComponentType.HEAD:
                    new_sat = Satellite(owner_id=player_id)
                    player.satellites.append(new_sat)
                    sat = new_sat
                else:
                    player.cash += self.alien_offer.prices[comp] * (qty - _)
                    return {"ok": False, "error": "Satellite is full — buy a HEAD first to expand"}

        return {"ok": True, "cash": player.cash}

    def deploy(self, player_id: str, satellite_id: str, moon_id: str) -> dict:
        if self.phase != GamePhase.DEPLOYMENT:
            return {"ok": False, "error": "Not in deployment phase"}
        player = self.players.get(player_id)
        if not player:
            return {"ok": False, "error": "Player not found"}

        sat = player.get_satellite(satellite_id)
        if not sat:
            return {"ok": False, "error": "Satellite not found"}
        if not sat.is_mobile() and sat.moon_id is None:
            return {"ok": False, "error": "Needs a TOROID to move from reserve"}

        moon = next((m for m in self.moons if m.id == moon_id), None)
        if not moon:
            return {"ok": False, "error": "Moon not found"}

        sat.moon_id = moon_id
        return {"ok": True}

    def ready(self, player_id: str) -> dict:
        player = self.players.get(player_id)
        if not player:
            return {"ok": False, "error": "Player not found"}

        player.ready = True
        if all(p.ready for p in self.players.values()):
            for p in self.players.values():
                p.ready = False
            self._advance()

        return {"ok": True}

    # --------------------------------------------------------- internal logic

    def _resolve_combat(self) -> None:
        self.phase = GamePhase.COMBAT
        self.combat_log = []

        by_moon: Dict[str, List[Satellite]] = {}
        for player in self.players.values():
            for sat in player.satellites:
                if sat.moon_id:
                    by_moon.setdefault(sat.moon_id, []).append(sat)

        for moon_id, sats in by_moon.items():
            if len(sats) == 2 and sats[0].owner_id != sats[1].owner_id:
                result = run_battle(sats[0], sats[1])
                self.combat_log.append({"moon_id": moon_id, **result})

        # Remove destroyed satellites
        for player in self.players.values():
            player.satellites = [s for s in player.satellites if s.stability > 0]

    def _collect_resources(self) -> None:
        for moon in self.moons:
            occupants = [
                player for player in self.players.values()
                if any(s.moon_id == moon.id for s in player.satellites)
            ]
            if len(occupants) == 1:
                moon.controlled_by = occupants[0].player_id
                occupants[0].cash += moon.resource_amount * 25

    def _check_winner(self) -> bool:
        for player in self.players.values():
            if not player.satellites:
                return True
        player_ids = list(self.players.keys())
        for pid in player_ids:
            if all(m.controlled_by == pid for m in self.moons):
                return True
        return False

    def get_winner_name(self) -> Optional[str]:
        for player in self.players.values():
            if not player.satellites:
                other = next(p for p in self.players.values() if p.player_id != player.player_id)
                return other.name
        for player in self.players.values():
            if all(m.controlled_by == player.player_id for m in self.moons):
                return player.name
        return None

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "phase": self.phase.value,
            "turn_number": self.turn_number,
            "players": {pid: p.to_dict() for pid, p in self.players.items()},
            "moons": [m.to_dict() for m in self.moons],
            "alien_offer": self.alien_offer.to_dict() if self.alien_offer else None,
            "combat_log": self.combat_log,
            "winner": self.get_winner_name() if self.phase == GamePhase.GAME_OVER else None,
        }
