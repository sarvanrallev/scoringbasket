"""
WebSocket Routes
Real-time match updates and spectator features
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.exceptions import WebSocketException
from sqlalchemy.orm import Session
import logging
from typing import Optional

from .database import get_db_session
from .security import get_current_user_from_token
from .routes_auth import get_current_user
from .models import User, Game
from .services_realtime import realtime_service, EventType, RealtimeEvent

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/match/{match_id}")
async def websocket_match_endpoint(
    websocket: WebSocket,
    match_id: int,
    token: Optional[str] = Query(None),
    db = Depends(get_db_session)
):
    """
    WebSocket endpoint for real-time match updates
    
    Query parameters:
    - token: JWT authentication token
    
    Events broadcast:
    - match_started: Game has started
    - score_update: Score changes
    - event_recorded: Player event (goal, foul, etc)
    - spectator_joined: New spectator connected
    - match_paused: Game paused
    - match_resumed: Game resumed
    - match_ended: Game finished
    - message: Chat message from spectator
    """
    
    # Authenticate user
    if not token:
        await websocket.close(code=1008, reason="Authentication token required")
        return
    
    try:
        user = get_current_user_from_token(token, db)
        if not user:
            await websocket.close(code=1008, reason="Invalid authentication token")
            return
    except Exception as e:
        logger.error(f"WebSocket auth error: {str(e)}")
        await websocket.close(code=1008, reason="Authentication failed")
        return
    
    # Verify match exists
    match = db.query(Game).filter(Game.id == match_id).first()
    if not match:
        await websocket.close(code=1008, reason="Game not found")
        return
    
    # Accept connection
    await websocket.accept()
    connection_id = f"{user.id}_{match_id}_{id(websocket)}"
    
    # Register connection
    room = realtime_service.connection_manager.add_connection(
        connection_id=connection_id,
        match_id=match_id,
        user_id=user.id,
        username=user.username
    )
    
    logger.info(f"User {user.username} connected to match {match_id} room")
    
    # Send initial state
    try:
        await websocket.send_json({
            "type": "connection_established",
            "connection_id": connection_id,
            "match_id": match_id,
            "user_id": user.id,
            "username": user.username,
            "spectators": room.get_spectator_count(),
            "room_state": room.get_state()
        })
    except Exception as e:
        logger.error(f"Error sending initial state: {str(e)}")
        realtime_service.connection_manager.remove_connection(connection_id)
        return
    
    # Broadcast spectator joined
    join_event = RealtimeEvent(
        event_type=EventType.SPECTATOR_JOINED,
        match_id=match_id,
        user_id=user.id,
        data={
            "username": user.username,
            "user_id": user.id,
            "spectators_count": room.get_spectator_count()
        }
    )
    
    connections = realtime_service.connection_manager.get_connections_for_match(match_id)
    for conn_id in connections:
        if conn_id != connection_id:
            try:
                # This would need to store websocket refs for actual broadcast
                pass
            except Exception as e:
                logger.error(f"Error broadcasting join event: {str(e)}")
    
    # Message handling loop
    try:
        while True:
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "ping":
                # Simple heartbeat
                await websocket.send_json({"type": "pong"})
            
            elif message_type == "chat":
                # Broadcast chat message
                message = data.get("message", "")
                if message.strip():
                    event = realtime_service.broadcast_chat(
                        match_id=match_id,
                        user_id=user.id,
                        username=user.username,
                        message=message
                    )
                    
                    # Send to client
                    await websocket.send_json({
                        "type": "chat",
                        "data": event.to_dict()
                    })
            
            elif message_type == "get_state":
                # Send current room state
                room_state = realtime_service.connection_manager.get_room(match_id)
                if room_state:
                    await websocket.send_json({
                        "type": "room_state",
                        "data": room_state.get_state()
                    })
            
            elif message_type == "get_events":
                # Send recent events
                room_state = realtime_service.connection_manager.get_room(match_id)
                if room_state:
                    await websocket.send_json({
                        "type": "events",
                        "data": [e.to_dict() for e in room_state.events_history]
                    })
            
            else:
                logger.warning(f"Unknown message type: {message_type}")
    
    except WebSocketDisconnect:
        logger.info(f"User {user.username} disconnected from match {match_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    
    finally:
        # Remove connection
        realtime_service.connection_manager.remove_connection(connection_id)
        
        # Broadcast spectator left
        try:
            room = realtime_service.connection_manager.get_room(match_id)
            if room:
                spectators_count = room.get_spectator_count()
                
                leave_event = RealtimeEvent(
                    event_type=EventType.SPECTATOR_LEFT,
                    match_id=match_id,
                    user_id=user.id,
                    data={
                        "username": user.username,
                        "user_id": user.id,
                        "spectators_count": spectators_count
                    }
                )
        except Exception as e:
            logger.error(f"Error on disconnect: {str(e)}")


@router.get("/api/matches/{match_id}/spectators")
async def get_match_spectators(
    match_id: int,
    db = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Get spectator count for a match"""
    # Verify match exists
    match = db.query(Game).filter(Game.id == match_id).first()
    if not match:
        return {"error": "Game not found"}
    
    count = realtime_service.get_spectator_count(match_id)
    state = realtime_service.get_match_state(match_id)
    
    return {
        "match_id": match_id,
        "spectators": count,
        "state": state
    }


@router.get("/api/active-matches")
async def get_active_matches(
    db = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Get all matches with active spectators"""
    active_matches = realtime_service.connection_manager.get_active_matches()
    
    return {
        "active_matches": active_matches,
        "total_connections": realtime_service.connection_manager.get_connection_count()
    }


# Helper function to import in main.py
def get_websocket_router():
    """Get WebSocket router"""
    return router
