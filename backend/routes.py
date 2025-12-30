"""
API Routes for Scoring Basket
RESTful endpoints for teams, players, games, events, scoreboard, and box score
Integrated with WebSocket broadcasting
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import asyncio

from .database import get_db
from .models import Team, Player, Game, GameEvent
from .schemas import (
    TeamCreate, TeamUpdate, TeamResponse, TeamDetail,
    PlayerCreate, PlayerUpdate, PlayerResponse,
    GameCreate, GameResponse, GameDetail,
    GameEventCreate, GameEventResponse, GameEventDetail,
    ScoreboardResponse, BoxScoreResponse, TeamScore, PlayerStats,
)
from .services import (
    StatsCalculationService,
    GameStateService,
    EventValidationService,
    RepositoryService,
)

router = APIRouter(prefix="/api")


# ==================== TEAM ENDPOINTS ====================

@router.get("/teams", response_model=List[TeamResponse], tags=["teams"])
def list_teams(db = Depends(get_db)):
    """Get all teams"""
    teams = db.query(Team).all()
    return teams


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED, tags=["teams"])
def create_team(team: TeamCreate, db = Depends(get_db)):
    """Create a new team"""
    # Check if team already exists
    existing = db.query(Team).filter(Team.name == team.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team with this name already exists"
        )
    
    new_team = Team(name=team.name)
    db.add(new_team)
    db.commit()
    db.refresh(new_team)
    return new_team


@router.get("/teams/{team_id}", response_model=TeamDetail, tags=["teams"])
def get_team(team_id: int, db = Depends(get_db)):
    """Get team details with players"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.put("/teams/{team_id}", response_model=TeamResponse, tags=["teams"])
def update_team(team_id: int, team_data: TeamUpdate, db = Depends(get_db)):
    """Update team"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    if team_data.name:
        # Check if new name is already taken
        existing = db.query(Team).filter(
            Team.name == team_data.name,
            Team.id != team_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team with this name already exists"
            )
        team.name = team_data.name
    
    team.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(team)
    return team


# ==================== PLAYER ENDPOINTS ====================

@router.get("/teams/{team_id}/players", response_model=List[PlayerResponse], tags=["players"])
def list_players(team_id: int, db = Depends(get_db)):
    """Get all players for a team"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    players = db.query(Player).filter(Player.team_id == team_id).all()
    return players


@router.post("/teams/{team_id}/players", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED, tags=["players"])
def create_player(team_id: int, player: PlayerCreate, db = Depends(get_db)):
    """Add player to team"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Check if player number is unique in team
    existing = db.query(Player).filter(
        Player.team_id == team_id,
        Player.number == player.number
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Player number {player.number} already exists in {team.name}"
        )
    
    new_player = Player(
        team_id=team_id,
        name=player.name,
        number=player.number,
        position=player.position
    )
    db.add(new_player)
    db.commit()
    db.refresh(new_player)
    return new_player


@router.get("/players/{player_id}", response_model=PlayerResponse, tags=["players"])
def get_player(player_id: int, db = Depends(get_db)):
    """Get player details"""
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@router.put("/players/{player_id}", response_model=PlayerResponse, tags=["players"])
def update_player(player_id: int, player_data: PlayerUpdate, db = Depends(get_db)):
    """Update player"""
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    if player_data.name:
        player.name = player_data.name
    if player_data.number is not None:
        # Check if new number is unique in team
        existing = db.query(Player).filter(
            Player.team_id == player.team_id,
            Player.number == player_data.number,
            Player.id != player_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Player number {player_data.number} already exists in team"
            )
        player.number = player_data.number
    if player_data.position:
        player.position = player_data.position
    
    player.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(player)
    return player


# ==================== GAME ENDPOINTS ====================

@router.get("/games", response_model=List[GameResponse], tags=["games"])
def list_games(
    status: Optional[str] = Query(None),
    db = Depends(get_db)
):
    """Get all games, optionally filtered by status"""
    query = db.query(Game)
    if status:
        query = query.filter(Game.status == status)
    return query.all()


@router.post("/games", response_model=GameResponse, status_code=status.HTTP_201_CREATED, tags=["games"])
def create_game(game: GameCreate, db = Depends(get_db)):
    """Create a new game"""
    # Validate teams exist and are different
    home_team = db.query(Team).filter(Team.id == game.home_team_id).first()
    away_team = db.query(Team).filter(Team.id == game.away_team_id).first()
    
    if not home_team:
        raise HTTPException(status_code=404, detail="Home team not found")
    if not away_team:
        raise HTTPException(status_code=404, detail="Away team not found")
    if game.home_team_id == game.away_team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Home and away teams must be different"
        )
    
    new_game = Game(
        home_team_id=game.home_team_id,
        away_team_id=game.away_team_id,
        status="pending"
    )
    db.add(new_game)
    db.commit()
    db.refresh(new_game)
    return new_game


@router.get("/games/{game_id}", response_model=GameDetail, tags=["games"])
def get_game(game_id: int, db = Depends(get_db)):
    """Get game details with rosters and events"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@router.post("/games/{game_id}/start", response_model=GameResponse, tags=["games"])
async def start_game(game_id: int, db = Depends(get_db)):
    """Start a game (pending -> active)"""
    success, message, game = GameStateService.start_game(game_id, db)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    
    # Broadcast game status update
    try:
        from .websocket import broadcast_game_status_update
        asyncio.create_task(broadcast_game_status_update(game_id, "active"))
    except:
        pass  # WebSocket not available
    
    return game


@router.post("/games/{game_id}/end", response_model=GameResponse, tags=["games"])
async def end_game(game_id: int, db = Depends(get_db)):
    """End a game (active -> completed)"""
    success, message, game = GameStateService.end_game(game_id, db)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    
    # Broadcast game status update
    try:
        from .websocket import broadcast_game_status_update
        asyncio.create_task(broadcast_game_status_update(game_id, "completed"))
    except:
        pass  # WebSocket not available
    
    return game


# ==================== GAME EVENT ENDPOINTS ====================

@router.get("/games/{game_id}/events", response_model=List[GameEventDetail], tags=["events"])
def get_game_events(game_id: int, db = Depends(get_db)):
    """Get all events for a game"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    events = db.query(GameEvent).filter(
        GameEvent.game_id == game_id
    ).order_by(GameEvent.created_at).all()
    return events


@router.post("/games/{game_id}/events", response_model=GameEventResponse, status_code=status.HTTP_201_CREATED, tags=["events"])
async def record_event(game_id: int, event: GameEventCreate, db = Depends(get_db)):
    """Record a scoring event"""
    # Validate event
    is_valid, error_msg = EventValidationService.validate_event(
        game_id=game_id,
        player_id=event.player_id,
        team_id=event.team_id,
        event_type=event.event_type,
        period=event.period,
        db=db
    )
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    # Validate shot outcome if applicable
    if event.event_type in ["2PT", "3PT", "FT"]:
        is_valid, error_msg = EventValidationService.validate_shot_outcome(
            event.event_type,
            event.outcome
        )
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    new_event = GameEvent(
        game_id=game_id,
        player_id=event.player_id,
        team_id=event.team_id,
        event_type=event.event_type,
        period=event.period,
        timestamp=event.timestamp,
        outcome=event.outcome
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    
    # Broadcast event and scoreboard update
    try:
        from .websocket import broadcast_event_created, broadcast_scoreboard_update
        asyncio.create_task(broadcast_event_created(game_id, new_event.id))
        asyncio.create_task(broadcast_scoreboard_update(game_id))
    except:
        pass  # WebSocket not available
    
    return new_event


@router.delete("/games/{game_id}/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["events"])
async def undo_event(game_id: int, event_id: int, db = Depends(get_db)):
    """Undo (delete) the last event"""
    event = db.query(GameEvent).filter(
        GameEvent.id == event_id,
        GameEvent.game_id == game_id
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    db.delete(event)
    db.commit()
    
    # Broadcast event deletion and scoreboard update
    try:
        from .websocket import broadcast_event_deleted, broadcast_scoreboard_update
        asyncio.create_task(broadcast_event_deleted(game_id, event_id))
        asyncio.create_task(broadcast_scoreboard_update(game_id))
    except:
        pass  # WebSocket not available


# ==================== SCOREBOARD ENDPOINTS ====================

@router.get("/games/{game_id}/scoreboard", response_model=ScoreboardResponse, tags=["scoreboard"])
def get_scoreboard(game_id: int, db = Depends(get_db)):
    """Get live scoreboard with current scores and stats"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Get team stats
    home_stats = StatsCalculationService.get_team_stats(game_id, game.home_team_id, db)
    away_stats = StatsCalculationService.get_team_stats(game_id, game.away_team_id, db)
    
    # Get latest event
    latest_event = RepositoryService.get_latest_game_event(game_id, db)
    
    # Get current period
    current_period = GameStateService.get_current_period(game_id, db)
    
    return ScoreboardResponse(
        game_id=game_id,
        status=game.status,
        period=current_period,
        home_team=TeamScore(**home_stats),
        away_team=TeamScore(**away_stats),
        last_event=latest_event,
        updated_at=datetime.utcnow()
    )


# ==================== BOX SCORE ENDPOINTS ====================

@router.get("/games/{game_id}/boxscore", response_model=BoxScoreResponse, tags=["scoreboard"])
def get_boxscore(game_id: int, db = Depends(get_db)):
    """Get detailed box score (full game statistics)"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Get team stats
    home_stats = StatsCalculationService.get_team_stats(game_id, game.home_team_id, db)
    away_stats = StatsCalculationService.get_team_stats(game_id, game.away_team_id, db)
    
    # Count events
    event_count = db.query(GameEvent).filter(GameEvent.game_id == game_id).count()
    
    return BoxScoreResponse(
        game_id=game_id,
        home_team=TeamScore(**home_stats),
        away_team=TeamScore(**away_stats),
        total_events=event_count,
        game_status=game.status,
        started_at=game.started_at,
        ended_at=game.ended_at
    )


# ==================== HEALTH CHECK ====================

@router.get("/health", tags=["health"])
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.utcnow()}

router = APIRouter(prefix="/api")


# ==================== TEAM ENDPOINTS ====================

@router.get("/teams", response_model=List[TeamResponse], tags=["teams"])
def list_teams(db = Depends(get_db)):
    """Get all teams"""
    teams = db.query(Team).all()
    return teams


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED, tags=["teams"])
def create_team(team: TeamCreate, db = Depends(get_db)):
    """Create a new team"""
    # Check if team already exists
    existing = db.query(Team).filter(Team.name == team.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team with this name already exists"
        )
    
    new_team = Team(name=team.name)
    db.add(new_team)
    db.commit()
    db.refresh(new_team)
    return new_team


@router.get("/teams/{team_id}", response_model=TeamDetail, tags=["teams"])
def get_team(team_id: int, db = Depends(get_db)):
    """Get team details with players"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.put("/teams/{team_id}", response_model=TeamResponse, tags=["teams"])
def update_team(team_id: int, team_data: TeamUpdate, db = Depends(get_db)):
    """Update team"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    if team_data.name:
        # Check if new name is already taken
        existing = db.query(Team).filter(
            Team.name == team_data.name,
            Team.id != team_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team with this name already exists"
            )
        team.name = team_data.name
    
    team.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(team)
    return team


# ==================== PLAYER ENDPOINTS ====================

@router.get("/teams/{team_id}/players", response_model=List[PlayerResponse], tags=["players"])
def list_players(team_id: int, db = Depends(get_db)):
    """Get all players for a team"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    players = db.query(Player).filter(Player.team_id == team_id).all()
    return players


@router.post("/teams/{team_id}/players", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED, tags=["players"])
def create_player(team_id: int, player: PlayerCreate, db = Depends(get_db)):
    """Add player to team"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Check if player number is unique in team
    existing = db.query(Player).filter(
        Player.team_id == team_id,
        Player.number == player.number
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Player number {player.number} already exists in {team.name}"
        )
    
    new_player = Player(
        team_id=team_id,
        name=player.name,
        number=player.number,
        position=player.position
    )
    db.add(new_player)
    db.commit()
    db.refresh(new_player)
    return new_player


@router.get("/players/{player_id}", response_model=PlayerResponse, tags=["players"])
def get_player(player_id: int, db = Depends(get_db)):
    """Get player details"""
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@router.put("/players/{player_id}", response_model=PlayerResponse, tags=["players"])
def update_player(player_id: int, player_data: PlayerUpdate, db = Depends(get_db)):
    """Update player"""
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    if player_data.name:
        player.name = player_data.name
    if player_data.number is not None:
        # Check if new number is unique in team
        existing = db.query(Player).filter(
            Player.team_id == player.team_id,
            Player.number == player_data.number,
            Player.id != player_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Player number {player_data.number} already exists in team"
            )
        player.number = player_data.number
    if player_data.position:
        player.position = player_data.position
    
    player.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(player)
    return player


# ==================== GAME ENDPOINTS ====================

@router.get("/games", response_model=List[GameResponse], tags=["games"])
def list_games(
    status: Optional[str] = Query(None),
    db = Depends(get_db)
):
    """Get all games, optionally filtered by status"""
    query = db.query(Game)
    if status:
        query = query.filter(Game.status == status)
    return query.all()


@router.post("/games", response_model=GameResponse, status_code=status.HTTP_201_CREATED, tags=["games"])
def create_game(game: GameCreate, db = Depends(get_db)):
    """Create a new game"""
    # Validate teams exist and are different
    home_team = db.query(Team).filter(Team.id == game.home_team_id).first()
    away_team = db.query(Team).filter(Team.id == game.away_team_id).first()
    
    if not home_team:
        raise HTTPException(status_code=404, detail="Home team not found")
    if not away_team:
        raise HTTPException(status_code=404, detail="Away team not found")
    if game.home_team_id == game.away_team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Home and away teams must be different"
        )
    
    new_game = Game(
        home_team_id=game.home_team_id,
        away_team_id=game.away_team_id,
        status="pending"
    )
    db.add(new_game)
    db.commit()
    db.refresh(new_game)
    return new_game


@router.get("/games/{game_id}", response_model=GameDetail, tags=["games"])
def get_game(game_id: int, db = Depends(get_db)):
    """Get game details with rosters and events"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@router.post("/games/{game_id}/start", response_model=GameResponse, tags=["games"])
def start_game(game_id: int, db = Depends(get_db)):
    """Start a game (pending -> active)"""
    success, message, game = GameStateService.start_game(game_id, db)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return game


@router.post("/games/{game_id}/end", response_model=GameResponse, tags=["games"])
def end_game(game_id: int, db = Depends(get_db)):
    """End a game (active -> completed)"""
    success, message, game = GameStateService.end_game(game_id, db)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return game


# ==================== GAME EVENT ENDPOINTS ====================

@router.get("/games/{game_id}/events", response_model=List[GameEventDetail], tags=["events"])
def get_game_events(game_id: int, db = Depends(get_db)):
    """Get all events for a game"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    events = db.query(GameEvent).filter(
        GameEvent.game_id == game_id
    ).order_by(GameEvent.created_at).all()
    return events


@router.post("/games/{game_id}/events", response_model=GameEventResponse, status_code=status.HTTP_201_CREATED, tags=["events"])
def record_event(game_id: int, event: GameEventCreate, db = Depends(get_db)):
    """Record a scoring event"""
    # Validate event
    is_valid, error_msg = EventValidationService.validate_event(
        game_id=game_id,
        player_id=event.player_id,
        team_id=event.team_id,
        event_type=event.event_type,
        period=event.period,
        db=db
    )
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    # Validate shot outcome if applicable
    if event.event_type in ["2PT", "3PT", "FT"]:
        is_valid, error_msg = EventValidationService.validate_shot_outcome(
            event.event_type,
            event.outcome
        )
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    new_event = GameEvent(
        game_id=game_id,
        player_id=event.player_id,
        team_id=event.team_id,
        event_type=event.event_type,
        period=event.period,
        timestamp=event.timestamp,
        outcome=event.outcome
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event


@router.delete("/games/{game_id}/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["events"])
def undo_event(game_id: int, event_id: int, db = Depends(get_db)):
    """Undo (delete) the last event"""
    event = db.query(GameEvent).filter(
        GameEvent.id == event_id,
        GameEvent.game_id == game_id
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    db.delete(event)
    db.commit()


# ==================== SCOREBOARD ENDPOINTS ====================

@router.get("/games/{game_id}/scoreboard", response_model=ScoreboardResponse, tags=["scoreboard"])
def get_scoreboard(game_id: int, db = Depends(get_db)):
    """Get live scoreboard with current scores and stats"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Get team stats
    home_stats = StatsCalculationService.get_team_stats(game_id, game.home_team_id, db)
    away_stats = StatsCalculationService.get_team_stats(game_id, game.away_team_id, db)
    
    # Get latest event
    latest_event = RepositoryService.get_latest_game_event(game_id, db)
    
    # Get current period
    current_period = GameStateService.get_current_period(game_id, db)
    
    return ScoreboardResponse(
        game_id=game_id,
        status=game.status,
        period=current_period,
        home_team=TeamScore(**home_stats),
        away_team=TeamScore(**away_stats),
        last_event=latest_event,
        updated_at=datetime.utcnow()
    )


# ==================== BOX SCORE ENDPOINTS ====================

@router.get("/games/{game_id}/boxscore", response_model=BoxScoreResponse, tags=["scoreboard"])
def get_boxscore(game_id: int, db = Depends(get_db)):
    """Get detailed box score (full game statistics)"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Get team stats
    home_stats = StatsCalculationService.get_team_stats(game_id, game.home_team_id, db)
    away_stats = StatsCalculationService.get_team_stats(game_id, game.away_team_id, db)
    
    # Count events
    event_count = db.query(GameEvent).filter(GameEvent.game_id == game_id).count()
    
    return BoxScoreResponse(
        game_id=game_id,
        home_team=TeamScore(**home_stats),
        away_team=TeamScore(**away_stats),
        total_events=event_count,
        game_status=game.status,
        started_at=game.started_at,
        ended_at=game.ended_at
    )


# ==================== HEALTH CHECK ====================

@router.get("/health", tags=["health"])
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.utcnow()}
