"""
Business Logic Services for Scoring Basket
Handles stats calculation, game state management, and event validation
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from .models import Team, Player, Game, GameEvent
from .schemas import PlayerStats, TeamScore, EventType


class StatsCalculationService:
    """Service for calculating player and team statistics"""

    @staticmethod
    def calculate_points(game_id: int, player_id: int, db: Session) -> int:
        """
        Calculate total points for a player in a game
        2PT shots = 2 points, 3PT shots = 3 points, FT = 1 point
        Only count "made" outcomes
        """
        events = db.query(GameEvent).filter(
            GameEvent.game_id == game_id,
            GameEvent.player_id == player_id,
        ).all()
        
        points = 0
        for event in events:
            if event.outcome == "made":
                if event.event_type == "2PT":
                    points += 2
                elif event.event_type == "3PT":
                    points += 3
                elif event.event_type == "FT":
                    points += 1
        
        return points

    @staticmethod
    def calculate_field_goals(game_id: int, player_id: int, event_type: str, db: Session) -> Tuple[int, int]:
        """
        Calculate field goal attempts and makes
        Returns (made, attempts)
        """
        events = db.query(GameEvent).filter(
            GameEvent.game_id == game_id,
            GameEvent.player_id == player_id,
            GameEvent.event_type == event_type,
        ).all()
        
        made = sum(1 for e in events if e.outcome == "made")
        attempts = len(events)
        
        return made, attempts

    @staticmethod
    def calculate_percentage(made: int, attempts: int) -> float:
        """Calculate shooting percentage"""
        if attempts == 0:
            return 0.0
        return round((made / attempts) * 100, 1)

    @staticmethod
    def calculate_assists(game_id: int, player_id: int, db: Session) -> int:
        """Count assists for a player in a game"""
        count = db.query(GameEvent).filter(
            GameEvent.game_id == game_id,
            GameEvent.player_id == player_id,
            GameEvent.event_type == "AST",
        ).count()
        return count

    @staticmethod
    def calculate_rebounds(game_id: int, player_id: int, db: Session) -> int:
        """Count rebounds for a player in a game"""
        count = db.query(GameEvent).filter(
            GameEvent.game_id == game_id,
            GameEvent.player_id == player_id,
            GameEvent.event_type == "REB",
        ).count()
        return count

    @staticmethod
    def calculate_fouls(game_id: int, player_id: int, db: Session) -> int:
        """Count fouls for a player in a game"""
        count = db.query(GameEvent).filter(
            GameEvent.game_id == game_id,
            GameEvent.player_id == player_id,
            GameEvent.event_type == "FLS",
        ).count()
        return count

    @staticmethod
    def get_player_stats(game_id: int, player_id: int, db: Session) -> Dict:
        """
        Calculate all stats for a player in a game
        Returns comprehensive stats dictionary
        """
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return None
        
        # Get roster status
        roster = db.query(GameRoster).filter(
            GameRoster.game_id == game_id,
            GameRoster.player_id == player_id,
        ).first()
        status = roster.status if roster else "unknown"
        
        # Calculate field goals (all 2PT and 3PT combined)
        fga = 0
        fgm = 0
        
        two_pt_made, two_pt_attempts = StatsCalculationService.calculate_field_goals(
            game_id, player_id, "2PT", db
        )
        three_pt_made, three_pt_attempts = StatsCalculationService.calculate_field_goals(
            game_id, player_id, "3PT", db
        )
        
        fga = two_pt_attempts + three_pt_attempts
        fgm = two_pt_made + three_pt_made
        
        # Calculate free throws
        ft_made, ft_attempts = StatsCalculationService.calculate_field_goals(
            game_id, player_id, "FT", db
        )
        
        # Calculate points
        points = StatsCalculationService.calculate_points(game_id, player_id, db)
        
        # Calculate other stats
        assists = StatsCalculationService.calculate_assists(game_id, player_id, db)
        rebounds = StatsCalculationService.calculate_rebounds(game_id, player_id, db)
        fouls = StatsCalculationService.calculate_fouls(game_id, player_id, db)
        
        return {
            "player_id": player_id,
            "name": player.name,
            "number": player.number,
            "position": player.position,
            "status": status,
            "points": points,
            "fga": fga,
            "fgm": fgm,
            "fg_pct": StatsCalculationService.calculate_percentage(fgm, fga),
            "three_pa": three_pt_attempts,
            "three_pm": three_pt_made,
            "three_pct": StatsCalculationService.calculate_percentage(three_pt_made, three_pt_attempts),
            "fta": ft_attempts,
            "ftm": ft_made,
            "ft_pct": StatsCalculationService.calculate_percentage(ft_made, ft_attempts),
            "ast": assists,
            "reb": rebounds,
            "fls": fouls,
        }

    @staticmethod
    def get_team_stats(game_id: int, team_id: int, db: Session) -> Dict:
        """
        Calculate aggregated stats for a team in a game
        Returns team score and player stats
        """
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            return None
        
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return None
        
        # Get all players in this game for this team
        rosters = db.query(GameRoster).join(Player).filter(
            GameRoster.game_id == game_id,
            Player.team_id == team_id,
        ).all()
        
        team_points = 0
        team_fouls = 0
        team_timeouts = 0
        player_stats = []
        
        for roster in rosters:
            player_stat = StatsCalculationService.get_player_stats(
                game_id, roster.player_id, db
            )
            if player_stat:
                player_stats.append(player_stat)
                team_points += player_stat["points"]
                team_fouls += player_stat["fls"]
        
        # Count timeouts (team-level events)
        team_timeouts = db.query(GameEvent).filter(
            GameEvent.game_id == game_id,
            GameEvent.team_id == team_id,
            GameEvent.event_type == "TO",
        ).count()
        
        return {
            "team_id": team_id,
            "team_name": team.name,
            "points": team_points,
            "fouls": team_fouls,
            "timeouts": team_timeouts,
            "players": player_stats,
        }


class GameStateService:
    """Service for managing game state and transitions"""

    # Valid status transitions
    VALID_TRANSITIONS = {
        "pending": ["active"],
        "active": ["completed", "pending"],  # Allow pausing
        "completed": [],  # No transitions from completed
    }

    @staticmethod
    def can_transition(from_status: str, to_status: str) -> bool:
        """Check if game can transition from one status to another"""
        allowed = GameStateService.VALID_TRANSITIONS.get(from_status, [])
        return to_status in allowed

    @staticmethod
    def start_game(game_id: int, db: Session) -> Tuple[bool, str, Optional[Game]]:
        """
        Start a game (pending -> active)
        Returns (success, message, game)
        """
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return False, "Game not found", None
        
        if game.status == "active":
            return False, "Game is already active", None
        
        if not GameStateService.can_transition(game.status, "active"):
            return False, f"Cannot transition from {game.status} to active", None
        
        # Check if roster has players
        roster_count = db.query(GameRoster).filter(
            GameRoster.game_id == game_id
        ).count()
        if roster_count == 0:
            return False, "Game has no players in roster", None
        
        game.status = "active"
        game.started_at = datetime.utcnow()
        db.commit()
        
        return True, "Game started successfully", game

    @staticmethod
    def end_game(game_id: int, db: Session) -> Tuple[bool, str, Optional[Game]]:
        """
        End a game (active -> completed)
        Returns (success, message, game)
        """
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return False, "Game not found", None
        
        if game.status == "completed":
            return False, "Game is already completed", None
        
        if not GameStateService.can_transition(game.status, "completed"):
            return False, f"Cannot transition from {game.status} to completed", None
        
        game.status = "completed"
        game.ended_at = datetime.utcnow()
        db.commit()
        
        return True, "Game ended successfully", game

    @staticmethod
    def get_current_period(game_id: int, db: Session) -> int:
        """
        Get current period based on PERIOD_START/PERIOD_END events
        Returns period number (1-5)
        """
        period_start_events = db.query(GameEvent).filter(
            GameEvent.game_id == game_id,
            GameEvent.event_type == "PERIOD_START",
        ).order_by(GameEvent.created_at.desc()).first()
        
        if not period_start_events:
            return 1  # Default to period 1
        
        return period_start_events.period


class EventValidationService:
    """Service for validating game events before recording"""

    @staticmethod
    def validate_event(game_id: int, player_id: Optional[int], team_id: int,
                      event_type: str, period: int, db: Session) -> Tuple[bool, str]:
        """
        Validate a game event before recording
        Returns (is_valid, error_message)
        """
        # Validate game exists and is active
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            return False, "Game not found"
        
        if game.status != "active":
            return False, f"Game is {game.status}, not active"
        
        # Validate period is valid (1-5)
        if period < 1 or period > 5:
            return False, "Period must be between 1 and 5"
        
        # Validate team exists
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team:
            return False, "Team not found"
        
        # Validate team is in this game
        is_team_in_game = (
            (game.home_team_id == team_id or game.away_team_id == team_id)
        )
        if not is_team_in_game:
            return False, "Team is not in this game"
        
        # Events that require a player
        player_required_events = ["2PT", "3PT", "FT", "AST", "REB", "FLS", "SUB"]
        
        if event_type in player_required_events:
            if not player_id:
                return False, f"Event type {event_type} requires a player"
            
            # Validate player exists
            player = db.query(Player).filter(Player.id == player_id).first()
            if not player:
                return False, "Player not found"
            
            # Validate player is in game roster
            roster = db.query(GameRoster).filter(
                GameRoster.game_id == game_id,
                GameRoster.player_id == player_id,
            ).first()
            if not roster:
                return False, "Player is not in game roster"
            
            # Validate player's team matches event team
            if player.team_id != team_id:
                return False, "Player does not belong to the event team"
            
            # Validate foul count doesn't exceed 6 (disqualification)
            foul_count = db.query(GameEvent).filter(
                GameEvent.game_id == game_id,
                GameEvent.player_id == player_id,
                GameEvent.event_type == "FLS",
            ).count()
            
            if event_type == "FLS" and foul_count >= 6:
                return False, "Player has been disqualified (6 fouls)"
        
        # Validate event type
        valid_events = ["2PT", "3PT", "FT", "AST", "REB", "FLS", "SUB", "TO", "PERIOD_START", "PERIOD_END"]
        if event_type not in valid_events:
            return False, f"Invalid event type: {event_type}"
        
        return True, ""

    @staticmethod
    def validate_shot_outcome(event_type: str, outcome: str) -> Tuple[bool, str]:
        """
        Validate shot outcome (made/miss)
        Relevant for 2PT, 3PT, FT
        """
        shot_events = ["2PT", "3PT", "FT"]
        
        if event_type in shot_events:
            if outcome not in ["made", "miss"]:
                return False, f"Shot event must have outcome 'made' or 'miss', got '{outcome}'"
        
        return True, ""


class RepositoryService:
    """Service for common database queries"""

    @staticmethod
    def get_game_with_details(game_id: int, db: Session) -> Optional[Game]:
        """Get game with all related data"""
        return db.query(Game).filter(Game.id == game_id).first()

    @staticmethod
    def get_game_events(game_id: int, db: Session) -> List[GameEvent]:
        """Get all events for a game ordered by creation"""
        return db.query(GameEvent).filter(
            GameEvent.game_id == game_id
        ).order_by(GameEvent.created_at).all()

    @staticmethod
    def get_latest_game_event(game_id: int, db: Session) -> Optional[GameEvent]:
        """Get the most recent event for a game"""
        return db.query(GameEvent).filter(
            GameEvent.game_id == game_id
        ).order_by(GameEvent.created_at.desc()).first()

    @staticmethod
    def count_player_events(game_id: int, player_id: int, event_type: str, db: Session) -> int:
        """Count events of a specific type for a player"""
        return db.query(GameEvent).filter(
            GameEvent.game_id == game_id,
            GameEvent.player_id == player_id,
            GameEvent.event_type == event_type,
        ).count()
