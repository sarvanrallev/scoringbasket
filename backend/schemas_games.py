"""
Pydantic schemas for match and tournament features
Used for request validation and response serialization
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============================================================================
# TEAM SCHEMAS
# ============================================================================

class PlayerCreate(BaseModel):
    """Create player request"""
    user_id: int
    jersey_number: Optional[int] = None
    position: Optional[str] = None  # PG, SG, SF, PF, C
    status: str = "active"

    class Config:
        schema_extra = {
            "example": {
                "user_id": 5,
                "jersey_number": 23,
                "position": "SG",
                "status": "active"
            }
        }


class PlayerResponse(BaseModel):
    """Player response"""
    id: int
    user_id: int
    team_id: int
    name: str
    number: Optional[int]
    position: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TeamCreate(BaseModel):
    """Create team request"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    city: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "Lakers",
                "description": "Downtown basketball team",
                "city": "Los Angeles"
            }
        }


class TeamUpdate(BaseModel):
    """Update team request"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    city: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "Lakers",
                "description": "Updated description",
                "city": "Los Angeles"
            }
        }


class SimpleTeamResponse(BaseModel):
    """Simplified team response for nested usage"""
    id: int
    name: str
    description: Optional[str] = None
    owner_id: Optional[int] = None
    city: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TeamResponse(BaseModel):
    """Team response"""
    id: int
    name: str
    description: Optional[str]
    owner_id: Optional[int]
    city: Optional[str]
    wins: int = 0
    losses: int = 0
    created_at: datetime
    captain: Optional[dict] = None  # { "id": int, "name": str }
    player_count: int = 0

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": 1,
                "name": "Lakers",
                "description": "Professional team",
                "owner_id": 2,
                "city": "Los Angeles",
                "wins": 15,
                "losses": 5,
                "created_at": "2025-12-26T10:30:00",
                "captain": {"id": 2, "name": "John Doe"},
                "player_count": 12
            }
        }


class TeamDetailsResponse(BaseModel):
    """Team with full details including players"""
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    city: Optional[str]
    wins: int
    losses: int
    players: List[PlayerResponse]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# TEAM MEMBERSHIP SCHEMAS
# ============================================================================

class TeamMemberInvite(BaseModel):
    """Invite user to team by phone number"""
    phone: str = Field(..., pattern=r'^\+?1?\d{9,15}$')

    class Config:
        schema_extra = {
            "example": {
                "phone": "+1234567890"
            }
        }


class TeamMemberUpdateRole(BaseModel):
    """Update team member roles"""
    is_admin: Optional[bool] = None
    is_captain: Optional[bool] = None
    is_vice_captain: Optional[bool] = None

    class Config:
        schema_extra = {
            "example": {
                "is_admin": True,
                "is_captain": True,
                "is_vice_captain": False
            }
        }


class TeamMemberResponse(BaseModel):
    """Team member response"""
    id: int
    user_id: int
    username: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_admin: bool
    is_captain: bool
    is_vice_captain: bool
    status: str
    joined_at: datetime

    class Config:
        from_attributes = True


class TeamLeadershipHistoryResponse(BaseModel):
    """Team leadership history response"""
    id: int
    team_id: int
    user_id: int
    username: str
    first_name: Optional[str]
    last_name: Optional[str]
    role: str  # 'captain' or 'vice_captain'
    action: str  # 'assigned' or 'removed'
    assigned_by_username: Optional[str]
    assigned_at: datetime
    notes: Optional[str]

    class Config:
        from_attributes = True


class TeamWithMembersResponse(BaseModel):
    """Team with members response"""
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    city: Optional[str]
    wins: int
    losses: int
    members: List[TeamMemberResponse]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# MATCH SCHEMAS
# ============================================================================

class GameEventCreate(BaseModel):
    """Create match event request"""
    user_id: Optional[int] = None  # Optional for team events like timeout
    team_id: int
    event_type: str  # 2PT, 3PT, FT, AST, REB, FLS, SUB, TO, PERIOD_START, PERIOD_END
    period: int = Field(..., ge=1, le=5)  # 1-4 + OT
    timestamp: int = Field(..., ge=0)  # seconds in period
    outcome: Optional[str] = None  # made, miss (for shots only)

    class Config:
        schema_extra = {
            "example": {
                "user_id": 5,
                "team_id": 1,
                "event_type": "2PT",
                "period": 1,
                "timestamp": 125,
                "outcome": "made"
            }
        }


class GameEventResponse(BaseModel):
    """Match event response"""
    id: int
    game_id: int
    user_id: Optional[int]
    team_id: int
    event_type: str
    period: int
    timestamp: Optional[int]
    outcome: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class GamePlayerCreate(BaseModel):
    """Create match player request"""
    user_id: int
    jersey_number: Optional[int] = None
    position: Optional[str] = None  # PG, SG, SF, PF, C
    is_starter: bool = False

    class Config:
        schema_extra = {
            "example": {
                "user_id": 5,
                "jersey_number": 23,
                "position": "SG",
                "is_starter": True
            }
        }


class GamePlayerResponse(BaseModel):
    """Match player response"""
    id: int
    game_id: int
    user_id: int
    team_id: int
    name: str
    jersey_number: Optional[int]
    position: Optional[str]
    is_starter: bool
    minutes_played: int
    created_at: datetime

    class Config:
        from_attributes = True


class GameCreate(BaseModel):
    """Create match request"""
    home_team_id: int
    away_team_id: int
    match_date: datetime
    title: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    tournament_id: Optional[int] = None
    home_players: List[GamePlayerCreate] = []
    away_players: List[GamePlayerCreate] = []

    class Config:
        schema_extra = {
            "example": {
                "home_team_id": 1,
                "away_team_id": 2,
                "match_date": "2025-12-27T19:00:00",
                "title": "Lakers vs Celtics",
                "location": "Crypto.com Arena",
                "tournament_id": None,
                "home_players": [
                    {"user_id": 5, "jersey_number": 23, "position": "SG", "is_starter": True},
                    {"user_id": 6, "jersey_number": 11, "position": "PG", "is_starter": True}
                ],
                "away_players": [
                    {"user_id": 7, "jersey_number": 7, "position": "SF", "is_starter": True},
                    {"user_id": 8, "jersey_number": 13, "position": "C", "is_starter": True}
                ]
            }
        }


class GameUpdate(BaseModel):
    """Update match request"""
    title: Optional[str] = None
    location: Optional[str] = None
    match_date: Optional[datetime] = None
    status: Optional[str] = None  # scheduled, in_progress, completed, cancelled

    class Config:
        schema_extra = {
            "example": {
                "title": "Lakers vs Celtics",
                "location": "Crypto.com Arena",
                "status": "in_progress"
            }
        }


class GameResponse(BaseModel):
    """Match response"""
    id: int
    title: Optional[str]
    description: Optional[str]
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int
    status: str
    match_date: Optional[datetime]
    location: Optional[str]
    tournament_id: Optional[int]
    timeout_active: bool
    timeout_started_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    home_team: Optional['SimpleTeamResponse'] = None
    away_team: Optional['SimpleTeamResponse'] = None

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": 1,
                "title": "Lakers vs Celtics",
                "home_team_id": 1,
                "away_team_id": 2,
                "home_score": 98,
                "away_score": 95,
                "status": "completed",
                "match_date": "2025-12-27T19:00:00",
                "location": "Crypto.com Arena",
                "tournament_id": None,
                "created_at": "2025-12-26T10:00:00",
                "updated_at": "2025-12-26T21:30:00"
            }
        }


class PlayerScorerResponse(BaseModel):
    """Player scorer response"""
    user_id: int
    name: str
    points: int

    class Config:
        schema_extra = {
            "example": {
                "user_id": 1,
                "name": "John Doe",
                "points": 25
            }
        }


class PlayerFoulResponse(BaseModel):
    """Player foul response"""
    user_id: int
    name: str
    fouls: int

    class Config:
        schema_extra = {
            "example": {
                "user_id": 2,
                "name": "Jane Smith",
                "fouls": 4
            }
        }


class GameStatsResponse(BaseModel):
    """Game statistics response with top scorers and foul scorers"""
    game_id: int
    home_team_top_scorers: List[PlayerScorerResponse]
    away_team_top_scorers: List[PlayerScorerResponse]
    top_foul_scorers: List[PlayerFoulResponse]

    class Config:
        schema_extra = {
            "example": {
                "game_id": 1,
                "home_team_top_scorers": [
                    {"user_id": 1, "name": "John Doe", "points": 25},
                    {"user_id": 3, "name": "Mike Johnson", "points": 18}
                ],
                "away_team_top_scorers": [
                    {"user_id": 2, "name": "Jane Smith", "points": 22},
                    {"user_id": 4, "name": "Sarah Williams", "points": 19}
                ],
                "top_foul_scorers": [
                    {"user_id": 2, "name": "Jane Smith", "fouls": 4},
                    {"user_id": 3, "name": "Mike Johnson", "fouls": 3}
                ]
            }
        }


# ============================================================================
# TOURNAMENT SCHEMAS
# ============================================================================

class TournamentCreate(BaseModel):
    """Create tournament request"""
    title: str = Field(..., min_length=1, max_length=255)
    format: str = "single_elimination"  # single_elimination, double_elimination, round_robin
    start_date: datetime
    description: Optional[str] = None
    location: Optional[str] = None
    max_teams: Optional[int] = None
    end_date: Optional[datetime] = None
    entry_fee: float = 0.0
    prize_pool: float = 0.0
    rules: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "title": "Winter Basketball Championship",
                "format": "single_elimination",
                "start_date": "2025-12-27T09:00:00",
                "location": "Downtown Arena",
                "max_teams": 16,
                "entry_fee": 100.0,
                "prize_pool": 5000.0
            }
        }


class TournamentUpdate(BaseModel):
    """Update tournament request"""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None  # planning, registration, in_progress, completed
    end_date: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "title": "Winter Championship",
                "status": "in_progress"
            }
        }


class BracketResponse(BaseModel):
    """Tournament bracket response"""
    id: int
    tournament_id: int
    current_round: int
    total_rounds: int
    bracket_data: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TournamentResponse(BaseModel):
    """Tournament response"""
    id: int
    title: str
    description: Optional[str]
    organizer_id: int
    status: str
    format: str
    start_date: Optional[str]
    end_date: Optional[str]
    location: Optional[str]
    max_teams: Optional[int]
    entry_fee: float
    prize_pool: float
    rules: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": 1,
                "title": "Winter Basketball Championship",
                "organizer_id": 1,
                "status": "in_progress",
                "format": "single_elimination",
                "start_date": "2025-12-27T09:00:00",
                "location": "Downtown Arena",
                "max_teams": 16,
                "entry_fee": 100.0,
                "prize_pool": 5000.0,
                "created_at": "2025-12-26T10:00:00",
                "updated_at": "2025-12-26T15:00:00"
            }
        }


# ============================================================================
# COMBINED RESPONSES
# ============================================================================

class GameDetailsResponse(BaseModel):
    """Match with full details"""
    id: int
    title: str
    home_team_id: int
    away_team_id: int
    created_by: Optional[int]
    home_score: int
    away_score: int
    status: str
    match_date: datetime
    location: Optional[str]
    home_team: Optional["TeamResponse"]
    away_team: Optional["TeamResponse"]
    home_players: List[GamePlayerResponse]
    away_players: List[GamePlayerResponse]
    events: List[GameEventResponse]

    class Config:
        from_attributes = True


class PlayerStatsResponse(BaseModel):
    """Player statistics for a specific match"""
    player_id: int
    total_points: int
    field_goals: int
    three_pointers: int
    free_throws: int
    fouls: int
    rebounds: int
    assists: int
    steals: int
    blocks: int

    class Config:
        schema_extra = {
            "example": {
                "player_id": 5,
                "total_points": 28,
                "field_goals": 10,
                "three_pointers": 2,
                "free_throws": 6,
                "fouls": 3,
                "rebounds": 7,
                "assists": 4,
                "steals": 2,
                "blocks": 1
            }
        }


# ============================================================================
# PLAYER GAME STATS SCHEMAS
# ============================================================================

class PlayerGameStatsResponse(BaseModel):
    """Player game stats response"""
    id: int
    player_id: int
    game_id: int
    points: int
    assists: int
    rebounds: int
    fouls: int
    violations: int
    shots_made: int
    shots_attempted: int
    two_pointers_made: int
    two_pointers_attempted: int
    three_pointers_made: int
    three_pointers_attempted: int
    free_throws_made: int
    free_throws_attempted: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserStatsResponse(BaseModel):
    """User career stats response"""
    user_id: int
    total_games: int
    total_points: int
    average_points_per_game: float
    total_assists: int
    total_rebounds: int
    total_fouls: int
    total_violations: int
    total_shots_made: int
    total_shots_attempted: int
    career_shooting_percentage: float

    class Config:
        from_attributes = True


class FinalizeGameResponse(BaseModel):
    """Finalize game response with player stats"""
    game_id: int
    status: str
    player_stats: List[PlayerGameStatsResponse]
    home_team_name: str
    away_team_name: str
    home_score: int
    away_score: int
    message: str

    class Config:
        from_attributes = True


class PlayerStatsSummaryResponse(BaseModel):
    """Response schema for aggregated player statistics"""
    user_id: int
    total_games: int
    total_points: int
    average_points_per_game: float
    total_assists: int
    total_rebounds: int
    total_fouls: int
    total_violations: int
    total_shots_made: int
    total_shots_attempted: int
    career_shooting_percentage: float

    class Config:
        from_attributes = True


