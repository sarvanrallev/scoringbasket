"""
Pydantic request/response schemas for Scoring Basket
Used for API validation and serialization
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ==================== Enums ====================

class GameStatus(str, Enum):
    """Game status enum"""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


class EventType(str, Enum):
    """Game event type enum"""
    TWO_PT = "2PT"
    THREE_PT = "3PT"
    FREE_THROW = "FT"
    ASSIST = "AST"
    REBOUND = "REB"
    FOUL = "FLS"
    SUBSTITUTION = "SUB"
    TIMEOUT = "TO"
    PERIOD_START = "PERIOD_START"
    PERIOD_END = "PERIOD_END"


class EventOutcome(str, Enum):
    """Outcome for shots"""
    MADE = "made"
    MISS = "miss"


class PlayerPosition(str, Enum):
    """Basketball player position"""
    PG = "PG"  # Point Guard
    SG = "SG"  # Shooting Guard
    SF = "SF"  # Small Forward
    PF = "PF"  # Power Forward
    C = "C"    # Center


# ==================== Team Schemas ====================

class TeamCreate(BaseModel):
    """Schema for creating a new team"""
    name: str = Field(..., min_length=1, max_length=255, description="Team name")


class TeamUpdate(BaseModel):
    """Schema for updating a team"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)


class TeamResponse(BaseModel):
    """Schema for team response"""
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TeamDetail(TeamResponse):
    """Detailed team response with players"""
    players: List["PlayerResponse"] = []


# ==================== Player Schemas ====================

class PlayerCreate(BaseModel):
    """Schema for creating a new player"""
    name: str = Field(..., min_length=1, max_length=255)
    number: int = Field(..., ge=0, le=99, description="Jersey number")
    position: PlayerPosition


class PlayerUpdate(BaseModel):
    """Schema for updating a player"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    number: Optional[int] = Field(None, ge=0, le=99)
    position: Optional[PlayerPosition] = None


class PlayerResponse(BaseModel):
    """Schema for player response"""
    id: int
    name: str
    number: int
    position: str
    team_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Game Event Schemas ====================

class GameEventCreate(BaseModel):
    """Schema for creating a new game event"""
    player_id: Optional[int] = Field(None, description="Player ID (optional for team events)")
    team_id: int = Field(..., description="Team ID")
    event_type: EventType
    period: int = Field(..., ge=1, le=5, description="Period (1-4 for regular, 5 for OT)")
    timestamp: Optional[int] = Field(None, ge=0, description="Seconds elapsed in period")
    outcome: Optional[EventOutcome] = Field(None, description="Outcome for shot events")


class GameEventResponse(BaseModel):
    """Schema for game event response"""
    id: int
    game_id: int
    player_id: Optional[int]
    team_id: int
    event_type: str
    period: int
    timestamp: Optional[int]
    outcome: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class GameEventDetail(GameEventResponse):
    """Detailed event response with player info"""
    player: Optional[PlayerResponse] = None
    team: Optional[TeamResponse] = None


# ==================== Game Schemas ====================

class GameCreate(BaseModel):
    """Schema for creating a new game"""
    home_team_id: int = Field(..., description="Home team ID")
    away_team_id: int = Field(..., description="Away team ID")

    def validate_teams(self):
        """Ensure home and away teams are different"""
        if self.home_team_id == self.away_team_id:
            raise ValueError("Home and away teams must be different")


class GameStartRequest(BaseModel):
    """Schema for starting a game"""
    pass


class GameEndRequest(BaseModel):
    """Schema for ending a game"""
    pass


class GameResponse(BaseModel):
    """Schema for game response"""
    id: int
    home_team_id: int
    away_team_id: int
    status: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class GameDetail(GameResponse):
    """Detailed game response with teams and rosters"""
    home_team: Optional[TeamResponse] = None
    away_team: Optional[TeamResponse] = None
    events: List[GameEventResponse] = []


# ==================== Scoreboard & Stats Schemas ====================

class PlayerStats(BaseModel):
    """Player game statistics"""
    player_id: int
    name: str
    number: int
    position: str
    status: str
    
    # Scoring
    points: int = 0
    
    # Field Goals
    fga: int = 0  # Field Goal Attempts
    fgm: int = 0  # Field Goal Made
    fg_pct: float = 0.0
    
    # 3-Pointers
    three_pa: int = 0
    three_pm: int = 0
    three_pct: float = 0.0
    
    # Free Throws
    fta: int = 0
    ftm: int = 0
    ft_pct: float = 0.0
    
    # Other Stats
    ast: int = 0  # Assists
    reb: int = 0  # Rebounds
    fls: int = 0  # Fouls


class TeamScore(BaseModel):
    """Team score in a game"""
    team_id: int
    team_name: str
    points: int = 0
    fouls: int = 0
    timeouts: int = 0
    players: List[PlayerStats] = []


class ScoreboardResponse(BaseModel):
    """Live scoreboard response"""
    game_id: int
    status: str
    period: int
    home_team: TeamScore
    away_team: TeamScore
    last_event: Optional[GameEventDetail] = None
    updated_at: datetime


class BoxScoreResponse(BaseModel):
    """Box score (detailed stats) response"""
    game_id: int
    home_team: TeamScore
    away_team: TeamScore
    total_events: int
    game_status: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]


# ==================== Update forward references ====================

TeamDetail.model_rebuild()
GameDetail.model_rebuild()
