"""Real-time combat session — runs as an asyncio task at 30 fps."""
from __future__ import annotations
import asyncio
import math
import uuid
from dataclasses import dataclass, field
from typing import Callable, Coroutine, Dict, List, Optional

ARENA_W     = 800
ARENA_H     = 500
TICK_RATE   = 1 / 30        # 30 fps
BULLET_SPD  = 350.0
HIT_RADIUS  = 22.0
BASE_SPEED  = 140.0

WEAPON_DMG = {"grabber": 8, "plasma_gun": 12, "missile": 18, "head": 4}
WEAPON_CD  = {"grabber": 0.30, "plasma_gun": 0.40, "missile": 1.0,  "head": 0.50}


@dataclass
class _Sat:
    pid:       str
    name:      str
    x:         float
    y:         float
    health:    int
    max_hp:    int
    speed:     float
    weapons:   List[str]
    cooldowns: Dict[str, float] = field(default_factory=dict)


@dataclass
class _Bullet:
    bid:    str
    owner:  str
    x:      float
    y:      float
    vx:     float
    vy:     float
    damage: int
    weapon: str


def _build_sat(sat_data: dict, name: str, x: float) -> _Sat:
    comps   = sat_data.get("components", ["head"])
    weapons = [c for c in comps if c in WEAPON_DMG and c != "head"]
    if not weapons:
        weapons = ["head"]
    speed = BASE_SPEED + (20.0 if "toroid" in comps else 0.0)
    hp    = 80 + sat_data.get("stability", 100) + comps.count("armor") * 15 + comps.count("shield") * 10
    return _Sat(
        pid     = sat_data.get("owner_id", sat_data.get("player_id", "")),
        name    = name,
        x       = x,
        y       = ARENA_H / 2,
        health  = hp,
        max_hp  = hp,
        speed   = speed,
        weapons = weapons,
    )


class CombatSession:
    def __init__(
        self,
        moon_id:    str,
        sat_a_data: dict,
        sat_b_data: dict,
        name_a:     str,
        name_b:     str,
        ai_pid:     Optional[str],
        broadcast:  Callable[[dict], Coroutine],
    ) -> None:
        self.moon_id   = moon_id
        self.ai_pid    = ai_pid
        self._bc       = broadcast
        self.running   = False
        self.winner_id: Optional[str] = None

        self.sats: Dict[str, _Sat] = {
            sat_a_data.get("owner_id", sat_a_data.get("player_id", "a")): _build_sat(sat_a_data, name_a, 80),
            sat_b_data.get("owner_id", sat_b_data.get("player_id", "b")): _build_sat(sat_b_data, name_b, ARENA_W - 80),
        }
        self.bullets: List[_Bullet] = []
        self.inputs:  Dict[str, dict] = {}

    # ── Public ────────────────────────────────────────────────────────────

    def set_input(self, pid: str, data: dict) -> None:
        self.inputs[pid] = data

    async def run(self) -> None:
        self.running = True
        while self.running:
            if self.ai_pid:
                self._ai_think(self.ai_pid)
            await asyncio.sleep(TICK_RATE)
            self._tick(TICK_RATE)
            await self._bc(self._state())

    # ── Simulation ────────────────────────────────────────────────────────

    def _tick(self, dt: float) -> None:
        for pid, sat in self.sats.items():
            inp = self.inputs.get(pid, {})
            dx  = float(inp.get("dx", 0))
            dy  = float(inp.get("dy", 0))
            mag = math.sqrt(dx * dx + dy * dy)
            if mag > 1.0:
                dx /= mag
                dy /= mag
            sat.x = max(20, min(ARENA_W - 20, sat.x + dx * sat.speed * dt))
            sat.y = max(20, min(ARENA_H - 20, sat.y + dy * sat.speed * dt))

            weapon = inp.get("weapon") or sat.weapons[0]
            if weapon not in sat.weapons:
                weapon = sat.weapons[0]
            sat.cooldowns[weapon] = max(0.0, sat.cooldowns.get(weapon, 0.0) - dt)
            if inp.get("fire") and sat.cooldowns.get(weapon, 0.0) <= 0:
                self._fire(pid, sat, weapon)
                sat.cooldowns[weapon] = WEAPON_CD.get(weapon, 0.5)

        dead: List[_Bullet] = []
        for b in self.bullets:
            b.x += b.vx * dt
            b.y += b.vy * dt
            if not (0 <= b.x <= ARENA_W and 0 <= b.y <= ARENA_H):
                dead.append(b)
                continue
            for pid, sat in self.sats.items():
                if pid == b.owner:
                    continue
                if abs(b.x - sat.x) < HIT_RADIUS and abs(b.y - sat.y) < HIT_RADIUS:
                    sat.health = max(0, sat.health - b.damage)
                    dead.append(b)
                    if sat.health == 0:
                        self.winner_id = b.owner
                        self.running   = False
                    break
        for b in dead:
            if b in self.bullets:
                self.bullets.remove(b)

    def _fire(self, pid: str, sat: _Sat, weapon: str) -> None:
        opp = next((s for p, s in self.sats.items() if p != pid), None)
        if not opp:
            return
        dx, dy = opp.x - sat.x, opp.y - sat.y
        dist   = math.sqrt(dx * dx + dy * dy) or 1.0
        self.bullets.append(_Bullet(
            bid    = str(uuid.uuid4())[:6],
            owner  = pid,
            x      = sat.x, y = sat.y,
            vx     = dx / dist * BULLET_SPD,
            vy     = dy / dist * BULLET_SPD,
            damage = WEAPON_DMG.get(weapon, 4),
            weapon = weapon,
        ))

    # ── AI ────────────────────────────────────────────────────────────────

    def _ai_think(self, ai_pid: str) -> None:
        if ai_pid not in self.sats:
            return
        ai  = self.sats[ai_pid]
        opp = next((s for p, s in self.sats.items() if p != ai_pid), None)
        if not opp:
            return
        dx, dy = opp.x - ai.x, opp.y - ai.y
        dist   = math.sqrt(dx * dx + dy * dy) or 1.0
        pref   = 190.0

        if dist > pref + 50:
            mx, my = dx / dist, dy / dist
        elif dist < pref - 50:
            mx, my = -dx / dist, -dy / dist
        else:
            mx, my = -dy / dist * 0.8, dx / dist * 0.8  # strafe

        self.inputs[ai_pid] = {
            "dx":     mx,
            "dy":     my,
            "fire":   abs(dy) < 60,
            "weapon": ai.weapons[0] if ai.weapons else "head",
        }

    # ── State ─────────────────────────────────────────────────────────────

    def _state(self) -> dict:
        return {
            "type":      "combat_state",
            "moon_id":   self.moon_id,
            "sats":      {
                pid: {
                    "player_id": pid,
                    "name":      s.name,
                    "x":         round(s.x, 1),
                    "y":         round(s.y, 1),
                    "health":    s.health,
                    "max_health": s.max_hp,
                }
                for pid, s in self.sats.items()
            },
            "bullets":   [
                {"id": b.bid, "x": round(b.x, 1), "y": round(b.y, 1), "weapon": b.weapon}
                for b in self.bullets
            ],
            "winner_id": self.winner_id,
        }
