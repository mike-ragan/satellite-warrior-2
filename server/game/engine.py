from __future__ import annotations
import uuid
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .satellite import Satellite, ComponentType, COMPONENT_COSTS
from .moon import Moon
from .aliens import AlienOffer, generate_offer

SELL_RATE = 0.55  # sell components at 55 % of buy price

MOON_CONFIGS = [
    ("Alpha",   "plasma_gun", 2),
    ("Beta",    "shield",     2),
    ("Gamma",   "armor",      3),
    ("Delta",   "missile",    2),
    ("Epsilon", "grabber",    2),
]


class GamePhase(str, Enum):
    WAITING    = "waiting"
    TRADING    = "trading"
    DEPLOYMENT = "deployment"
    COMBAT     = "combat"
    GAME_OVER  = "game_over"


@dataclass
class Player:
    player_id: str
    name:      str
    cash:      int  = 500
    is_ai:     bool = False
    satellites: List[Satellite]  = field(default_factory=list)
    inventory:  Dict[str, int]   = field(default_factory=dict)
    ready:     bool = False

    # ── Inventory helpers ─────────────────────────────────────────────────

    def add_inv(self, comp: str, qty: int = 1) -> None:
        self.inventory[comp] = self.inventory.get(comp, 0) + qty

    def take_inv(self, comp: str, qty: int = 1) -> bool:
        if self.inventory.get(comp, 0) < qty:
            return False
        self.inventory[comp] -= qty
        if self.inventory[comp] == 0:
            del self.inventory[comp]
        return True

    def get_satellite(self, sat_id: str) -> Optional[Satellite]:
        return next((s for s in self.satellites if s.id == sat_id), None)

    def to_dict(self) -> dict:
        return {
            "player_id":  self.player_id,
            "name":       self.name,
            "cash":       self.cash,
            "is_ai":      self.is_ai,
            "satellites": [s.to_dict() for s in self.satellites],
            "inventory":  dict(self.inventory),
            "ready":      self.ready,
        }


class GameEngine:
    def __init__(self) -> None:
        self.game_id:          str = str(uuid.uuid4())[:6].upper()
        self.players:          Dict[str, Player] = {}
        self.phase:            GamePhase = GamePhase.WAITING
        self.turn_number:      int = 0
        self.alien_offer:      Optional[AlienOffer] = None
        self.pending_conflicts: List[dict] = []
        self.moons: List[Moon] = [
            Moon(id=f"m{i}", name=name, component_yield=comp, yield_per_turn=amt)
            for i, (name, comp, amt) in enumerate(MOON_CONFIGS)
        ]

    # ── Setup ─────────────────────────────────────────────────────────────

    def add_player(self, player_id: str, name: str) -> bool:
        if len(self.players) >= 2:
            return False
        p = Player(player_id=player_id, name=name)
        p.satellites.append(Satellite(owner_id=player_id))
        self.players[player_id] = p
        if len(self.players) == 2:
            self._begin_trading()
        return True

    def add_ai_player(self, name: str = "Computer") -> str:
        ai_id = str(uuid.uuid4())
        p = Player(player_id=ai_id, name=name, is_ai=True)
        p.satellites.append(Satellite(owner_id=ai_id))
        self.players[ai_id] = p
        if len(self.players) == 2:
            self._begin_trading()
        return ai_id

    # ── Actions ───────────────────────────────────────────────────────────

    def buy(self, player_id: str, component: str, qty: int) -> dict:
        """Buy from alien offer → goes to inventory."""
        if self.phase != GamePhase.TRADING:
            return {"ok": False, "error": "Not in trading phase"}
        player = self.players.get(player_id)
        if not player:
            return {"ok": False, "error": "Player not found"}
        if not self.alien_offer:
            return {"ok": False, "error": "No alien offer this turn"}
        try:
            comp = ComponentType(component)
        except ValueError:
            return {"ok": False, "error": f"Unknown component: {component}"}
        if comp not in self.alien_offer.components:
            return {"ok": False, "error": "Alien doesn't carry that"}
        cost = self.alien_offer.prices[comp] * qty
        if player.cash < cost:
            return {"ok": False, "error": f"Need {cost} credits, have {player.cash}"}
        player.cash -= cost
        player.add_inv(component, qty)
        return {"ok": True}

    def sell(self, player_id: str, component: str, qty: int = 1) -> dict:
        """Sell inventory component for credits."""
        if self.phase != GamePhase.TRADING:
            return {"ok": False, "error": "Not in trading phase"}
        player = self.players.get(player_id)
        if not player:
            return {"ok": False, "error": "Player not found"}
        if not player.take_inv(component, qty):
            return {"ok": False, "error": f"Not enough {component} in inventory"}
        try:
            base = COMPONENT_COSTS.get(ComponentType(component), 50)
        except ValueError:
            base = 50
        earned = int(base * SELL_RATE * qty)
        player.cash += earned
        return {"ok": True, "earned": earned}

    def build(self, player_id: str, component: str, satellite_id: str = "") -> dict:
        """Move component from inventory onto a satellite."""
        if self.phase != GamePhase.TRADING:
            return {"ok": False, "error": "Not in trading phase"}
        player = self.players.get(player_id)
        if not player:
            return {"ok": False, "error": "Player not found"}
        if not player.take_inv(component, 1):
            return {"ok": False, "error": f"No {component} in inventory"}
        try:
            comp_type = ComponentType(component)
        except ValueError:
            player.add_inv(component, 1)
            return {"ok": False, "error": f"Unknown component: {component}"}

        # If buying a HEAD with no existing satellite, spawn one
        if comp_type == ComponentType.HEAD and not player.satellites:
            sat = Satellite(owner_id=player_id)
            player.satellites.append(sat)
            return {"ok": True}

        sat = player.get_satellite(satellite_id) if satellite_id else None
        if sat is None and player.satellites:
            sat = player.satellites[0]
        if sat is None:
            player.add_inv(component, 1)
            return {"ok": False, "error": "No satellite to attach to"}

        if not sat.add_component(comp_type):
            player.add_inv(component, 1)
            return {"ok": False, "error": "Satellite is full — buy a HEAD to expand"}
        return {"ok": True}

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
        if player.is_ai:
            return {"ok": False, "error": "Cannot set ready for AI player"}
        player.ready = True
        if all(p.ready for p in self.players.values()):
            for p in self.players.values():
                p.ready = False
            self._advance()
        return {"ok": True}

    def resolve_combat(self, winner_id: str, moon_id: str) -> None:
        """Apply real-time combat result then advance."""
        loser_id = next((pid for pid in self.players if pid != winner_id), None)
        if loser_id:
            self.players[loser_id].satellites = [
                s for s in self.players[loser_id].satellites if s.moon_id != moon_id
            ]
        for moon in self.moons:
            if moon.id == moon_id:
                moon.controlled_by = winner_id
        self.pending_conflicts = [c for c in self.pending_conflicts if c.get("moon_id") != moon_id]
        if not self.pending_conflicts:
            if not self._check_winner():
                self._collect_resources()
                self.turn_number += 1
                self._begin_trading()

    # ── State ─────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "game_id":     self.game_id,
            "phase":       self.phase.value,
            "turn_number": self.turn_number,
            "winner":      self._winner_name(),
            "players":     {pid: p.to_dict() for pid, p in self.players.items()},
            "moons":       [m.to_dict() for m in self.moons],
            "alien_offer": self.alien_offer.to_dict() if self.alien_offer else None,
        }

    # ── Internal ──────────────────────────────────────────────────────────

    def _begin_trading(self) -> None:
        self.phase       = GamePhase.TRADING
        self.alien_offer = generate_offer()
        for p in self.players.values():
            p.ready = False
        self._ai_act()

    def _advance(self) -> None:
        if self.phase == GamePhase.TRADING:
            self.phase = GamePhase.DEPLOYMENT
            self._ai_act()

        elif self.phase == GamePhase.DEPLOYMENT:
            conflicts = self._find_conflicts()
            self.pending_conflicts = conflicts
            if conflicts:
                self.phase = GamePhase.COMBAT
                # main.py detects this and launches CombatSession
            else:
                if not self._check_winner():
                    self._collect_resources()
                    self.turn_number += 1
                    self._begin_trading()

    def _find_conflicts(self) -> List[dict]:
        by_moon: Dict[str, Dict[str, Satellite]] = {}
        for p in self.players.values():
            for sat in p.satellites:
                if sat.moon_id:
                    by_moon.setdefault(sat.moon_id, {})[p.player_id] = sat
        conflicts = []
        for moon_id, sats in by_moon.items():
            if len(sats) >= 2:
                items = list(sats.items())
                conflicts.append({
                    "moon_id": moon_id,
                    "sat_a":   {"player_id": items[0][0], **items[0][1].to_dict()},
                    "sat_b":   {"player_id": items[1][0], **items[1][1].to_dict()},
                })
        return conflicts

    def _collect_resources(self) -> None:
        for moon in self.moons:
            if moon.controlled_by:
                player = self.players.get(moon.controlled_by)
                if player:
                    player.add_inv(moon.component_yield, moon.yield_per_turn)

    def _check_winner(self) -> bool:
        for pid, player in self.players.items():
            if not player.satellites:
                opp = next(p for p in self.players.values() if p.player_id != pid)
                self._set_winner(opp.name)
                return True
        controllers = {m.controlled_by for m in self.moons if m.controlled_by}
        if len(controllers) == 1 and len({m.controlled_by for m in self.moons}) == len(self.moons):
            pid = controllers.pop()
            self._set_winner(self.players[pid].name)
            return True
        return False

    def _set_winner(self, name: str) -> None:
        self.phase = GamePhase.GAME_OVER
        self._winner = name

    def _winner_name(self) -> Optional[str]:
        if self.phase != GamePhase.GAME_OVER:
            return None
        return getattr(self, "_winner", None)

    # ── AI ────────────────────────────────────────────────────────────────

    def _ai_act(self) -> None:
        for player in self.players.values():
            if player.is_ai:
                self._ai_turn(player)

    def _ai_turn(self, ai: Player) -> None:
        if self.phase == GamePhase.TRADING:
            self._ai_trade(ai)
            ai.ready = True
        elif self.phase == GamePhase.DEPLOYMENT:
            self._ai_deploy(ai)
            ai.ready = True

    def _ai_trade(self, ai: Player) -> None:
        # Try to buy one component from alien offer
        if self.alien_offer and ai.cash >= 50:
            comp = self._ai_pick_comp(ai)
            if comp and comp in self.alien_offer.components:
                cost = self.alien_offer.prices[comp]
                if ai.cash >= cost:
                    ai.cash -= cost
                    ai.add_inv(comp.value)
        # Build from inventory into satellite
        sat = ai.satellites[0] if ai.satellites else None
        if sat:
            for name in ["toroid", "plasma_gun", "missile", "grabber", "shield", "armor", "ecm"]:
                if ai.inventory.get(name, 0) > 0:
                    try:
                        ct = ComponentType(name)
                        if sat.add_component(ct):
                            ai.take_inv(name)
                            break
                    except ValueError:
                        continue

    def _ai_pick_comp(self, ai: Player) -> Optional[ComponentType]:
        if not self.alien_offer:
            return None
        avail  = self.alien_offer.components
        owned  = [c for sat in ai.satellites for c in sat.components]
        prio   = [ComponentType.TOROID, ComponentType.PLASMA_GUN, ComponentType.GRABBER,
                  ComponentType.MISSILE, ComponentType.SHIELD, ComponentType.ARMOR, ComponentType.ECM]
        for c in prio:
            if c in avail and owned.count(c) < 2:
                return c
        return random.choice(avail) if avail else None

    def _ai_deploy(self, ai: Player) -> None:
        sat = next((s for s in ai.satellites if s.is_mobile()), None)
        if not sat:
            return
        occupied = {s.moon_id for p in self.players.values() for s in p.satellites if s.moon_id}
        unclaimed = [m for m in self.moons if m.id not in occupied]
        moon = max(unclaimed, key=lambda m: m.yield_per_turn) if unclaimed else random.choice(self.moons)
        sat.moon_id = moon.id
