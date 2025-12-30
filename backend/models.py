"""
SQLAlchemy ORM Models for Scoring Basket
Maps to SQLite database tables
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime
import enum

Base = declarative_base()

# Constants
class HandStyle(enum.Enum):
    RIGHT_HAND = "right_hand"
    LEFT_HAND = "left_hand"

# Favorite basketball players constants
FAVORITE_PLAYERS = [
    "LeBron James", "Stephen Curry", "Kevin Durant", "Kobe Bryant", "Michael Jordan",
    "Shaquille O'Neal", "Magic Johnson", "Larry Bird", "Kareem Abdul-Jabbar", "Dirk Nowitzki",
    "Giannis Antetokounmpo", "Kawhi Leonard", "Russell Westbrook", "James Harden", "Luka Dončić",
    "Nikola Jokić", "Joel Embiid", "Damian Lillard", "Ja Morant", "Zion Williamson"
]


# ============================================================================
# AUTHENTICATION & USER MANAGEMENT MODELS (Phase 1)
# ============================================================================

class User(Base):
    """User model - represents an app user with authentication"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    stats = relationship("UserStats", back_populates="user", uselist=False, cascade="all, delete-orphan")
    players = relationship("Player", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class UserProfile(Base):
    """UserProfile model - extended user information"""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    city = Column(String(255), nullable=True)
    country = Column(String(255), nullable=True)
    mobile_number = Column(String(20), nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    preferred_position = Column(String(20), nullable=True)  # Point Guard, Shooting Guard, Small Forward, Power Forward, Center
    jersey_number = Column(Integer, nullable=True)
    hand_style = Column(Enum(HandStyle), nullable=True)
    favorite_player = Column(String(255), nullable=True)
    height_cm = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="profile")

    def __repr__(self):
        return f"<UserProfile(user_id={self.user_id})>"


class UserStats(Base):
    """UserStats model - aggregated player statistics"""
    __tablename__ = "user_stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    total_matches = Column(Integer, default=0, nullable=False)
    total_points = Column(Integer, default=0, nullable=False)
    total_assists = Column(Integer, default=0, nullable=False)
    total_rebounds = Column(Integer, default=0, nullable=False)
    matches_won = Column(Integer, default=0, nullable=False)
    matches_lost = Column(Integer, default=0, nullable=False)
    win_rate = Column(Float, default=0.0, nullable=False)
    points_per_game = Column(Float, default=0.0, nullable=False)
    assists_per_game = Column(Float, default=0.0, nullable=False)
    rebounds_per_game = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="stats")

    def __repr__(self):
        return f"<UserStats(user_id={self.user_id}, total_matches={self.total_matches})>"


# ============================================================================
# SPORTS & GAME MODELS
# ============================================================================


class Team(Base):
    """Team model - represents a basketball team"""
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    description = Column(Text, nullable=True)
    logo_url = Column(String(500), nullable=True)
    city = Column(String(255), nullable=True)
    country = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    players = relationship("Player", back_populates="team", cascade="all, delete-orphan")
    home_games = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    away_games = relationship("Game", foreign_keys="Game.away_team_id", back_populates="away_team")
    events = relationship("GameEvent", back_populates="team", cascade="all, delete-orphan")
    tournament_teams = relationship("TournamentTeam", back_populates="team", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Team(id={self.id}, name='{self.name}')>"


class TeamMember(Base):
    """TeamMember model - represents team membership and roles"""
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), default="member", nullable=False)  # member, captain, vice_captain, admin
    is_admin = Column(Boolean, default=False, nullable=False)
    is_captain = Column(Boolean, default=False, nullable=False)
    is_vice_captain = Column(Boolean, default=False, nullable=False)
    status = Column(String(20), default="active", nullable=False)  # active, inactive, pending
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    invited_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    team = relationship("Team", backref="members")
    user = relationship("User", foreign_keys=[user_id], backref="team_memberships")
    inviter = relationship("User", foreign_keys=[invited_by])

    def __repr__(self):
        return f"<TeamMember(team_id={self.team_id}, user_id={self.user_id}, role='{self.role}')>"


class TeamLeadershipHistory(Base):
    """TeamLeadershipHistory model - tracks captain and vice captain role changes"""
    __tablename__ = "team_leadership_history"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'captain' or 'vice_captain'
    action = Column(String(20), nullable=False)  # 'assigned' or 'removed'
    assigned_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, nullable=True)  # Optional notes about the change

    # Relationships
    team = relationship("Team", backref="leadership_history")
    user = relationship("User", foreign_keys=[user_id], backref="leadership_history")
    assigner = relationship("User", foreign_keys=[assigned_by])

    def __repr__(self):
        return f"<TeamLeadershipHistory(team_id={self.team_id}, user_id={self.user_id}, role='{self.role}', action='{self.action}')>"


class Player(Base):
    """Player model - represents a basketball player"""
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    number = Column(Integer, nullable=True)
    position = Column(String(10), nullable=False)  # PG, SG, SF, PF, C
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="players")
    team = relationship("Team", back_populates="players")

    def __repr__(self):
        return f"<Player(id={self.id}, name='{self.name}', number={self.number})>"


class Game(Base):
    """Game model - represents a basketball game"""
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    home_team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    away_team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    home_score = Column(Integer, default=0, nullable=False)
    away_score = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default="scheduled", nullable=False, index=True)  # scheduled, in_progress, completed, cancelled
    match_date = Column(DateTime, nullable=True)
    location = Column(String(255), nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    timeout_active = Column(Boolean, default=False, nullable=False)  # True when timeout in effect
    timeout_started_at = Column(DateTime, nullable=True)  # When timeout was initiated
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_games")
    tournament = relationship("Tournament", back_populates="matches")
    creator = relationship("User", foreign_keys=[created_by])
    events = relationship("GameEvent", back_populates="game", cascade="all, delete-orphan")
    game_players = relationship("GamePlayer", back_populates="game", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Game(id={self.id}, status='{self.status}')>"


class GameEvent(Base):
    """GameEvent model - represents a scoring event in a game"""
    __tablename__ = "game_events"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(30), nullable=False)  # 2PT, 3PT, FT, AST, REB, FLS, SUB, TO, PERIOD_START, PERIOD_END, FOUL_*, VIOLATION_*
    period = Column(Integer, nullable=False)
    timestamp = Column(Integer, nullable=True)  # seconds elapsed in period
    outcome = Column(String(20), nullable=True)  # made, miss (for shots only)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    game = relationship("Game", back_populates="events")
    user = relationship("User", backref="game_events")
    team = relationship("Team", back_populates="events")

    def __repr__(self):
        return f"<GameEvent(id={self.id}, game_id={self.game_id}, event_type='{self.event_type}')>"


class GamePlayer(Base):
    """GamePlayer model - associates players with games and their teams"""
    __tablename__ = "game_players"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    jersey_number = Column(Integer, nullable=True)
    position = Column(String(50), nullable=True)  # PG, SG, SF, PF, C
    is_starter = Column(Boolean, default=False, nullable=False)
    minutes_played = Column(Integer, default=0, nullable=False)  # in seconds
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    game = relationship("Game", back_populates="game_players")
    user = relationship("User", backref="game_players")
    team = relationship("Team", backref="game_players")

    @hybrid_property
    def name(self):
        """Get the player's display name"""
        if self.user:
            if self.user.first_name and self.user.last_name:
                return f"{self.user.first_name} {self.user.last_name}"
            return self.user.username
        return "Unknown Player"

    def __repr__(self):
        return f"<GamePlayer(game_id={self.game_id}, user_id={self.user_id}, team_id={self.team_id})>"


# ============================================================================
# MATCH & TOURNAMENT MODELS (Phase 3)
# ============================================================================


class Tournament(Base):
    """Tournament model - represents a basketball tournament"""
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    organizer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="planning", nullable=False, index=True)  # planning, registration, in_progress, completed
    format = Column(String(50), default="single_elimination", nullable=False)  # single_elimination, double_elimination, round_robin
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=True)
    location = Column(String(255), nullable=True)
    max_teams = Column(Integer, nullable=True)
    entry_fee = Column(Float, default=0.0)
    prize_pool = Column(Float, default=0.0)
    rules = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    organizer = relationship("User", foreign_keys=[organizer_id], backref="organized_tournaments")
    tournament_teams = relationship("TournamentTeam", back_populates="tournament", cascade="all, delete-orphan")
    matches = relationship("Game", back_populates="tournament", cascade="all, delete-orphan")
    bracket = relationship("TournamentBracket", back_populates="tournament", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tournament(id={self.id}, title='{self.title}', status='{self.status}')>"


class TournamentTeam(Base):
    """TournamentTeam model - represents teams participating in a tournament"""
    __tablename__ = "tournament_teams"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    registered_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(50), default="registered", nullable=False)  # registered, qualified, eliminated, champion
    seed = Column(Integer, nullable=True)  # For bracket seeding
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)

    # Relationships
    tournament = relationship("Tournament", back_populates="tournament_teams")
    team = relationship("Team", back_populates="tournament_teams")

    def __repr__(self):
        return f"<TournamentTeam(tournament_id={self.tournament_id}, team_id={self.team_id})>"


class TournamentBracket(Base):
    """TournamentBracket model - stores tournament bracket structure"""
    __tablename__ = "tournament_brackets"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    bracket_data = Column(Text, nullable=True)  # JSON structure of bracket
    current_round = Column(Integer, default=1, nullable=False)
    total_rounds = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tournament = relationship("Tournament", back_populates="bracket")

    def __repr__(self):
        return f"<TournamentBracket(tournament_id={self.tournament_id}, current_round={self.current_round})>"


# ============================================================================
# PLAYER GAME STATISTICS MODEL
# ============================================================================

class PlayerGameStats(Base):
    """PlayerGameStats model - stores stats for a player in a specific game"""
    __tablename__ = "player_game_stats"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    points = Column(Integer, default=0, nullable=False)  # Total points
    assists = Column(Integer, default=0, nullable=False)
    rebounds = Column(Integer, default=0, nullable=False)
    fouls = Column(Integer, default=0, nullable=False)
    violations = Column(Integer, default=0, nullable=False)
    shots_made = Column(Integer, default=0, nullable=False)  # 2PT + 3PT made
    shots_attempted = Column(Integer, default=0, nullable=False)  # 2PT + 3PT attempted
    two_pointers_made = Column(Integer, default=0, nullable=False)
    two_pointers_attempted = Column(Integer, default=0, nullable=False)
    three_pointers_made = Column(Integer, default=0, nullable=False)
    three_pointers_attempted = Column(Integer, default=0, nullable=False)
    free_throws_made = Column(Integer, default=0, nullable=False)
    free_throws_attempted = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    player = relationship("User", foreign_keys=[player_id])
    game = relationship("Game", foreign_keys=[game_id])

    def __repr__(self):
        return f"<PlayerGameStats(player_id={self.player_id}, game_id={self.game_id}, points={self.points})>"


# ============================================================================
# ANALYTICS & STATISTICS MODELS (Phase 5) - Moved to models_analytics.py
# ============================================================================
# These models are now defined in models_analytics.py to avoid duplication

