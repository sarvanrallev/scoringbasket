"""
Game and Tournament Service Layer
Handles all business logic for matches, teams, and tournaments
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, and_, or_
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from typing import List, Optional, Dict
import json

from .models import (
    Team, Player, Game, GameEvent, GamePlayer,
    Tournament, TournamentTeam, TournamentBracket, User,
    TeamMember, TeamLeadershipHistory, PlayerGameStats
)


class GameService:
    """Service for managing games, teams, and tournaments"""

    def __init__(self, db: Session):
        self.db = db

    # ========================================================================
    # TEAM MANAGEMENT
    # ========================================================================

    def create_team(self, owner_id: int, name: str, description: str = None, city: str = None) -> Dict:
        """Create a new team"""
        try:
            team = Team(
                name=name,
                description=description,
                owner_id=owner_id,
                city=city
            )
            self.db.add(team)
            self.db.commit()
            self.db.refresh(team)
            
            # Calculate wins and losses (initially 0 for new team)
            return {
                "id": team.id,
                "name": team.name,
                "description": team.description,
                "owner_id": team.owner_id,
                "city": team.city,
                "wins": 0,
                "losses": 0,
                "created_at": team.created_at.isoformat(),
                "is_admin": True  # Creator is always admin
            }
        except IntegrityError as e:
            self.db.rollback()
            if "ix_teams_name" in str(e):
                raise Exception("A team with this name already exists. Please choose a different name.")
            else:
                raise Exception(f"Database constraint violation: {str(e)}")
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Error creating team: {str(e)}")

    def update_team(self, team_id: int, name: str = None, description: str = None, city: str = None) -> Team:
        """Update team information"""
        try:
            team = self.db.query(Team).filter(Team.id == team_id).first()
            if not team:
                raise Exception("Team not found")

            if name:
                team.name = name
            if description is not None:
                team.description = description
            if city is not None:
                team.city = city
            team.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(team)
            return team
        except Exception as e:
            self.db.rollback()
            raise

    def delete_team(self, team_id: int) -> bool:
        """Delete a team"""
        try:
            team = self.db.query(Team).filter(Team.id == team_id).first()
            if not team:
                raise Exception("Team not found")

            # Delete related records first
            self.db.query(TeamLeadershipHistory).filter(TeamLeadershipHistory.team_id == team_id).delete()
            self.db.query(TeamMember).filter(TeamMember.team_id == team_id).delete()

            self.db.delete(team)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise

    def get_team(self, team_id: int) -> Dict:
        """Get team details with calculated stats"""
        from .models import TeamMember, User, Player
        
        team = self.db.query(Team).filter(Team.id == team_id).first()
        if not team:
            return None
            
        # Calculate wins and losses from completed matches
        home_matches = self.db.query(Game).filter(
            Game.home_team_id == team_id,
            Game.status == "completed"
        ).all()
        
        away_matches = self.db.query(Game).filter(
            Game.away_team_id == team_id,
            Game.status == "completed"
        ).all()
        
        wins = 0
        losses = 0
        
        # Calculate home wins/losses
        for match in home_matches:
            if match.home_score > match.away_score:
                wins += 1
            elif match.home_score < match.away_score:
                losses += 1
        
        # Calculate away wins/losses
        for match in away_matches:
            if match.away_score > match.home_score:
                wins += 1
            elif match.away_score < match.home_score:
                losses += 1
        
        # Get captain info
        captain_member = self.db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.is_captain == True,
            TeamMember.status == "active"
        ).first()
        
        captain = None
        if captain_member:
            captain_user = self.db.query(User).filter(User.id == captain_member.user_id).first()
            if captain_user:
                captain = {
                    "id": captain_user.id,
                    "name": f"{captain_user.first_name} {captain_user.last_name}".strip() or captain_user.username
                }
        
        # Count players
        player_count = self.db.query(Player).filter(Player.team_id == team_id).count()
        
        return {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "owner_id": team.owner_id,
            "city": team.city,
            "wins": wins,
            "losses": losses,
            "created_at": team.created_at.isoformat(),
            "captain": captain,
            "player_count": player_count
        }

    def get_user_teams(self, user_id: int) -> List[Dict]:
        """Get all teams owned by a user with stats"""
        from .models import TeamMember, User
        
        teams = self.db.query(Team).filter(Team.owner_id == user_id).all()
        result = []
        
        for team in teams:
            # Get captain info
            captain_member = self.db.query(TeamMember).filter(
                TeamMember.team_id == team.id,
                TeamMember.is_captain == True,
                TeamMember.status == "active"
            ).first()
            
            captain = None
            if captain_member:
                captain_user = self.db.query(User).filter(User.id == captain_member.user_id).first()
                if captain_user:
                    captain = {
                        "id": captain_user.id,
                        "name": f"{captain_user.first_name} {captain_user.last_name}".strip() or captain_user.username
                    }
            
            # Count players
            player_count = self.db.query(Player).filter(Player.team_id == team.id).count()
            
            result.append({
                "id": team.id,
                "name": team.name,
                "description": team.description,
                "owner_id": team.owner_id,
                "city": team.city,
                "wins": 0,  # TODO: Calculate from match results
                "losses": 0,  # TODO: Calculate from match results
                "created_at": team.created_at.isoformat(),
                "is_admin": True,  # Owner is always admin
                "captain": captain,
                "player_count": player_count
            })
        
        return result

    def add_player_to_team(self, team_id: int, user_id: int, jersey_number: int = None, position: str = None, status: str = "active") -> Player:
        """Add a player to a team"""
        try:
            # Check if player already on team
            existing = self.db.query(Player).filter(
                and_(Player.user_id == user_id, Player.team_id == team_id)
            ).first()
            if existing:
                raise Exception("Player already on team")

            # Get user for name
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise Exception("User not found")
            
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username

            player = Player(
                user_id=user_id,
                team_id=team_id,
                name=name,
                number=jersey_number,
                position=position
            )
            self.db.add(player)
            self.db.commit()
            self.db.refresh(player)
            return player
        except Exception as e:
            self.db.rollback()
            raise

    def remove_player_from_team(self, team_id: int, user_id: int) -> bool:
        """Remove a player from a team"""
        try:
            player = self.db.query(Player).filter(
                and_(Player.user_id == user_id, Player.team_id == team_id)
            ).first()
            if not player:
                raise Exception("Player not found on team")

            self.db.delete(player)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise

    def get_team_players(self, team_id: int) -> List[Player]:
        """Get all players on a team"""
        return self.db.query(Player).filter(Player.team_id == team_id).all()

    def get_player(self, player_id: int) -> Optional[Player]:
        """Get a player by ID"""
        return self.db.query(Player).filter(Player.id == player_id).first()

    def is_player_on_team(self, user_id: int, team_id: int) -> bool:
        """Check if user is on team"""
        return self.db.query(Player).filter(
            and_(Player.user_id == user_id, Player.team_id == team_id)
        ).first() is not None

    # ========================================================================
    # MATCH MANAGEMENT
    # ========================================================================

    def create_match(self, home_team_id: int, away_team_id: int, match_date: datetime, 
                     created_by: int, title: str = None, location: str = None, 
                     description: str = None, tournament_id: int = None,
                     home_players: List[Dict] = None, away_players: List[Dict] = None) -> Game:
        """Create a new match"""
        try:
            if home_team_id == away_team_id:
                raise Exception("Home and away teams cannot be the same")

            match = Game(
                title=title or f"Team {home_team_id} vs Team {away_team_id}",
                description=description,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                match_date=match_date,
                location=location,
                created_by=created_by,
                tournament_id=tournament_id,
                status="scheduled"
            )
            self.db.add(match)
            self.db.commit()
            self.db.refresh(match)

            # Create match players
            if home_players:
                for player_data in home_players:
                    match_player = GamePlayer(
                        game_id=match.id,
                        user_id=player_data["user_id"],
                        team_id=home_team_id,
                        jersey_number=player_data.get("jersey_number"),
                        position=player_data.get("position"),
                        is_starter=player_data.get("is_starter", False)
                    )
                    self.db.add(match_player)
            
            if away_players:
                for player_data in away_players:
                    match_player = GamePlayer(
                        game_id=match.id,
                        user_id=player_data["user_id"],
                        team_id=away_team_id,
                        jersey_number=player_data.get("jersey_number"),
                        position=player_data.get("position"),
                        is_starter=player_data.get("is_starter", False)
                    )
                    self.db.add(match_player)
            
            self.db.commit()

            return match
        except Exception as e:
            self.db.rollback()
            raise

    def update_match(self, match_id: int, title: str = None, location: str = None, 
                     match_date: datetime = None, status: str = None) -> Game:
        """Update match information"""
        try:
            match = self.db.query(Game).filter(Game.id == match_id).first()
            if not match:
                raise Exception("Game not found")

            if title:
                match.title = title
            if location:
                match.location = location
            if match_date:
                match.match_date = match_date
            if status:
                match.status = status
            match.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(match)
            return match
        except Exception as e:
            self.db.rollback()
            raise

    def get_match(self, match_id: int) -> Optional[Game]:
        """Get match details"""
        return self.db.query(Game).filter(Game.id == match_id).first()

    def get_match_with_details(self, match_id: int) -> Optional[Dict]:
        """Get match with full details including teams and players"""
        game = self.db.query(Game).options(
            joinedload(Game.home_team),
            joinedload(Game.away_team),
            joinedload(Game.game_players).joinedload(GamePlayer.user),
            joinedload(Game.events)
        ).filter(Game.id == match_id).first()

        if not game:
            return None

        # Structure the response to match GameDetailsResponse schema
        home_players = []
        away_players = []

        for player in game.game_players:
            player_data = {
                "id": player.id,
                "game_id": player.game_id,
                "user_id": player.user_id,
                "team_id": player.team_id,
                "name": player.user.username if player.user else "Unknown Player",
                "jersey_number": player.jersey_number,
                "position": player.position,
                "is_starter": player.is_starter,
                "minutes_played": player.minutes_played,
                "created_at": player.created_at,
                "user": {
                    "id": player.user.id if player.user else None,
                    "username": player.user.username if player.user else "Unknown",
                    "first_name": player.user.first_name if player.user else "",
                    "last_name": player.user.last_name if player.user else ""
                } if player.user else None
            }

            if player.team_id == game.home_team_id:
                home_players.append(player_data)
            elif player.team_id == game.away_team_id:
                away_players.append(player_data)

        return {
            "id": game.id,
            "title": f"{game.home_team.name} vs {game.away_team.name}" if game.home_team and game.away_team else "Match",
            "home_team_id": game.home_team_id,
            "away_team_id": game.away_team_id,
            "created_by": game.created_by,
            "home_score": game.home_score,
            "away_score": game.away_score,
            "status": game.status,
            "match_date": game.match_date,
            "location": game.location,
            "home_team": {
                "id": game.home_team.id,
                "name": game.home_team.name,
                "description": game.home_team.description,
                "owner_id": game.home_team.owner_id,
                "city": game.home_team.city,
                "wins": 0,  # TODO: Calculate actual wins
                "losses": 0,  # TODO: Calculate actual losses
                "created_at": game.home_team.created_at
            } if game.home_team else None,
            "away_team": {
                "id": game.away_team.id,
                "name": game.away_team.name,
                "description": game.away_team.description,
                "owner_id": game.away_team.owner_id,
                "city": game.away_team.city,
                "wins": 0,  # TODO: Calculate actual wins
                "losses": 0,  # TODO: Calculate actual losses
                "created_at": game.away_team.created_at
            } if game.away_team else None,
            "home_players": home_players,
            "away_players": away_players,
            "events": [
                {
                    "id": event.id,
                    "game_id": event.game_id,
                    "user_id": event.user_id,
                    "team_id": event.team_id,
                    "event_type": event.event_type,
                    "period": event.period,
                    "timestamp": event.timestamp,
                    "outcome": event.outcome,
                    "created_at": event.created_at
                } for event in game.events
            ]
        }

    def start_match(self, match_id: int) -> Game:
        """Start a match (change status to in_progress)"""
        return self.update_match(match_id, status="in_progress")

    def end_match(self, match_id: int, home_score: int, away_score: int) -> Game:
        """End a match and set final score"""
        try:
            match = self.db.query(Game).filter(Game.id == match_id).first()
            if not match:
                raise Exception("Game not found")

            match.status = "completed"
            match.home_score = home_score
            match.away_score = away_score
            match.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(match)
            return match
        except Exception as e:
            self.db.rollback()
            raise

    def cancel_match(self, match_id: int) -> Game:
        """Cancel a match"""
        return self.update_match(match_id, status="cancelled")

    def get_team_matches(self, team_id: int, status: str = None, limit: int = 50, offset: int = 0) -> List[Game]:
        """Get matches for a team (home or away)"""
        query = self.db.query(Game).filter(
            or_(Game.home_team_id == team_id, Game.away_team_id == team_id)
        )

        if status:
            query = query.filter(Game.status == status)

        return query.order_by(desc(Game.match_date)).limit(limit).offset(offset).all()

    def get_matches(self, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get matches with optional status filtering"""
        query = self.db.query(Game)
        if status:
            query = query.filter(Game.status == status)
        games = query.order_by(desc(Game.created_at)).limit(limit).offset(offset).all()
        return [
            {
                "id": game.id,
                "title": game.title,
                "description": game.description,
                "home_team_id": game.home_team_id,
                "away_team_id": game.away_team_id,
                "home_score": game.home_score,
                "away_score": game.away_score,
                "status": game.status,
                "match_date": game.match_date.isoformat() if game.match_date else None,
                "location": game.location,
                "tournament_id": game.tournament_id,
                "created_by": game.created_by,
                "timeout_active": game.timeout_active,
                "timeout_started_at": game.timeout_started_at.isoformat() if game.timeout_started_at else None,
                "created_at": game.created_at.isoformat(),
                "updated_at": game.updated_at.isoformat(),
                "home_team": {
                    "id": game.home_team.id,
                    "name": game.home_team.name,
                    "city": game.home_team.city
                } if game.home_team else None,
                "away_team": {
                    "id": game.away_team.id,
                    "name": game.away_team.name,
                    "city": game.away_team.city
                } if game.away_team else None,
            }
            for game in games
        ]

    def get_upcoming_matches(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get upcoming scheduled matches"""
        games = self.db.query(Game).filter(
            Game.status.in_(["scheduled", "in_progress"])
        ).order_by(Game.match_date).limit(limit).offset(offset).all()
        return [
            {
                "id": game.id,
                "title": game.title,
                "description": game.description,
                "home_team_id": game.home_team_id,
                "away_team_id": game.away_team_id,
                "home_score": game.home_score,
                "away_score": game.away_score,
                "status": game.status,
                "match_date": game.match_date.isoformat(),
                "location": game.location,
                "tournament_id": game.tournament_id,
                "created_by": game.created_by,
                "timeout_active": game.timeout_active,
                "timeout_started_at": game.timeout_started_at.isoformat() if game.timeout_started_at else None,
                "created_at": game.created_at.isoformat(),
                "updated_at": game.updated_at.isoformat(),
            }
            for game in games
        ]

    def get_completed_matches(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get completed matches"""
        games = self.db.query(Game).filter(
            Game.status == "completed"
        ).order_by(desc(Game.match_date)).limit(limit).offset(offset).all()
        return [
            {
                "id": game.id,
                "title": game.title,
                "description": game.description,
                "home_team_id": game.home_team_id,
                "away_team_id": game.away_team_id,
                "home_score": game.home_score,
                "away_score": game.away_score,
                "status": game.status,
                "match_date": game.match_date.isoformat(),
                "location": game.location,
                "tournament_id": game.tournament_id,
                "created_by": game.created_by,
                "timeout_active": game.timeout_active,
                "timeout_started_at": game.timeout_started_at.isoformat() if game.timeout_started_at else None,
                "created_at": game.created_at.isoformat(),
                "updated_at": game.updated_at.isoformat(),
            }
            for game in games
        ]

    def get_matches_by_creator(self, creator_id: int) -> List[Dict]:
        """Get matches created by a specific user"""
        games = self.db.query(Game).filter(
            and_(Game.created_by == creator_id, Game.status != "completed")
        ).order_by(desc(Game.created_at)).all()
        return [
            {
                "id": game.id,
                "title": game.title,
                "description": game.description,
                "home_team_id": game.home_team_id,
                "away_team_id": game.away_team_id,
                "home_score": game.home_score,
                "away_score": game.away_score,
                "status": game.status,
                "match_date": game.match_date.isoformat() if game.match_date else None,
                "location": game.location,
                "tournament_id": game.tournament_id,
                "timeout_active": game.timeout_active,
                "timeout_started_at": game.timeout_started_at.isoformat() if game.timeout_started_at else None,
                "created_at": game.created_at.isoformat(),
                "updated_at": game.updated_at.isoformat(),
                "home_team": {
                    "id": game.home_team.id,
                    "name": game.home_team.name,
                    "city": game.home_team.city
                } if game.home_team else None,
                "away_team": {
                    "id": game.away_team.id,
                    "name": game.away_team.name,
                    "city": game.away_team.city
                } if game.away_team else None,
            }
            for game in games
        ]

    def update_match_score(self, match_id: int, home_score: int, away_score: int) -> Game:
        """Update match score"""
        try:
            match = self.db.query(Game).filter(Game.id == match_id).first()
            if not match:
                raise Exception("Game not found")

            match.home_score = home_score
            match.away_score = away_score
            match.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(match)
            return match
        except Exception as e:
            self.db.rollback()
            raise

    # ========================================================================
    # MATCH EVENTS & SCORING
    # ========================================================================

    def add_match_event(self, match_id: int, user_id: int, team_id: int, event_type: str, 
                       timestamp: int, period: int, outcome: str = None) -> GameEvent:
        """Record a match event (scoring, foul, etc.)
        
        Args:
            match_id: Game ID
            user_id: Player ID (optional for team events like timeout)
            team_id: Team ID
            event_type: Type of event (2PT, 3PT, FT, AST, REB, FLS, SUB, TO, etc.)
            timestamp: Timestamp in seconds
            period: Game period
            outcome: Outcome of the event (for shots: made/miss)
        """
        try:
            event = GameEvent(
                game_id=match_id,
                user_id=user_id,  # Can be None for team events
                team_id=team_id,
                event_type=event_type,
                period=period,
                timestamp=timestamp,
                outcome=outcome
            )
            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)
            return event
        except Exception as e:
            self.db.rollback()
            raise

    def get_match_events(self, match_id: int) -> List[GameEvent]:
        """Get all events from a match"""
        return self.db.query(GameEvent).filter(GameEvent.game_id == match_id).order_by(GameEvent.timestamp).all()

    def get_player_match_stats(self, match_id: int, player_id: int) -> Dict:
        """Get player statistics for a specific match"""
        events = self.db.query(GameEvent).filter(
            and_(GameEvent.game_id == match_id, GameEvent.player_id == player_id)
        ).all()

        stats = {
            "player_id": player_id,
            "total_points": 0,
            "field_goals": 0,
            "three_pointers": 0,
            "free_throws": 0,
            "fouls": 0,
            "rebounds": 0,
            "assists": 0,
            "steals": 0,
            "blocks": 0,
            "events": []
        }

        for event in events:
            if event.event_type == "basket":
                stats["field_goals"] += 1
                stats["total_points"] += event.points
            elif event.event_type == "three_pointer":
                stats["three_pointers"] += 1
                stats["total_points"] += 3
            elif event.event_type == "foul":
                stats["fouls"] += 1
            elif event.event_type == "rebound":
                stats["rebounds"] += 1
            elif event.event_type == "assist":
                stats["assists"] += 1
            elif event.event_type == "steal":
                stats["steals"] += 1
            elif event.event_type == "block":
                stats["blocks"] += 1

            stats["events"].append({
                "id": event.id,
                "type": event.event_type,
                "points": event.points,
                "timestamp": event.timestamp,
                "quarter": event.quarter
            })

        return stats

    # ========================================================================
    # TOURNAMENT MANAGEMENT
    # ========================================================================

    def create_tournament(self, organizer_id: int, title: str, format: str, start_date: datetime,
                         description: str = None, location: str = None, max_teams: int = None,
                         end_date: datetime = None, entry_fee: float = 0.0, prize_pool: float = 0.0,
                         rules: str = None) -> Tournament:
        """Create a new tournament"""
        try:
            tournament = Tournament(
                title=title,
                description=description,
                organizer_id=organizer_id,
                format=format,
                start_date=start_date,
                end_date=end_date,
                location=location,
                max_teams=max_teams,
                entry_fee=entry_fee,
                prize_pool=prize_pool,
                rules=rules,
                status="planning"
            )
            self.db.add(tournament)
            self.db.commit()
            self.db.refresh(tournament)
            return tournament
        except Exception as e:
            self.db.rollback()
            raise

    def get_tournament(self, tournament_id: int) -> Optional[Tournament]:
        """Get tournament details"""
        return self.db.query(Tournament).filter(Tournament.id == tournament_id).first()

    def get_tournaments(self, status: str = None, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get list of tournaments"""
        query = self.db.query(Tournament)
        
        if status:
            query = query.filter(Tournament.status == status)

        tournaments = query.order_by(desc(Tournament.start_date)).limit(limit).offset(offset).all()
        return [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "organizer_id": t.organizer_id,
                "status": t.status,
                "format": t.format,
                "start_date": t.start_date.isoformat() if t.start_date else None,
                "end_date": t.end_date.isoformat() if t.end_date else None,
                "location": t.location,
                "max_teams": t.max_teams,
                "entry_fee": t.entry_fee,
                "prize_pool": t.prize_pool,
                "rules": t.rules,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in tournaments
        ]

    def update_tournament(self, tournament_id: int, title: str = None, status: str = None,
                         description: str = None, end_date: datetime = None) -> Tournament:
        """Update tournament information"""
        try:
            tournament = self.db.query(Tournament).filter(Tournament.id == tournament_id).first()
            if not tournament:
                raise Exception("Tournament not found")

            if title:
                tournament.title = title
            if status:
                tournament.status = status
            if description is not None:
                tournament.description = description
            if end_date:
                tournament.end_date = end_date
            tournament.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(tournament)
            return tournament
        except Exception as e:
            self.db.rollback()
            raise

    def delete_tournament(self, tournament_id: int) -> bool:
        """Delete a tournament"""
        try:
            tournament = self.db.query(Tournament).filter(Tournament.id == tournament_id).first()
            if not tournament:
                raise Exception("Tournament not found")

            self.db.delete(tournament)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise

    def add_team_to_tournament(self, tournament_id: int, team_id: int, seed: int = None) -> TournamentTeam:
        """Add a team to a tournament"""
        try:
            # Check if already registered
            existing = self.db.query(TournamentTeam).filter(
                and_(TournamentTeam.tournament_id == tournament_id, TournamentTeam.team_id == team_id)
            ).first()
            if existing:
                raise Exception("Team already registered for tournament")

            # Check tournament team limit
            tournament = self.db.query(Tournament).filter(Tournament.id == tournament_id).first()
            if tournament.max_teams:
                team_count = self.db.query(TournamentTeam).filter(
                    TournamentTeam.tournament_id == tournament_id
                ).count()
                if team_count >= tournament.max_teams:
                    raise Exception("Tournament is full")

            tournament_team = TournamentTeam(
                tournament_id=tournament_id,
                team_id=team_id,
                seed=seed,
                status="registered"
            )
            self.db.add(tournament_team)
            self.db.commit()
            self.db.refresh(tournament_team)
            return tournament_team
        except Exception as e:
            self.db.rollback()
            raise

    def remove_team_from_tournament(self, tournament_id: int, team_id: int) -> bool:
        """Remove a team from a tournament"""
        try:
            tournament_team = self.db.query(TournamentTeam).filter(
                and_(TournamentTeam.tournament_id == tournament_id, TournamentTeam.team_id == team_id)
            ).first()
            if not tournament_team:
                raise Exception("Team not registered for tournament")

            self.db.delete(tournament_team)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise

    def get_tournament_teams(self, tournament_id: int) -> List[TournamentTeam]:
        """Get all teams in a tournament"""
        return self.db.query(TournamentTeam).filter(
            TournamentTeam.tournament_id == tournament_id
        ).all()

    def get_tournament_matches(self, tournament_id: int) -> List[Game]:
        """Get all matches in a tournament"""
        return self.db.query(Game).filter(Game.tournament_id == tournament_id).all()

    def generate_bracket(self, tournament_id: int) -> TournamentBracket:
        """Generate tournament bracket structure"""
        try:
            tournament = self.db.query(Tournament).filter(Tournament.id == tournament_id).first()
            if not tournament:
                raise Exception("Tournament not found")

            teams = self.get_tournament_teams(tournament_id)
            team_count = len(teams)

            # Calculate number of rounds
            rounds = 0
            temp = team_count
            while temp > 1:
                temp //= 2
                rounds += 1

            # Create bracket structure
            bracket_data = {
                "teams": [{"id": t.team_id, "name": t.team.name, "seed": t.seed} for t in teams],
                "rounds": rounds,
                "matches": []
            }

            bracket = TournamentBracket(
                tournament_id=tournament_id,
                bracket_data=json.dumps(bracket_data),
                current_round=1,
                total_rounds=rounds
            )
            self.db.add(bracket)
            self.db.commit()
            self.db.refresh(bracket)

            tournament.status = "in_progress"
            self.db.commit()

            return bracket
        except Exception as e:
            self.db.rollback()
            raise

    def get_bracket_structure(self, tournament_id: int) -> Optional[Dict]:
        """Get bracket structure"""
        bracket = self.db.query(TournamentBracket).filter(
            TournamentBracket.tournament_id == tournament_id
        ).first()

        if not bracket or not bracket.bracket_data:
            return None

        return json.loads(bracket.bracket_data)

    def advance_team_in_bracket(self, tournament_id: int, match_id: int, winner_team_id: int) -> bool:
        """Advance winning team in tournament bracket"""
        try:
            bracket = self.db.query(TournamentBracket).filter(
                TournamentBracket.tournament_id == tournament_id
            ).first()
            if not bracket:
                raise Exception("Bracket not found")

            match = self.db.query(Game).filter(Game.id == match_id).first()
            if not match:
                raise Exception("Game not found")

            # Update tournament team status
            tournament_team = self.db.query(TournamentTeam).filter(
                and_(TournamentTeam.tournament_id == tournament_id, TournamentTeam.team_id == winner_team_id)
            ).first()
            if tournament_team:
                tournament_team.wins += 1
                self.db.commit()

            return True
        except Exception as e:
            self.db.rollback()
            raise
    # ========================================================================
    # GAME FINALIZATION & STATS CALCULATION
    # ========================================================================

    def finalize_game(self, game_id: int) -> Dict:
        """
        Finalize a game and calculate player statistics
        Aggregates all game events and creates PlayerGameStats records
        """
        try:
            game = self.db.query(Game).filter(Game.id == game_id).first()
            if not game:
                raise Exception("Game not found")

            # Get all events for this game
            events = self.db.query(GameEvent).filter(GameEvent.game_id == game_id).all()

            # Dictionary to accumulate player stats
            player_stats = {}

            # Process each event
            for event in events:
                if not event.user_id:
                    continue  # Skip team events without a user_id (like timeouts)

                if event.user_id not in player_stats:
                    player_stats[event.user_id] = {
                        'points': 0,
                        'assists': 0,
                        'rebounds': 0,
                        'fouls': 0,
                        'violations': 0,
                        'shots_made': 0,
                        'shots_attempted': 0,
                        'two_pointers_made': 0,
                        'two_pointers_attempted': 0,
                        'three_pointers_made': 0,
                        'three_pointers_attempted': 0,
                        'free_throws_made': 0,
                        'free_throws_attempted': 0,
                    }

                stats = player_stats[event.user_id]

                # Process different event types
                if event.event_type == '2PT':
                    stats['shots_attempted'] += 1
                    stats['two_pointers_attempted'] += 1
                    if event.outcome == 'made':
                        stats['points'] += 2
                        stats['shots_made'] += 1
                        stats['two_pointers_made'] += 1

                elif event.event_type == '3PT':
                    stats['shots_attempted'] += 1
                    stats['three_pointers_attempted'] += 1
                    if event.outcome == 'made':
                        stats['points'] += 3
                        stats['shots_made'] += 1
                        stats['three_pointers_made'] += 1

                elif event.event_type == 'FT':  # Free Throw
                    stats['free_throws_attempted'] += 1
                    if event.outcome == 'made':
                        stats['points'] += 1
                        stats['free_throws_made'] += 1

                elif event.event_type == 'AST':  # Assist
                    stats['assists'] += 1

                elif event.event_type == 'REB':  # Rebound
                    stats['rebounds'] += 1

                elif event.event_type in ['FLS', 'FOUL_BLOCKING', 'FOUL_CHARGING', 'FOUL_HOLDING', 
                                          'FOUL_PUSHING', 'FOUL_HAND_CHECKING', 'FOUL_ILLEGAL_SCREEN', 
                                          'FOUL_ELBOWING', 'FOUL_SHOOTING']:  # Fouls
                    stats['fouls'] += 1

                elif event.event_type in ['VIOLATION_TRAVELING', 'VIOLATION_DOUBLE_DRIBBLE']:  # Violations
                    stats['violations'] += 1

            # Create PlayerGameStats records
            created_stats = []
            for player_id, stats in player_stats.items():
                # Check if stats for this player/game already exist
                existing_stats = self.db.query(PlayerGameStats).filter(
                    and_(
                        PlayerGameStats.player_id == player_id,
                        PlayerGameStats.game_id == game_id
                    )
                ).first()

                if existing_stats:
                    # Update existing record
                    for key, value in stats.items():
                        setattr(existing_stats, key, value)
                    existing_stats.updated_at = datetime.utcnow()
                    self.db.commit()
                    self.db.refresh(existing_stats)
                    created_stats.append(existing_stats)
                else:
                    # Create new record
                    player_game_stat = PlayerGameStats(
                        player_id=player_id,
                        game_id=game_id,
                        **stats
                    )
                    self.db.add(player_game_stat)
                    created_stats.append(player_game_stat)

            # Update game status to completed
            game.status = 'completed'
            game.ended_at = datetime.utcnow()
            self.db.commit()

            return {
                'game_id': game_id,
                'status': 'completed',
                'player_stats': created_stats,
                'total_players': len(created_stats)
            }

        except Exception as e:
            self.db.rollback()
            raise

    def get_player_stats(self, player_id: int) -> Dict:
        """
        Get aggregated career stats for a player
        """
        try:
            player = self.db.query(User).filter(User.id == player_id).first()
            if not player:
                raise Exception("Player not found")

            # Get all game stats for this player
            game_stats = self.db.query(PlayerGameStats).filter(
                PlayerGameStats.player_id == player_id
            ).all()

            if not game_stats:
                return {
                    'user_id': player_id,
                    'total_games': 0,
                    'total_points': 0,
                    'average_points_per_game': 0.0,
                    'total_assists': 0,
                    'total_rebounds': 0,
                    'total_fouls': 0,
                    'total_violations': 0,
                    'total_shots_made': 0,
                    'total_shots_attempted': 0,
                    'career_shooting_percentage': 0.0
                }

            # Aggregate stats
            total_points = sum(stat.points for stat in game_stats)
            total_assists = sum(stat.assists for stat in game_stats)
            total_rebounds = sum(stat.rebounds for stat in game_stats)
            total_fouls = sum(stat.fouls for stat in game_stats)
            total_violations = sum(stat.violations for stat in game_stats)
            total_shots_made = sum(stat.shots_made for stat in game_stats)
            total_shots_attempted = sum(stat.shots_attempted for stat in game_stats)
            
            total_games = len(game_stats)
            average_ppg = total_points / total_games if total_games > 0 else 0.0
            shooting_pct = (total_shots_made / total_shots_attempted * 100) if total_shots_attempted > 0 else 0.0

            return {
                'user_id': player_id,
                'total_games': total_games,
                'total_points': total_points,
                'average_points_per_game': round(average_ppg, 2),
                'total_assists': total_assists,
                'total_rebounds': total_rebounds,
                'total_fouls': total_fouls,
                'total_violations': total_violations,
                'total_shots_made': total_shots_made,
                'total_shots_attempted': total_shots_attempted,
                'career_shooting_percentage': round(shooting_pct, 2)
            }

        except Exception as e:
            self.db.rollback()
            raise

    def get_player_game_stats_list(self, player_id: int) -> List[PlayerGameStats]:
        """Get all game stats for a player"""
        return self.db.query(PlayerGameStats).filter(
            PlayerGameStats.player_id == player_id
        ).order_by(desc(PlayerGameStats.created_at)).all()

    def get_game_stats_summary(self, game_id: int) -> dict:
        """Get game statistics including top scorers and foul scorers"""
        game = self.get_match(game_id)
        if not game:
            return None
        
        try:
            # Get all game events for this game
            events = self.db.query(GameEvent).filter(
                GameEvent.game_id == game_id
            ).all()
            
            # Initialize stats dictionaries
            home_team_stats = {}
            away_team_stats = {}
            foul_stats = {}
            
            # Process events
            for event in events:
                # Track points
                if event.event_type in ['2PT', '3PT', 'FT'] and event.outcome == 'made':
                    points = 3 if event.event_type == '3PT' else 2 if event.event_type == '2PT' else 1
                    
                    if event.user_id:
                        if event.team_id == game.home_team_id:
                            if event.user_id not in home_team_stats:
                                home_team_stats[event.user_id] = {'points': 0, 'name': self._get_player_name(event.user_id)}
                            home_team_stats[event.user_id]['points'] += points
                        else:
                            if event.user_id not in away_team_stats:
                                away_team_stats[event.user_id] = {'points': 0, 'name': self._get_player_name(event.user_id)}
                            away_team_stats[event.user_id]['points'] += points
                
                # Track fouls
                if event.event_type.startswith('FOUL_'):
                    if event.user_id:
                        if event.user_id not in foul_stats:
                            foul_stats[event.user_id] = {'fouls': 0, 'name': self._get_player_name(event.user_id)}
                        foul_stats[event.user_id]['fouls'] += 1
            
            # Get top 2 scorers for each team
            home_scorers = sorted(home_team_stats.items(), key=lambda x: x[1]['points'], reverse=True)[:2]
            away_scorers = sorted(away_team_stats.items(), key=lambda x: x[1]['points'], reverse=True)[:2]
            top_foul_scorers = sorted(foul_stats.items(), key=lambda x: x[1]['fouls'], reverse=True)[:2]
            
            return {
                'game_id': game_id,
                'home_team_top_scorers': [
                    {
                        'user_id': user_id,
                        'name': stats['name'],
                        'points': stats['points']
                    }
                    for user_id, stats in home_scorers
                ],
                'away_team_top_scorers': [
                    {
                        'user_id': user_id,
                        'name': stats['name'],
                        'points': stats['points']
                    }
                    for user_id, stats in away_scorers
                ],
                'top_foul_scorers': [
                    {
                        'user_id': user_id,
                        'name': stats['name'],
                        'fouls': stats['fouls']
                    }
                    for user_id, stats in top_foul_scorers
                ]
            }
        
        except Exception as e:
            self.db.rollback()
            raise

    def _get_player_name(self, user_id: int) -> str:
        """Get player name from user"""
        from .models import User
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            if user.first_name and user.last_name:
                return f"{user.first_name} {user.last_name}"
            return user.username
        return "Unknown Player"