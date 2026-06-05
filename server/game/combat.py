import random
from typing import Tuple
from .satellite import Satellite


def _round(attacker: Satellite, defender: Satellite) -> Tuple[int, int]:
    atk = attacker.attack_power()
    atk_def = attacker.defense_power()
    def_atk = defender.attack_power()
    def_def = defender.defense_power()

    # Each unblocked weapon unit deals damage; randomise ±20%
    a_dmg = (max(0, def_atk["close"] - atk_def["close"]) * 15 +
             max(0, def_atk["medium"] - atk_def["medium"]) * 12 +
             max(0, def_atk["long"] - atk_def["long"]) * 10)
    d_dmg = (max(0, atk["close"] - def_def["close"]) * 15 +
             max(0, atk["medium"] - def_def["medium"]) * 12 +
             max(0, atk["long"] - def_def["long"]) * 10)

    # Unarmed satellites still deal 5 scratch damage per round
    a_dmg = max(5, int(a_dmg * random.uniform(0.8, 1.2)))
    d_dmg = max(5, int(d_dmg * random.uniform(0.8, 1.2)))
    return a_dmg, d_dmg


def run_battle(sat1: Satellite, sat2: Satellite) -> dict:
    rounds = []
    while sat1.stability > 0 and sat2.stability > 0 and len(rounds) < 50:
        d1, d2 = _round(sat1, sat2)
        sat1.stability = max(0, sat1.stability - d1)
        sat2.stability = max(0, sat2.stability - d2)
        rounds.append({
            "sat1_stability": sat1.stability,
            "sat2_stability": sat2.stability,
            "sat1_took": d1,
            "sat2_took": d2,
        })

    winner_id = sat1.owner_id if sat1.stability > 0 else sat2.owner_id
    return {
        "winner_id": winner_id,
        "rounds": rounds,
        "sat1": sat1.to_dict(),
        "sat2": sat2.to_dict(),
    }
