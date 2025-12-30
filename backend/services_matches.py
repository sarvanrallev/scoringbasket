"""
Match and Tournament Service Layer
Handles all business logic for matches, teams, and tournaments
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, and_, or_
from datetime import datetime
from typing import List, Optional, Dict
import json

from .models import (
    Team, Player, Match, MatchEvent, MatchStatistics, MatchPlayer,
    Tournament, TournamentTeam, TournamentBracket, User,
    TeamMember, TeamLeadershipHistory
)


class MatchService:
    """Service for managing matches, teams, and tournaments"""

    def __init__(self, db: Session):
        self.db = db

    # ========================================================================
    # TEAM MANAGEMENT
    # ========================================================================

    def create_team(self, owner_id: int, name: str, description: str = None, city: str = None) -> Team:
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
            return team
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
        team = self.db.query(Team).filter(Team.id == team_id).first()
        if not team:
            return None
            
        # Calculate wins and losses from completed matches
        home_matches = self.db.query(Match).filter(
            Match.home_team_id == team_id,
            Match.status == "completed"
        ).all()
        
        away_matches = self.db.query(Match).filter(
            Match.away_team_id == team_id,
            Match.status == "completed"
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
        
        return {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "owner_id": team.owner_id,
            "city": team.city,
            "wins": wins,
            "losses": losses,
            "created_at": team.created_at
        }

    def get_user_teams(self, user_id: int) -> List[Dict]:
        """Get all teams owned by a user with stats"""
        teams = self.db.query(Team).filter(Team.owner_id == user_id).all()
        return [
            {
                "id": team.id,
                "name": team.name,
                "description": team.description,
                "owner_id": team.owner_id,
                "city": team.city,
                "country": team.country,
                "created_at": team.created_at,
                "updated_at": team.updated_at,
                "wins": 0,  # TODO: Calculate from match results
                "losses": 0  # TODO: Calculate from match results
            }
            for team in teams
        ]

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
                     home_players: List[Dict] = None, away_players: List[Dict] = None) -> Match:
        """Create a new match"""
        try:
            if home_team_id == away_team_id:
                raise Exception("Home and away teams cannot be the same")

            match = Match(
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

            # Create associated statistics record
            stats = MatchStatistics(match_id=match.id)
            self.db.add(stats)
            self.db.commit()

            # Create match players
            if home_players:
                for player_data in home_players:
                    match_player = MatchPlayer(
                        match_id=match.id,
                        user_id=player_data["user_id"],
                        team_id=home_team_id,
                        jersey_number=player_data.get("jersey_number"),
                        position=player_data.get("position"),
                        is_starter=player_data.get("is_starter", False)
                    )
                    self.db.add(match_player)
            
            if away_players:
                for player_data in away_players:
                    match_player = MatchPlayer(
                        match_id=match.id,
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
                     match_date: datetime = None, status: str = None) -> Match:
        """Update match information"""
        try:
            match = self.db.query(Match).filter(Match.id == match_id).first()
            if not match:
                raise Exception("Match not found")

            if title:
                match.title = title
            if location:
                match.location = location
            if match_date:
                match.match_date = match_date
            if status:
                match.status = status
                if status == 'in_progress' and not match.started_at:
                    match.started_at = datetime.utcnow()
                elif status == 'completed' and not match.ended_at:
                    match.ended_at = datetime.utcnow()
            match.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(match)
            return match
        except Exception as e:
            self.db.rollback()
            raise

    def get_match(self, match_id: int) -> Optional[Match]:
        """Get match details"""
        return self.db.query(Match).filter(Match.id == match_id).first()

    def get_match_with_details(self, match_id: int) -> Optional[Match]:
        """Get match with full details including teams and players"""
        return self.db.query(Match).options(
            joinedload(Match.home_team),
            joinedload(Match.away_team),
            joinedload(Match.match_players).joinedload(MatchPlayer.user),
            joinedload(Match.events),
            joinedload(Match.statistics)
        ).filter(Match.id == match_id).first()

    def start_match(self, match_id: int) -> Match:
        """Start a match (change status to in_progress)"""
        return self.update_match(match_id, status="in_progress")

    def end_match(self, match_id: int, home_score: int, away_score: int) -> Match:
        """End a match and set final score"""
        try:
            match = self.db.query(Match).filter(Match.id == match_id).first()
            if not match:
                raise Exception("Match not found")

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

    def cancel_match(self, match_id: int) -> Match:
        """Cancel a match"""
        return self.update_match(match_id, status="cancelled")

    def get_team_matches(self, team_id: int, status: str = None, limit: int = 50, offset: int = 0) -> List[Match]:
        """Get matches for a team (home or away)"""
        query = self.db.query(Match).filter(
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id)
        )

        if status:
            query = query.filter(Match.status == status)

        return query.order_by(desc(Match.match_date)).limit(limit).offset(offset).all()

    def get_matches(self, status: str = None, limit: int = 50, offset: int = 0) -> List[Match]:
        """Get matches with optional status filtering"""
        query = self.db.query(Match)
        if status:
            query = query.filter(Match.status == status)
        return query.order_by(desc(Match.created_at)).limit(limit).offset(offset).all()

    def get_upcoming_matches(self, limit: int = 50, offset: int = 0) -> List[Match]:
        """Get upcoming scheduled matches"""
        return self.db.query(Match).filter(
            Match.status.in_(["scheduled", "in_progress"])
        ).order_by(Match.match_date).limit(limit).offset(offset).all()

    def get_completed_matches(self, limit: int = 50, offset: int = 0) -> List[Match]:
        """Get completed matches"""
        return self.db.query(Match).filter(
            Match.status == "completed"
        ).order_by(desc(Match.match_date)).limit(limit).offset(offset).all()

    def get_matches_by_creator(self, creator_id: int) -> List[Match]:
        """Get matches created by a specific user"""
        return self.db.query(Match).filter(
            and_(Match.created_by == creator_id, Match.status != "completed")
        ).order_by(desc(Match.created_at)).all()

    def update_match_score(self, match_id: int, home_score: int, away_score: int) -> Match:
        """Update match score"""
        try:
            match = self.db.query(Match).filter(Match.id == match_id).first()
            if not match:
                raise Exception("Match not found")

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

    def add_match_event(self, match_id: int, player_id: int, team_id: int, event_type: str, 
                       points: int, timestamp: int, quarter: int) -> MatchEvent:
        """Record a match event (scoring, foul, etc.)"""
        try:
            event = MatchEvent(
                match_id=match_id,
                player_id=player_id,
                team_id=team_id,
                event_type=event_type,
                points=points,
                timestamp=timestamp,
                quarter=quarter
            )
            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)
            return event
        except Exception as e:
            self.db.rollback()
            raise

    def get_match_events(self, match_id: int) -> List[MatchEvent]:
        """Get all events from a match"""
        return self.db.query(MatchEvent).filter(MatchEvent.match_id == match_id).order_by(MatchEvent.timestamp).all()

    def get_player_match_stats(self, match_id: int, player_id: int) -> Dict:
        """Get player statistics for a specific match"""
        events = self.db.query(MatchEvent).filter(
            and_(MatchEvent.match_id == match_id, MatchEvent.player_id == player_id)
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

    def get_match_statistics(self, match_id: int) -> Optional[MatchStatistics]:
        """Get match statistics"""
        return self.db.query(MatchStatistics).filter(MatchStatistics.match_id == match_id).first()

    def update_match_statistics(self, match_id: int, team_id: int, stat_key: str, value: int) -> MatchStatistics:
        """Update match statistics for a team"""
        try:
            stats = self.db.query(MatchStatistics).filter(MatchStatistics.match_id == match_id).first()
            if not stats:
                raise Exception("Statistics not found")

            match = self.db.query(Match).filter(Match.id == match_id).first()
            if not match:
                raise Exception("Match not found")

            # Determine team prefix (home or away)
            prefix = "home_" if team_id == match.home_team_id else "away_"
            column = f"{prefix}{stat_key}"

            if hasattr(stats, column):
                setattr(stats, column, value)
                stats.updated_at = datetime.utcnow()
                self.db.commit()
                self.db.refresh(stats)
                return stats
            else:
                raise Exception(f"Invalid statistic key: {stat_key}")
        except Exception as e:
            self.db.rollback()
            raise

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

    def get_tournaments(self, status: str = None, limit: int = 50, offset: int = 0) -> List[Tournament]:
        """Get list of tournaments"""
        query = self.db.query(Tournament)
        
        if status:
            query = query.filter(Tournament.status == status)

        return query.order_by(desc(Tournament.start_date)).limit(limit).offset(offset).all()

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

    def get_tournament_matches(self, tournament_id: int) -> List[Match]:
        """Get all matches in a tournament"""
        return self.db.query(Match).filter(Match.tournament_id == tournament_id).all()

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

            match = self.db.query(Match).filter(Match.id == match_id).first()
            if not match:
                raise Exception("Match not found")

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
