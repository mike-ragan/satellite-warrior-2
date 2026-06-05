import asyncio
import uuid
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from game.engine import GameEngine, GamePhase
from game.combat_rt import CombatSession

app = FastAPI(title="Satellite Warrior 2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

games:           Dict[str, GameEngine]     = {}
sessions:        Dict[str, tuple]          = {}   # token → (game_id, player_id)
connections:     Dict[str, List[WebSocket]] = {}
combat_sessions: Dict[str, CombatSession]  = {}


class CreateRequest(BaseModel):
    player_name: str = "Anonymous"


class JoinRequest(BaseModel):
    player_name: str = "Anonymous"


# ── HTTP routes ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/games")
async def create_game(body: CreateRequest):
    player_id = str(uuid.uuid4())
    token     = str(uuid.uuid4())
    engine    = GameEngine()
    engine.add_player(player_id, body.player_name)
    games[engine.game_id]      = engine
    sessions[token]             = (engine.game_id, player_id)
    connections[engine.game_id] = []
    return {"game_id": engine.game_id, "player_id": player_id, "session_token": token}


@app.post("/games/solo")
async def create_solo_game(body: CreateRequest):
    player_id = str(uuid.uuid4())
    token     = str(uuid.uuid4())
    engine    = GameEngine()
    engine.add_player(player_id, body.player_name)
    engine.add_ai_player("Computer")
    games[engine.game_id]      = engine
    sessions[token]             = (engine.game_id, player_id)
    connections[engine.game_id] = []
    return {"game_id": engine.game_id, "player_id": player_id, "session_token": token}


@app.get("/games/{game_id}")
async def get_game(game_id: str):
    engine = games.get(game_id)
    if not engine:
        raise HTTPException(404, "Game not found")
    return {"phase": engine.phase.value, "player_count": len(engine.players)}


@app.post("/games/{game_id}/join")
async def join_game(game_id: str, body: JoinRequest):
    engine = games.get(game_id)
    if not engine:
        raise HTTPException(404, "Game not found")
    player_id = str(uuid.uuid4())
    token     = str(uuid.uuid4())
    if not engine.add_player(player_id, body.player_name):
        raise HTTPException(400, "Game is full")
    sessions[token] = (game_id, player_id)
    await _broadcast(game_id, {"type": "state", "state": engine.to_dict()})
    return {"game_id": game_id, "player_id": player_id, "session_token": token}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/{token}")
async def ws_endpoint(websocket: WebSocket, token: str):
    session = sessions.get(token)
    if not session:
        await websocket.close(code=4001)
        return
    game_id, player_id = session
    engine = games.get(game_id)
    if not engine:
        await websocket.close(code=4002)
        return

    await websocket.accept()
    connections[game_id].append(websocket)
    await websocket.send_json({"type": "state", "state": engine.to_dict()})

    try:
        while True:
            data = await websocket.receive_json()

            # Combat input is routed directly to the active session
            if data.get("type") == "combat_input":
                cs = combat_sessions.get(game_id)
                if cs:
                    cs.set_input(player_id, data)
                continue

            result = _handle(engine, player_id, data)
            if result.get("ok"):
                await _broadcast(game_id, {"type": "state", "state": engine.to_dict()})
                # If phase just became COMBAT, launch real-time session
                if engine.phase == GamePhase.COMBAT and engine.pending_conflicts:
                    await _launch_combat(game_id, engine)
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": result.get("error", "Unknown error"),
                })
    except WebSocketDisconnect:
        conns = connections.get(game_id, [])
        if websocket in conns:
            conns.remove(websocket)


# ── Action dispatcher ─────────────────────────────────────────────────────────

def _handle(engine: GameEngine, player_id: str, data: dict) -> dict:
    match data.get("type"):
        case "buy":
            return engine.buy(player_id, data.get("component", ""), data.get("qty", 1))
        case "sell":
            return engine.sell(player_id, data.get("component", ""), data.get("qty", 1))
        case "build":
            return engine.build(player_id, data.get("component", ""), data.get("satellite_id", ""))
        case "deploy":
            return engine.deploy(player_id, data.get("satellite_id", ""), data.get("moon_id", ""))
        case "ready":
            return engine.ready(player_id)
        case _:
            return {"ok": False, "error": f"Unknown action: {data.get('type')}"}


# ── Combat helpers ────────────────────────────────────────────────────────────

async def _launch_combat(game_id: str, engine: GameEngine) -> None:
    if not engine.pending_conflicts:
        return
    conflict = engine.pending_conflicts[0]
    sat_a    = conflict["sat_a"]
    sat_b    = conflict["sat_b"]
    pid_a    = sat_a.get("owner_id", sat_a.get("player_id", ""))
    pid_b    = sat_b.get("owner_id", sat_b.get("player_id", ""))
    name_a   = engine.players[pid_a].name if pid_a in engine.players else "?"
    name_b   = engine.players[pid_b].name if pid_b in engine.players else "?"
    ai_pid   = next((pid for pid, p in engine.players.items() if p.is_ai), None)

    async def _bc(data: dict) -> None:
        await _broadcast(game_id, data)

    session = CombatSession(
        moon_id    = conflict["moon_id"],
        sat_a_data = sat_a,
        sat_b_data = sat_b,
        name_a     = name_a,
        name_b     = name_b,
        ai_pid     = ai_pid,
        broadcast  = _bc,
    )
    combat_sessions[game_id] = session
    asyncio.create_task(_run_combat(game_id, session, engine))


async def _run_combat(game_id: str, session: CombatSession, engine: GameEngine) -> None:
    await session.run()
    if session.winner_id:
        engine.resolve_combat(session.winner_id, session.moon_id)
    combat_sessions.pop(game_id, None)
    await _broadcast(game_id, {"type": "state", "state": engine.to_dict()})


async def _broadcast(game_id: str, msg: dict) -> None:
    dead = []
    for ws in connections.get(game_id, []):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connections[game_id].remove(ws)
