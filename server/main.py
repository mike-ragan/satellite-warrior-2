from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
from typing import Dict, List

from game.engine import GameEngine

app = FastAPI(title="Satellite Warrior 2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

games: Dict[str, GameEngine] = {}
sessions: Dict[str, tuple] = {}          # token -> (game_id, player_id)
connections: Dict[str, List[WebSocket]] = {}


class CreateRequest(BaseModel):
    player_name: str = "Anonymous"


class JoinRequest(BaseModel):
    player_name: str = "Anonymous"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/games")
async def create_game(body: CreateRequest):
    player_id = str(uuid.uuid4())
    token = str(uuid.uuid4())
    engine = GameEngine()
    engine.add_player(player_id, body.player_name)
    games[engine.game_id] = engine
    sessions[token] = (engine.game_id, player_id)
    connections[engine.game_id] = []
    return {"game_id": engine.game_id, "player_id": player_id, "session_token": token}


@app.post("/games/solo")
async def create_solo_game(body: CreateRequest):
    player_id = str(uuid.uuid4())
    token = str(uuid.uuid4())
    engine = GameEngine()
    engine.add_player(player_id, body.player_name)
    engine.add_ai_player("Computer")
    games[engine.game_id] = engine
    sessions[token] = (engine.game_id, player_id)
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
    token = str(uuid.uuid4())
    if not engine.add_player(player_id, body.player_name):
        raise HTTPException(400, "Game is full")
    sessions[token] = (game_id, player_id)
    await _broadcast(game_id, {"type": "state", "state": engine.to_dict()})
    return {"game_id": game_id, "player_id": player_id, "session_token": token}


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
            result = _handle(engine, player_id, data)
            if result.get("ok"):
                await _broadcast(game_id, {"type": "state", "state": engine.to_dict()})
            else:
                await websocket.send_json({"type": "error", "message": result.get("error")})
    except WebSocketDisconnect:
        if websocket in connections.get(game_id, []):
            connections[game_id].remove(websocket)


def _handle(engine: GameEngine, player_id: str, data: dict) -> dict:
    match data.get("type"):
        case "buy":
            return engine.buy(player_id, data.get("component", ""), data.get("qty", 1))
        case "deploy":
            return engine.deploy(player_id, data.get("satellite_id", ""), data.get("moon_id", ""))
        case "ready":
            return engine.ready(player_id)
        case _:
            return {"ok": False, "error": f"Unknown action: {data.get('type')}"}


async def _broadcast(game_id: str, msg: dict) -> None:
    dead = []
    for ws in connections.get(game_id, []):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connections[game_id].remove(ws)
