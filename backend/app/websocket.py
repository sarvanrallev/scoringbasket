"""
WebSocket configuration and handlers for Scoring Basket
Manages real-time game updates using Socket.IO
"""

from fastapi import Depends
from sqlalchemy.orm import Session
from socketio import AsyncServer, ASGIApp
import logging
from typing import Dict, Set, Optional
from datetime import datetime

from .database import get_db_context
from .models import Game, GameEvent
from .services import StatsCalculationService, GameStateService, RepositoryService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create async Socket.IO server
sio = AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_interval=20,
    ping_timeout=10,
    max_http_buffer_size=1000000,
)

# Track connected clients per game
game_rooms: Dict[int, Set[str]] = {}  # {game_id: {session_id, ...}}


# ==================== CONNECTION HANDLERS ====================

@sio.on("connect")
async def connect(sid: str, environ):
    """Handle client connection"""
    logger.info(f"✅ Client connected: {sid}")
    return True


@sio.on("disconnect")
async def disconnect(sid: str):
    """Handle client disconnection"""
    logger.info(f"❌ Client disconnected: {sid}")
    
    # Remove from all game rooms
    for game_id, clients in list(game_rooms.items()):
        if sid in clients:
            clients.discard(sid)
            logger.info(f"   Removed from game {game_id} room")


# ==================== GAME ROOM HANDLERS ====================

@sio.on("join_game")
async def join_game(sid: str, data: dict):
    """
    Join a game room for real-time updates
    Expected data: {"game_id": int}
    """
    game_id = data.get("game_id")
    
    if not game_id:
        logger.warning(f"Invalid join_game data from {sid}: {data}")
        return {"status": "error", "message": "game_id required"}
    
    # Verify game exists
    with get_db_context() as db:
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            logger.warning(f"Game {game_id} not found")
            return {"status": "error", "message": "Game not found"}
    
    # Add to room
    if game_id not in game_rooms:
        game_rooms[game_id] = set()
    
    game_rooms[game_id].add(sid)
    sio.enter_room(sid, f"game_{game_id}")
    
    logger.info(f"✅ Client {sid} joined game {game_id} room ({len(game_rooms[game_id])} clients)")
    
    return {
        "status": "success",
        "message": f"Joined game {game_id}",
        "game_id": game_id,
        "room": f"game_{game_id}"
    }


@sio.on("leave_game")
async def leave_game(sid: str, data: dict):
    """
    Leave a game room
    Expected data: {"game_id": int}
    """
    game_id = data.get("game_id")
    
    if game_id and game_id in game_rooms:
        game_rooms[game_id].discard(sid)
        sio.leave_room(sid, f"game_{game_id}")
        logger.info(f"Client {sid} left game {game_id} room ({len(game_rooms[game_id])} clients)")
    
    return {"status": "success", "message": "Left game room"}


# ==================== GAME UPDATE HANDLERS ====================

@sio.on("get_scoreboard")
async def get_scoreboard(sid: str, data: dict):
    """
    Get live scoreboard for a game
    Expected data: {"game_id": int}
    """
    game_id = data.get("game_id")
    
    if not game_id:
        return {"status": "error", "message": "game_id required"}
    
    with get_db_context() as db:
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return {"status": "error", "message": "Game not found"}
        
        # Calculate scoreboard data
        home_stats = StatsCalculationService.get_team_stats(game_id, game.home_team_id, db)
        away_stats = StatsCalculationService.get_team_stats(game_id, game.away_team_id, db)
        period = GameStateService.get_current_period(game_id, db)
        latest_event = RepositoryService.get_latest_game_event(game_id, db)
        
        return {
            "status": "success",
            "game_id": game_id,
            "game_status": game.status,
            "period": period,
            "home_team": home_stats,
            "away_team": away_stats,
            "latest_event": {
                "id": latest_event.id,
                "event_type": latest_event.event_type,
                "period": latest_event.period,
                "outcome": latest_event.outcome,
            } if latest_event else None,
            "timestamp": datetime.utcnow().isoformat()
        }


@sio.on("get_boxscore")
async def get_boxscore(sid: str, data: dict):
    """
    Get detailed box score for a game
    Expected data: {"game_id": int}
    """
    game_id = data.get("game_id")
    
    if not game_id:
        return {"status": "error", "message": "game_id required"}
    
    with get_db_context() as db:
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return {"status": "error", "message": "Game not found"}
        
        home_stats = StatsCalculationService.get_team_stats(game_id, game.home_team_id, db)
        away_stats = StatsCalculationService.get_team_stats(game_id, game.away_team_id, db)
        event_count = db.query(GameEvent).filter(GameEvent.game_id == game_id).count()
        
        return {
            "status": "success",
            "game_id": game_id,
            "home_team": home_stats,
            "away_team": away_stats,
            "total_events": event_count,
            "game_status": game.status,
            "timestamp": datetime.utcnow().isoformat()
        }


# ==================== BROADCAST FUNCTIONS ====================

async def broadcast_scoreboard_update(game_id: int):
    """
    Broadcast scoreboard update to all clients in game room
    Called when new event is recorded
    """
    with get_db_context() as db:
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return
        
        # Calculate scoreboard data
        home_stats = StatsCalculationService.get_team_stats(game_id, game.home_team_id, db)
        away_stats = StatsCalculationService.get_team_stats(game_id, game.away_team_id, db)
        period = GameStateService.get_current_period(game_id, db)
        latest_event = RepositoryService.get_latest_game_event(game_id, db)
    
    message = {
        "event": "scoreboard_update",
        "game_id": game_id,
        "game_status": game.status,
        "period": period,
        "home_team": home_stats,
        "away_team": away_stats,
        "latest_event": {
            "id": latest_event.id,
            "event_type": latest_event.event_type,
            "period": latest_event.period,
            "outcome": latest_event.outcome,
            "player_id": latest_event.player_id,
            "team_id": latest_event.team_id,
        } if latest_event else None,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Broadcast to all clients in game room
    await sio.emit("scoreboard_update", message, room=f"game_{game_id}")
    logger.info(f"📡 Broadcasted scoreboard update for game {game_id}")


async def broadcast_game_status_update(game_id: int, status: str):
    """
    Broadcast game status change to all clients in game room
    """
    with get_db_context() as db:
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return
    
    message = {
        "event": "game_status_update",
        "game_id": game_id,
        "status": status,
        "started_at": game.started_at.isoformat() if game.started_at else None,
        "ended_at": game.ended_at.isoformat() if game.ended_at else None,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await sio.emit("game_status_update", message, room=f"game_{game_id}")
    logger.info(f"📡 Broadcasted game status update for game {game_id}: {status}")


async def broadcast_event_created(game_id: int, event_id: int):
    """
    Broadcast new event to all clients in game room
    """
    with get_db_context() as db:
        event = db.query(GameEvent).filter(GameEvent.id == event_id).first()
        if not event:
            return
    
    message = {
        "event": "event_created",
        "game_id": game_id,
        "event_id": event_id,
        "event_type": event.event_type,
        "period": event.period,
        "timestamp": event.timestamp,
        "outcome": event.outcome,
        "player_id": event.player_id,
        "team_id": event.team_id,
        "created_at": event.created_at.isoformat()
    }
    
    await sio.emit("event_created", message, room=f"game_{game_id}")
    logger.info(f"📡 Broadcasted event {event_id} for game {game_id}")


async def broadcast_event_deleted(game_id: int, event_id: int):
    """
    Broadcast event deletion to all clients in game room
    """
    message = {
        "event": "event_deleted",
        "game_id": game_id,
        "event_id": event_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await sio.emit("event_deleted", message, room=f"game_{game_id}")
    logger.info(f"📡 Broadcasted event deletion {event_id} for game {game_id}")


async def broadcast_roster_update(game_id: int, player_id: int, status: str):
    """
    Broadcast roster status change to all clients in game room
    """
    message = {
        "event": "roster_update",
        "game_id": game_id,
        "player_id": player_id,
        "status": status,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await sio.emit("roster_update", message, room=f"game_{game_id}")
    logger.info(f"📡 Broadcasted roster update for game {game_id}")


def get_game_room_client_count(game_id: int) -> int:
    """Get number of connected clients for a game"""
    return len(game_rooms.get(game_id, set()))


def get_connected_games() -> Dict[int, int]:
    """Get all games with connected clients and their client count"""
    return {game_id: len(clients) for game_id, clients in game_rooms.items() if clients}


# ==================== ASGI APP ====================

def get_socket_app():
    """Create Socket.IO ASGI app"""
    return ASGIApp(sio)
