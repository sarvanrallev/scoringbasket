"""
Game and Tournament API routes
Handles: teams, games, events, tournaments, brackets
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from .database import get_db_session
from .models import User, Team, TeamMember, TeamLeadershipHistory, Game, Tournament
from .routes_auth import get_current_user
from .services_games import GameService
from .schemas_games import (
    TeamCreate, TeamUpdate, TeamResponse, TeamDetailsResponse, PlayerResponse,
    TeamMemberInvite, TeamMemberUpdateRole, TeamMemberResponse, TeamLeadershipHistoryResponse, TeamWithMembersResponse,
    GameCreate, GameUpdate, GameResponse, GameEventCreate, GameEventResponse,
    GameDetailsResponse, PlayerStatsResponse, PlayerGameStatsResponse, UserStatsResponse, FinalizeGameResponse,
    PlayerStatsSummaryResponse, TournamentCreate, TournamentUpdate, TournamentResponse, BracketResponse
)

router = APIRouter(prefix="/api/games", tags=["games"])


# ============================================================================
# TEAM ENDPOINTS
# ============================================================================

@router.post("/teams", response_model=TeamResponse)
def create_team(
    team_data: TeamCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Create a new team"""
    try:
        service = GameService(db)
        team = service.create_team(
            owner_id=current_user.id,
            name=team_data.name,
            description=team_data.description,
            city=team_data.city
        )
        
        # Create team membership for the creator as admin
        team_member = TeamMember(
            team_id=team["id"],
            user_id=current_user.id,
            role="admin",
            is_admin=True,
            status="active"
        )
        
        db.add(team_member)
        db.commit()
        
        return team
    except Exception as e:
        # Rollback any pending changes
        db.rollback()
        error_msg = str(e)
        if "already exists" in error_msg:
            raise HTTPException(status_code=400, detail=error_msg)
        else:
            raise HTTPException(status_code=500, detail=f"Failed to create team: {error_msg}")


@router.put("/teams/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: int,
    team_data: TeamUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Update team information"""
    service = GameService(db)
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    owner_id = team['owner_id'] if isinstance(team, dict) else team.owner_id
    if owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not team owner")
    
    team = service.update_team(
        team_id=team_id,
        name=team_data.name,
        description=team_data.description,
        city=team_data.city
    )
    return service.get_team(team_id)


@router.delete("/teams/{team_id}")
def delete_team(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Delete a team"""
    service = GameService(db)
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    owner_id = team['owner_id'] if isinstance(team, dict) else team.owner_id
    if owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not team owner")
    
    service.delete_team(team_id)
    return {"message": "Team deleted successfully"}


@router.get("/teams")
def get_teams(
    db: Session = Depends(get_db_session)
):
    """Get all teams in the system"""
    from .models import Player, TeamMember
    
    # Get all teams regardless of user membership
    teams = db.query(Team).all()
    
    teams_list = []
    for team in teams:
        # Get captain info
        captain_member = db.query(TeamMember).filter(
            TeamMember.team_id == team.id,
            TeamMember.is_captain == True,
            TeamMember.status == "active"
        ).first()
        
        captain = None
        if captain_member:
            captain_user = db.query(User).filter(User.id == captain_member.user_id).first()
            if captain_user:
                captain = {
                    "id": captain_user.id,
                    "name": f"{captain_user.first_name} {captain_user.last_name}".strip() or captain_user.username
                }
        
        # Count players
        player_count = db.query(Player).filter(Player.team_id == team.id).count()
        
        teams_list.append({
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "owner_id": team.owner_id,
            "city": team.city,
            "wins": 0,  # TODO: Calculate from match results
            "losses": 0,  # TODO: Calculate from match results
            "created_at": team.created_at.isoformat(),
            "is_admin": False,
            "captain": captain,
            "player_count": player_count
        })
    
    return teams_list


@router.get("/teams/{team_id}", response_model=TeamResponse)
def get_team(
    team_id: int,
    db: Session = Depends(get_db_session)
):
    """Get team details"""
    service = GameService(db)
    team = service.get_team(team_id)
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return team


@router.get("/my-teams", response_model=List[TeamResponse])
def get_my_teams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get teams where current user is owner or member"""
    from .models import TeamMember, Player
    
    service = GameService(db)
    
    # Get teams where user is owner (automatically admin)
    owned_teams = service.get_user_teams(current_user.id)
    # Add is_admin flag to owned teams
    for team in owned_teams:
        team["is_admin"] = True
    
    # Get teams where user is a member (but not owner)
    member_teams = db.query(Team).join(TeamMember).filter(
        TeamMember.user_id == current_user.id,
        TeamMember.status == "active",
        Team.owner_id != current_user.id  # Exclude teams they own
    ).all()
    
    # Convert member teams to dict format with stats and admin status
    member_teams_dict = []
    for team in member_teams:
        # Check if user is admin in this team
        membership = db.query(TeamMember).filter(
            TeamMember.team_id == team.id,
            TeamMember.user_id == current_user.id
        ).first()
        is_admin = membership.is_admin if membership else False
        
        # Get captain info
        captain_member = db.query(TeamMember).filter(
            TeamMember.team_id == team.id,
            TeamMember.is_captain == True,
            TeamMember.status == "active"
        ).first()
        
        captain = None
        if captain_member:
            captain_user = db.query(User).filter(User.id == captain_member.user_id).first()
            if captain_user:
                captain = {
                    "id": captain_user.id,
                    "name": f"{captain_user.first_name} {captain_user.last_name}".strip() or captain_user.username
                }
        
        # Count players
        player_count = db.query(Player).filter(Player.team_id == team.id).count()
        
        member_teams_dict.append({
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "owner_id": team.owner_id,
            "city": team.city,
            "wins": 0,  # TODO: Calculate from match results
            "losses": 0,  # TODO: Calculate from match results
            "created_at": team.created_at.isoformat(),
            "is_admin": is_admin,
            "captain": captain,
            "player_count": player_count
        })
    
    # Combine and return
    all_teams = owned_teams + member_teams_dict
    return all_teams


@router.post("/teams/{team_id}/players", response_model=PlayerResponse)
def add_player_to_team(
    team_id: int,
    player_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Add a player to a team"""
    service = GameService(db)
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    owner_id = team['owner_id'] if isinstance(team, dict) else team.owner_id
    if owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not team owner")
    
    player = service.add_player_to_team(
        team_id=team_id,
        user_id=player_data["user_id"],
        jersey_number=player_data.get("jersey_number"),
        position=player_data.get("position")
    )
    return player


@router.delete("/teams/{team_id}/players/{user_id}")
def remove_player_from_team(
    team_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Remove a player from a team"""
    service = GameService(db)
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    owner_id = team['owner_id'] if isinstance(team, dict) else team.owner_id
    if owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not team owner")
    
    service.remove_player_from_team(team_id, user_id)
    return {"message": "Player removed from team"}


@router.get("/teams/{team_id}/players", response_model=List[PlayerResponse])
def get_team_players(
    team_id: int,
    db: Session = Depends(get_db_session)
):
    """Get all players on a team"""
    service = GameService(db)
    team = service.get_team(team_id)
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    players = service.get_team_players(team_id)
    return players


# ============================================================================
# TEAM MEMBERSHIP ENDPOINTS
# ============================================================================

@router.post("/teams/{team_id}/members/invite", response_model=TeamMemberResponse)
def invite_team_member(
    team_id: int,
    invite_data: TeamMemberInvite,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Invite a user to join a team by phone number"""
    service = GameService(db)
    
    # Check if team exists
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Check if current user is team admin
    member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id,
        TeamMember.is_admin == True,
        TeamMember.status == "active"
    ).first()
    
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized to invite members")
    
    # Find user by phone number
    user = db.query(User).filter(User.phone == invite_data.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User with this phone number not found")
    
    # Check if user is already a member
    existing_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user.id
    ).first()
    
    if existing_member:
        raise HTTPException(status_code=400, detail="User is already a team member")
    
    # Create team membership
    team_member = TeamMember(
        team_id=team_id,
        user_id=user.id,
        role="member",
        status="active",
        invited_by=current_user.id
    )
    
    db.add(team_member)
    db.commit()
    db.refresh(team_member)
    
    return {
        "id": team_member.id,
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_admin": team_member.is_admin,
        "is_captain": team_member.is_captain,
        "is_vice_captain": team_member.is_vice_captain,
        "status": team_member.status,
        "joined_at": team_member.joined_at
    }


@router.post("/teams/{team_id}/members/add", response_model=TeamMemberResponse)
def add_team_member_direct(
    team_id: int,
    member_data: dict,  # {"user_id": int, "role": str}
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Add a user directly to a team (admin only)"""
    service = GameService(db)
    
    # Check if current user is team admin
    admin_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id,
        TeamMember.is_admin == True,
        TeamMember.status == "active"
    ).first()
    
    if not admin_member:
        raise HTTPException(status_code=403, detail="Not authorized to add members")
    
    user_id = member_data.get("user_id")
    role = member_data.get("role", "member")
    
    # Convert role to boolean flags
    is_admin = role == "admin"
    is_captain = role == "captain"
    is_vice_captain = role == "vice_captain"
    
    # Determine role based on boolean flags
    role = "member"
    if is_admin:
        role = "admin"
    elif is_captain:
        role = "captain"
    elif is_vice_captain:
        role = "vice_captain"
    
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is already a member
    existing_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id
    ).first()
    
    if existing_member:
        raise HTTPException(status_code=400, detail="User is already a team member")
    
    # Create team membership
    team_member = TeamMember(
        team_id=team_id,
        user_id=user_id,
        role=role,
        is_admin=is_admin,
        is_captain=is_captain,
        is_vice_captain=is_vice_captain,
        status="active",
        invited_by=current_user.id
    )
    
    db.add(team_member)
    db.commit()
    db.refresh(team_member)
    
    return {
        "id": team_member.id,
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_admin": team_member.is_admin,
        "is_captain": team_member.is_captain,
        "is_vice_captain": team_member.is_vice_captain,
        "status": team_member.status,
        "joined_at": team_member.joined_at
    }


@router.put("/teams/{team_id}/members/{member_id}/role", response_model=TeamMemberResponse)
def update_team_member_role(
    team_id: int,
    member_id: int,
    role_data: TeamMemberUpdateRole,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Update a team member's role (admin only)"""
    service = GameService(db)
    
    # Check if current user is team admin
    admin_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id,
        TeamMember.is_admin == True,
        TeamMember.status == "active"
    ).first()
    
    if not admin_member:
        raise HTTPException(status_code=403, detail="Not authorized to manage member roles")
    
    # Get the member to update
    member = db.query(TeamMember).filter(
        TeamMember.id == member_id,
        TeamMember.team_id == team_id
    ).first()
    
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    # Track role changes for history
    role_changes = []
    
    # Handle captain role - only one captain allowed
    if role_data.is_captain is not None and role_data.is_captain != member.is_captain:
        if role_data.is_captain:
            # Assigning captain - remove captain role from any existing captain
            existing_captain = db.query(TeamMember).filter(
                TeamMember.team_id == team_id,
                TeamMember.is_captain == True,
                TeamMember.status == "active"
            ).first()
            
            if existing_captain and existing_captain.id != member.id:
                existing_captain.is_captain = False
                role_changes.append({
                    'member': existing_captain,
                    'role': 'captain',
                    'action': 'removed',
                    'reason': 'New captain assigned'
                })
            
            role_changes.append({
                'member': member,
                'role': 'captain',
                'action': 'assigned',
                'reason': 'Assigned as captain'
            })
        else:
            # Removing captain role
            role_changes.append({
                'member': member,
                'role': 'captain',
                'action': 'removed',
                'reason': 'Captain role removed'
            })
        
        member.is_captain = role_data.is_captain
    
    # Handle vice captain role - only one vice captain allowed
    if role_data.is_vice_captain is not None and role_data.is_vice_captain != member.is_vice_captain:
        if role_data.is_vice_captain:
            # Assigning vice captain - remove vice captain role from any existing vice captain
            existing_vice_captain = db.query(TeamMember).filter(
                TeamMember.team_id == team_id,
                TeamMember.is_vice_captain == True,
                TeamMember.status == "active"
            ).first()
            
            if existing_vice_captain and existing_vice_captain.id != member.id:
                existing_vice_captain.is_vice_captain = False
                role_changes.append({
                    'member': existing_vice_captain,
                    'role': 'vice_captain',
                    'action': 'removed',
                    'reason': 'New vice captain assigned'
                })
            
            role_changes.append({
                'member': member,
                'role': 'vice_captain',
                'action': 'assigned',
                'reason': 'Assigned as vice captain'
            })
        else:
            # Removing vice captain role
            role_changes.append({
                'member': member,
                'role': 'vice_captain',
                'action': 'removed',
                'reason': 'Vice captain role removed'
            })
        
        member.is_vice_captain = role_data.is_vice_captain
    
    # Handle admin role (no constraints for admin)
    if role_data.is_admin is not None:
        member.is_admin = role_data.is_admin
    
    # Record history for all role changes
    for change in role_changes:
        history_entry = TeamLeadershipHistory(
            team_id=team_id,
            user_id=change['member'].user_id,
            role=change['role'],
            action=change['action'],
            assigned_by=current_user.id,
            notes=change['reason']
        )
        db.add(history_entry)
    
    db.commit()
    db.refresh(member)
    
    # Get user details
    user = db.query(User).filter(User.id == member.user_id).first()
    
    return {
        "id": member.id,
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_admin": member.is_admin,
        "is_captain": member.is_captain,
        "is_vice_captain": member.is_vice_captain,
        "status": member.status,
        "joined_at": member.joined_at
    }


@router.get("/teams/{team_id}/leadership-history", response_model=List[TeamLeadershipHistoryResponse])
def get_team_leadership_history(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get team leadership history (team members only)"""
    
    # Check if current user is a team member
    team_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id,
        TeamMember.status == "active"
    ).first()
    
    if not team_member:
        raise HTTPException(status_code=403, detail="Not authorized to view team leadership history")
    
    # Get leadership history with user details
    history_entries = db.query(TeamLeadershipHistory).filter(
        TeamLeadershipHistory.team_id == team_id
    ).order_by(TeamLeadershipHistory.assigned_at.desc()).all()
    
    # Build response with user details
    response = []
    for entry in history_entries:
        user = db.query(User).filter(User.id == entry.user_id).first()
        assigner = db.query(User).filter(User.id == entry.assigned_by).first() if entry.assigned_by else None
        
        response.append({
            "id": entry.id,
            "team_id": entry.team_id,
            "user_id": entry.user_id,
            "username": user.username if user else "Unknown",
            "first_name": user.first_name if user else None,
            "last_name": user.last_name if user else None,
            "role": entry.role,
            "action": entry.action,
            "assigned_by_username": assigner.username if assigner else None,
            "assigned_at": entry.assigned_at,
            "notes": entry.notes
        })
    
    return response


@router.delete("/teams/{team_id}/members/{member_id}")
def remove_team_member(
    team_id: int,
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Remove a member from team (admin only)"""
    service = GameService(db)
    
    # Check if current user is team admin
    admin_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id,
        TeamMember.role == "admin",
        TeamMember.status == "active"
    ).first()
    
    if not admin_member:
        raise HTTPException(status_code=403, detail="Not authorized to remove members")
    
    # Get the member to remove
    member = db.query(TeamMember).filter(
        TeamMember.id == member_id,
        TeamMember.team_id == team_id
    ).first()
    
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    # Cannot remove the team owner
    team = db.query(Team).filter(Team.id == team_id).first()
    if team.owner_id == member.user_id:
        raise HTTPException(status_code=400, detail="Cannot remove team owner")
    
    db.delete(member)
    db.commit()
    
    return {"message": "Member removed from team"}


@router.get("/teams/{team_id}/members", response_model=List[TeamMemberResponse])
def get_team_members(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get all members of a team"""
    service = GameService(db)
    
    # Allow anyone to view team members for read-only purposes
    # Editing operations (add, update, delete) still require appropriate permissions
    
    # Get all team members with user details
    members = db.query(TeamMember, User).join(
        User, TeamMember.user_id == User.id
    ).filter(
        TeamMember.team_id == team_id,
        TeamMember.status == "active"
    ).all()
    
    result = []
    for member, user in members:
        result.append({
            "id": member.id,
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_admin": member.is_admin,
            "is_captain": member.is_captain,
            "is_vice_captain": member.is_vice_captain,
            "status": member.status,
            "joined_at": member.joined_at
        })
    
    return result


@router.get("/teams/{team_id}/with-members", response_model=TeamWithMembersResponse)
def get_team_with_members(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get team details with all members"""
    service = GameService(db)
    
    # Allow anyone to view team details and members for read-only purposes
    # Editing operations still require appropriate permissions
    
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Get team members
    members = db.query(TeamMember, User).join(
        User, TeamMember.user_id == User.id
    ).filter(
        TeamMember.team_id == team_id,
        TeamMember.status == "active"
    ).all()
    
    member_list = []
    for member, user in members:
        member_list.append({
            "id": member.id,
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_admin": member.is_admin,
            "is_captain": member.is_captain,
            "is_vice_captain": member.is_vice_captain,
            "status": member.status,
            "joined_at": member.joined_at
        })
    
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "owner_id": team.owner_id,
        "city": team.city,
        "wins": 0,  # TODO: Calculate from games
        "losses": 0,  # TODO: Calculate from games
        "members": member_list,
        "created_at": team.created_at
    }


# ============================================================================
# GAME ENDPOINTS
# ============================================================================

@router.post("/games", response_model=GameResponse)
def create_game(
    game_data: GameCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Create a new game"""
    service = GameService(db)
    
    game = service.create_match(
        home_team_id=game_data.home_team_id,
        away_team_id=game_data.away_team_id,
        match_date=game_data.match_date,
        created_by=current_user.id,
        title=game_data.title,
        location=game_data.location,
        description=game_data.description,
        tournament_id=game_data.tournament_id,
        home_players=[player.dict() for player in game_data.home_players],
        away_players=[player.dict() for player in game_data.away_players]
    )
    return game


@router.put("/games/{game_id}", response_model=GameResponse)
def update_game(
    game_id: int,
    game_data: GameUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Update game information"""
    service = GameService(db)
    game = service.get_match(game_id)
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not game creator")
    
    game = service.update_match(
        match_id=game_id,
        title=game_data.title,
        location=game_data.location,
        match_date=game_data.match_date,
        status=game_data.status
    )
    return game


@router.get("/my-games", response_model=List[GameResponse])
def get_my_games(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get games created by the current user"""
    service = GameService(db)
    matches = service.get_matches_by_creator(current_user.id)
    return matches


@router.get("/my-live-games", response_model=List[GameResponse])
def get_my_live_games(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get live games where current user is a team member"""
    # Get user's teams
    user_teams = db.query(TeamMember).filter(TeamMember.user_id == current_user.id).all()
    user_team_ids = [tm.team_id for tm in user_teams]
    
    if not user_team_ids:
        return []
    
    # Get live games where user is in either home or away team
    games = db.query(Game).filter(
        Game.status == 'in_progress',
        (Game.home_team_id.in_(user_team_ids) | Game.away_team_id.in_(user_team_ids))
    ).order_by(Game.created_at.desc()).all()
    
    return games


@router.get("/games")
def get_games(
    status: Optional[str] = Query(None, description="Filter by status: scheduled, in_progress, completed, cancelled"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session)
):
    """Get all games with optional filtering"""
    service = GameService(db)
    games = service.get_matches(status=status, limit=limit, offset=offset)
    return games


@router.get("/games/{game_id}", response_model=GameDetailsResponse)
def get_game(
    game_id: int,
    db: Session = Depends(get_db_session)
):
    """Get game details with full information"""
    service = GameService(db)
    game = service.get_match_with_details(game_id)
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    return game


@router.get("/games/{game_id}/stats", response_model=dict)
def get_game_stats(
    game_id: int,
    db: Session = Depends(get_db_session)
):
    """Get game statistics including top scorers and foul scorers"""
    service = GameService(db)
    game = service.get_match(game_id)
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Only get stats for completed or in_progress games
    if game.status not in ['completed', 'in_progress']:
        return {
            'game_id': game_id,
            'home_team_top_scorers': [],
            'away_team_top_scorers': [],
            'top_foul_scorers': []
        }
    
    stats = service.get_game_stats_summary(game_id)
    return stats


@router.delete("/games/{game_id}")
def cancel_game(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Cancel a game"""
    service = GameService(db)
    game = service.get_match(game_id)
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not game creator")
    
    service.cancel_match(game_id)
    return {"message": "Game cancelled"}


@router.get("/upcoming", response_model=List[GameResponse])
def get_upcoming_games(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session)
):
    """Get upcoming games"""
    service = GameService(db)
    games = service.get_upcoming_matches(limit=limit, offset=offset)
    return games


@router.get("/completed", response_model=List[GameResponse])
def get_completed_games(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session)
):
    """Get completed matches"""
    service = GameService(db)
    matches = service.get_completed_matches(limit=limit, offset=offset)
    return matches


@router.get("/teams/{team_id}/games", response_model=List[GameResponse])
def get_team_games(
    team_id: int,
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session)
):
    """Get games for a team"""
    service = GameService(db)
    team = service.get_team(team_id)
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    matches = service.get_team_matches(team_id, status=status, limit=limit, offset=offset)
    return matches


# ============================================================================
# MATCH EVENTS & SCORING
# ============================================================================

@router.post("/games/{game_id}/events", response_model=GameEventResponse)
def add_game_event(
    game_id: int,
    event_data: GameEventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Record a game event (goal, foul, etc.)"""
    service = GameService(db)
    game = service.get_match(game_id)
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    event = service.add_match_event(
        match_id=game_id,
        user_id=event_data.user_id,
        team_id=event_data.team_id,
        event_type=event_data.event_type,
        timestamp=event_data.timestamp,
        period=event_data.period,
        outcome=event_data.outcome
    )
    return event


@router.get("/games/{game_id}/events", response_model=List[GameEventResponse])
def get_game_events(
    game_id: int,
    db: Session = Depends(get_db_session)
):
    """Get all events from a game"""
    service = GameService(db)
    game = service.get_match(game_id)
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    events = service.get_match_events(game_id)
    return events


@router.post("/games/{game_id}/score")
def update_game_score(
    game_id: int,
    score_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Update game score"""
    service = GameService(db)
    game = service.get_match(game_id)
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Check if timeout is active - prevent scoring during timeout
    game_obj = db.query(Game).filter(Game.id == game_id).first()
    if game_obj and game_obj.timeout_active:
        raise HTTPException(status_code=403, detail="Scoring is disabled during timeout")
    
    game = service.update_match_score(
        match_id=game_id,
        home_score=score_data["home_score"],
        away_score=score_data["away_score"]
    )
    return game


@router.post("/{game_id}/timeout")
def manage_game_timeout(
    game_id: int,
    timeout_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Manage game timeout - start or revoke"""
    game = db.query(Game).filter(Game.id == game_id).first()
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Check if user is authorized (must be game admin)
    is_game_creator = game.created_by and int(game.created_by) == int(current_user.id)
    is_home_team_admin = game.home_team and game.home_team.owner_id and int(game.home_team.owner_id) == int(current_user.id)
    is_away_team_admin = game.away_team and game.away_team.owner_id and int(game.away_team.owner_id) == int(current_user.id)
    
    if not (is_game_creator or is_home_team_admin or is_away_team_admin):
        raise HTTPException(status_code=403, detail="Not authorized to manage timeout for this game")
    
    action = timeout_data.get("action")  # 'start' or 'revoke'
    
    if action == "start":
        game.timeout_active = True
        game.timeout_started_at = datetime.utcnow()
    elif action == "revoke":
        game.timeout_active = False
        game.timeout_started_at = None
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'start' or 'revoke'")
    
    game.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(game)
    
    return GameResponse.from_orm(game)


@router.get("/games/{game_id}/players/{player_id}/stats", response_model=PlayerStatsResponse)
def get_player_game_stats(
    game_id: int,
    player_id: int,
    db: Session = Depends(get_db_session)
):
    """Get player statistics for a specific game"""
    service = GameService(db)
    game = service.get_match(game_id)
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    stats = service.get_player_match_stats(game_id, player_id)
    return stats


@router.post("/games/{game_id}/finalize", response_model=FinalizeGameResponse)
def finalize_game(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Finalize a game and calculate player statistics"""
    service = GameService(db)
    game = service.get_match(game_id)
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # Check if user is authorized to end the game (must be admin)
    is_game_creator = game.created_by and int(game.created_by) == int(current_user.id)
    is_home_team_admin = game.home_team and game.home_team.owner_id and int(game.home_team.owner_id) == int(current_user.id)
    is_away_team_admin = game.away_team and game.away_team.owner_id and int(game.away_team.owner_id) == int(current_user.id)
    
    if not (is_game_creator or is_home_team_admin or is_away_team_admin):
        raise HTTPException(status_code=403, detail="Not authorized to end this game")
    
    try:
        result = service.finalize_game(game_id)
        return {
            'game_id': game.id,
            'status': 'completed',
            'player_stats': result['player_stats'],
            'home_team_name': game.home_team.name if game.home_team else 'Home Team',
            'away_team_name': game.away_team.name if game.away_team else 'Away Team',
            'home_score': game.home_score,
            'away_score': game.away_score,
            'message': f'Game finalized. Stats calculated for {result["total_players"]} players.'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/stats", response_model=UserStatsResponse)
def get_user_stats(
    user_id: int,
    db: Session = Depends(get_db_session)
):
    """Get career statistics for a user"""
    service = GameService(db)
    
    try:
        stats = service.get_player_stats(user_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/users/{user_id}/game-stats", response_model=List[PlayerGameStatsResponse])
def get_user_game_stats(
    user_id: int,
    db: Session = Depends(get_db_session)
):
    """Get all game stats for a user"""
    service = GameService(db)
    
    try:
        stats = service.get_player_game_stats_list(user_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TOURNAMENT ENDPOINTS
# ============================================================================

@router.post("/tournaments", response_model=TournamentResponse)
def create_tournament(
    tournament_data: TournamentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Create a new tournament"""
    service = GameService(db)
    
    tournament = service.create_tournament(
        organizer_id=current_user.id,
        title=tournament_data.title,
        format=tournament_data.format,
        start_date=tournament_data.start_date,
        description=tournament_data.description,
        location=tournament_data.location,
        max_teams=tournament_data.max_teams,
        end_date=tournament_data.end_date,
        entry_fee=tournament_data.entry_fee,
        prize_pool=tournament_data.prize_pool,
        rules=tournament_data.rules
    )
    return tournament


@router.put("/tournaments/{tournament_id}", response_model=TournamentResponse)
def update_tournament(
    tournament_id: int,
    tournament_data: TournamentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Update tournament information"""
    service = GameService(db)
    tournament = service.get_tournament(tournament_id)
    
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if tournament.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not tournament organizer")
    
    tournament = service.update_tournament(
        tournament_id=tournament_id,
        title=tournament_data.title,
        status=tournament_data.status,
        description=tournament_data.description,
        end_date=tournament_data.end_date
    )
    return tournament


@router.get("/tournaments/{tournament_id}", response_model=TournamentResponse)
def get_tournament(
    tournament_id: int,
    db: Session = Depends(get_db_session)
):
    """Get tournament details"""
    service = GameService(db)
    tournament = service.get_tournament(tournament_id)
    
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    return tournament


@router.get("/tournaments", response_model=List[TournamentResponse])
def list_tournaments(
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session)
):
    """List tournaments"""
    service = GameService(db)
    tournaments = service.get_tournaments(status=status, limit=limit, offset=offset)
    return tournaments


@router.delete("/tournaments/{tournament_id}")
def delete_tournament(
    tournament_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Delete a tournament"""
    service = GameService(db)
    tournament = service.get_tournament(tournament_id)
    
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if tournament.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not tournament organizer")
    
    service.delete_tournament(tournament_id)
    return {"message": "Tournament deleted"}


@router.post("/tournaments/{tournament_id}/teams/{team_id}")
def add_team_to_tournament(
    tournament_id: int,
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Add a team to a tournament"""
    service = GameService(db)
    tournament = service.get_tournament(tournament_id)
    
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    tournament_team = service.add_team_to_tournament(tournament_id, team_id)
    return {"message": "Team added to tournament", "tournament_team_id": tournament_team.id}


@router.delete("/tournaments/{tournament_id}/teams/{team_id}")
def remove_team_from_tournament(
    tournament_id: int,
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Remove a team from a tournament"""
    service = GameService(db)
    tournament = service.get_tournament(tournament_id)
    
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    service.remove_team_from_tournament(tournament_id, team_id)
    return {"message": "Team removed from tournament"}


@router.post("/tournaments/{tournament_id}/bracket", response_model=BracketResponse)
def generate_bracket(
    tournament_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Generate tournament bracket"""
    service = GameService(db)
    tournament = service.get_tournament(tournament_id)
    
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if tournament.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not tournament organizer")
    
    bracket = service.generate_bracket(tournament_id)
    return bracket


@router.get("/tournaments/{tournament_id}/bracket", response_model=BracketResponse)
def get_bracket(
    tournament_id: int,
    db: Session = Depends(get_db_session)
):
    """Get tournament bracket"""
    service = GameService(db)
    tournament = service.get_tournament(tournament_id)
    
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    bracket = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not bracket or not bracket.bracket:
        raise HTTPException(status_code=404, detail="Bracket not found")
    
    return bracket.bracket


@router.post("/tournaments/{tournament_id}/advance")
def advance_team_in_bracket(
    tournament_id: int,
    advance_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Advance team in tournament bracket"""
    service = GameService(db)
    tournament = service.get_tournament(tournament_id)
    
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if tournament.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not tournament organizer")
    
    service.advance_team_in_bracket(
        tournament_id=tournament_id,
        match_id=advance_data["match_id"],
        winner_team_id=advance_data["winner_team_id"]
    )
    return {"message": "Team advanced in bracket"}


# ============================================================================
# PLAYER STATS ENDPOINTS
# ============================================================================

@router.get("/users/{user_id}/stats", response_model=PlayerStatsSummaryResponse)
def get_player_stats(
    user_id: int,
    db: Session = Depends(get_db_session)
):
    """Get player statistics"""
    service = GameService(db)
    stats = service.get_player_stats(user_id)
    return stats


@router.get("/users/{user_id}/game-stats", response_model=List[PlayerGameStatsResponse])
def get_player_game_stats(
    user_id: int,
    db: Session = Depends(get_db_session)
):
    """Get player game-by-game statistics"""
    service = GameService(db)
    stats = service.get_player_game_stats_list(user_id)
    return stats
