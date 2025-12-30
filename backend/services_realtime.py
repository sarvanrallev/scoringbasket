"""
Real-time Services
Handles WebSocket connections, live match updates, and broadcasting
"""

from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session
from datetime import datetime
import json
import asyncio
from enum import Enum

from .models import Game, GameEvent, User, Team


class EventType(str, Enum):
    """Real-time event types"""
    MATCH_STARTED = "match_started"
    MATCH_ENDED = "match_ended"
    SCORE_UPDATE = "score_update"
    EVENT_RECORDED = "event_recorded"
    PLAYER_STATS = "player_stats"
    SPECTATOR_JOINED = "spectator_joined"
    SPECTATOR_LEFT = "spectator_left"
    MATCH_PAUSED = "match_paused"
    MATCH_RESUMED = "match_resumed"
    MESSAGE = "message"
    NOTIFICATION = "notification"
    BRACKET_UPDATE = "bracket_update"


class RealtimeEvent:
    """Represents a real-time event"""
    
    def __init__(
        self,
        event_type: EventType,
        game_id: int,
        data: dict,
        user_id: Optional[int] = None,
        timestamp: Optional[datetime] = None
    ):
        self.event_type = event_type
        self.game_id = game_id
        self.data = data
        self.user_id = user_id
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> dict:
        """Convert event to dictionary"""
        return {
            "type": self.event_type.value,
            "game_id": self.game_id,
            "data": self.data,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_json(self) -> str:
        """Convert event to JSON string"""
        return json.dumps(self.to_dict())


class GameRoom:
    """Manages WebSocket connections for a specific game"""
    
    def __init__(self, game_id: int):
        self.game_id = game_id
        self.spectators: Set[str] = set()  # Connection IDs
        self.scoreboard_data: dict = {}
        self.events_history: List[RealtimeEvent] = []
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
    
    def add_spectator(self, connection_id: str) -> bool:
        """Add spectator to room"""
        if connection_id not in self.spectators:
            self.spectators.add(connection_id)
            self.last_activity = datetime.utcnow()
            return True
        return False
    
    def remove_spectator(self, connection_id: str) -> bool:
        """Remove spectator from room"""
        if connection_id in self.spectators:
            self.spectators.remove(connection_id)
            self.last_activity = datetime.utcnow()
            return True
        return False
    
    def get_spectator_count(self) -> int:
        """Get number of active spectators"""
        return len(self.spectators)
    
    def add_event(self, event: RealtimeEvent) -> None:
        """Add event to history"""
        self.events_history.append(event)
        self.last_activity = datetime.utcnow()
        # Keep only last 100 events
        if len(self.events_history) > 100:
            self.events_history = self.events_history[-100:]
    
    def update_scoreboard(self, home_score: int, away_score: int) -> dict:
        """Update and return scoreboard data"""
        self.scoreboard_data = {
            "home_score": home_score,
            "away_score": away_score,
            "timestamp": datetime.utcnow().isoformat()
        }
        return self.scoreboard_data
    
    def get_state(self) -> dict:
        """Get current room state"""
        return {
            "game_id": self.game_id,
            "spectators": self.get_spectator_count(),
            "scoreboard": self.scoreboard_data,
            "recent_events": [e.to_dict() for e in self.events_history[-10:]],
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat()
        }


class ConnectionManager:
    """Manages WebSocket connections and rooms"""
    
    def __init__(self):
        self.rooms: Dict[int, GameRoom] = {}
        self.connection_map: Dict[str, int] = {}  # connection_id -> game_id
        self.active_connections: Dict[str, dict] = {}  # connection_id -> user info
    
    def create_room(self, game_id: int) -> GameRoom:
        """Create a new match room"""
        if game_id not in self.rooms:
            self.rooms[game_id] = GameRoom(game_id)
        return self.rooms[game_id]
    
    def get_room(self, game_id: int) -> Optional[GameRoom]:
        """Get match room"""
        return self.rooms.get(game_id)
    
    def add_connection(
        self,
        connection_id: str,
        game_id: int,
        user_id: int,
        username: str
    ) -> GameRoom:
        """Add a new WebSocket connection"""
        room = self.create_room(game_id)
        room.add_spectator(connection_id)
        self.connection_map[connection_id] = game_id
        self.active_connections[connection_id] = {
            "user_id": user_id,
            "username": username,
            "game_id": game_id,
            "connected_at": datetime.utcnow().isoformat()
        }
        return room
    
    def remove_connection(self, connection_id: str) -> Optional[int]:
        """Remove a WebSocket connection"""
        if connection_id in self.connection_map:
            game_id = self.connection_map[connection_id]
            room = self.rooms.get(game_id)
            if room:
                room.remove_spectator(connection_id)
                # Clean up empty rooms after 1 hour
                if room.get_spectator_count() == 0:
                    # Optional: remove room after timeout
                    pass
            
            del self.connection_map[connection_id]
            del self.active_connections[connection_id]
            return game_id
        return None
    
    def get_connections_for_match(self, game_id: int) -> List[str]:
        """Get all connections for a specific match"""
        room = self.rooms.get(game_id)
        if room:
            return list(room.spectators)
        return []
    
    def get_match_for_connection(self, connection_id: str) -> Optional[int]:
        """Get match ID for a connection"""
        return self.connection_map.get(connection_id)
    
    def broadcast_to_match(self, game_id: int, event: RealtimeEvent) -> int:
        """Broadcast event to all connections in a match"""
        room = self.rooms.get(game_id)
        if not room:
            return 0
        
        room.add_event(event)
        return room.get_spectator_count()
    
    def get_active_matches(self) -> List[dict]:
        """Get list of active matches with spectator info"""
        active = []
        for game_id, room in self.rooms.items():
            if room.get_spectator_count() > 0:
                active.append({
                    "game_id": game_id,
                    "spectators": room.get_spectator_count(),
                    "last_activity": room.last_activity.isoformat()
                })
        return active
    
    def get_connection_count(self) -> int:
        """Get total active connections"""
        return len(self.active_connections)


class RealtimeService:
    """Service for real-time match operations"""
    
    def __init__(self):
        self.connection_manager = ConnectionManager()
    
    def start_match(self, game_id: int, db: Session) -> RealtimeEvent:
        """Create match started event"""
        match = db.query(Game).filter(Game.id == game_id).first()
        if not match:
            raise ValueError(f"Game {game_id} not found")
        
        event = RealtimeEvent(
            event_type=EventType.MATCH_STARTED,
            game_id=game_id,
            data={
                "home_team": match.home_team.name if match.home_team else "Unknown",
                "away_team": match.away_team.name if match.away_team else "Unknown",
                "home_id": match.home_team_id,
                "away_id": match.away_team_id,
                "location": match.location,
                "quarter": 1
            }
        )
        
        self.connection_manager.broadcast_to_match(game_id, event)
        return event
    
    def end_match(
        self,
        game_id: int,
        home_score: int,
        away_score: int,
        db: Session
    ) -> RealtimeEvent:
        """Create match ended event"""
        match = db.query(Game).filter(Game.id == game_id).first()
        if not match:
            raise ValueError(f"Game {game_id} not found")
        
        winner = None
        if home_score > away_score:
            winner = "home"
        elif away_score > home_score:
            winner = "away"
        else:
            winner = "tie"
        
        event = RealtimeEvent(
            event_type=EventType.MATCH_ENDED,
            game_id=game_id,
            data={
                "home_score": home_score,
                "away_score": away_score,
                "winner": winner,
                "home_team": match.home_team.name if match.home_team else "Unknown",
                "away_team": match.away_team.name if match.away_team else "Unknown"
            }
        )
        
        self.connection_manager.broadcast_to_match(game_id, event)
        return event
    
    def record_score(
        self,
        game_id: int,
        home_score: int,
        away_score: int,
        db: Session
    ) -> RealtimeEvent:
        """Create score update event"""
        match = db.query(Game).filter(Game.id == game_id).first()
        if not match:
            raise ValueError(f"Game {game_id} not found")
        
        event = RealtimeEvent(
            event_type=EventType.SCORE_UPDATE,
            game_id=game_id,
            data={
                "home_score": home_score,
                "away_score": away_score,
                "margin": abs(home_score - away_score),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        room = self.connection_manager.get_room(game_id)
        if room:
            room.update_scoreboard(home_score, away_score)
        
        self.connection_manager.broadcast_to_match(game_id, event)
        return event
    
    def record_event(
        self,
        game_id: int,
        event_type: str,
        player_id: int,
        player_name: str,
        team_id: int,
        team_name: str,
        points: int,
        quarter: int,
        db: Session
    ) -> RealtimeEvent:
        """Create match event record"""
        match = db.query(Game).filter(Game.id == game_id).first()
        if not match:
            raise ValueError(f"Game {game_id} not found")
        
        event = RealtimeEvent(
            event_type=EventType.EVENT_RECORDED,
            game_id=game_id,
            data={
                "event_type": event_type,
                "player_id": player_id,
                "player_name": player_name,
                "team_id": team_id,
                "team_name": team_name,
                "points": points,
                "quarter": quarter,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        self.connection_manager.broadcast_to_match(game_id, event)
        return event
    
    def send_notification(
        self,
        game_id: int,
        title: str,
        message: str,
        notif_type: str = "info"
    ) -> RealtimeEvent:
        """Send notification to all spectators"""
        event = RealtimeEvent(
            event_type=EventType.NOTIFICATION,
            game_id=game_id,
            data={
                "title": title,
                "message": message,
                "type": notif_type,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        self.connection_manager.broadcast_to_match(game_id, event)
        return event
    
    def broadcast_chat(
        self,
        game_id: int,
        user_id: int,
        username: str,
        message: str
    ) -> RealtimeEvent:
        """Broadcast chat message to match spectators"""
        event = RealtimeEvent(
            event_type=EventType.MESSAGE,
            game_id=game_id,
            user_id=user_id,
            data={
                "username": username,
                "message": message,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        self.connection_manager.broadcast_to_match(game_id, event)
        return event
    
    def get_spectator_count(self, game_id: int) -> int:
        """Get number of spectators for a match"""
        room = self.connection_manager.get_room(game_id)
        if room:
            return room.get_spectator_count()
        return 0
    
    def get_match_state(self, game_id: int) -> dict:
        """Get current state of a match room"""
        room = self.connection_manager.get_room(game_id)
        if room:
            return room.get_state()
        return {}


# Global instance
realtime_service = RealtimeService()
