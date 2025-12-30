"""
Match and Tournament API routes
Handles: teams, matches, events, tournaments, brackets
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from .database import get_db_session
from .models import User, Team, TeamMember, TeamLeadershipHistory, Match, Tournament
from .routes_auth import get_current_user
from .services_matches import MatchService
from .schemas_matches import (
    TeamCreate, TeamUpdate, TeamResponse, TeamDetailsResponse, PlayerResponse,
    TeamMemberInvite, TeamMemberUpdateRole, TeamMemberResponse, TeamLeadershipHistoryResponse, TeamWithMembersResponse,
    MatchCreate, MatchUpdate, MatchResponse, MatchEventCreate, MatchEventResponse,
    MatchStatisticsResponse, MatchDetailsResponse, PlayerStatsResponse,
    TournamentCreate, TournamentUpdate, TournamentResponse, BracketResponse
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
    service = MatchService(db)
    team = service.create_team(
        owner_id=current_user.id,
        name=team_data.name,
        description=team_data.description,
        city=team_data.city
    )
    
    # Create team membership for the creator as admin
    team_member = TeamMember(
        team_id=team.id,
        user_id=current_user.id,
        role="admin",
        is_admin=True,
        status="active"
    )
    
    db.add(team_member)
    db.commit()
    
    return team


@router.put("/teams/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: int,
    team_data: TeamUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Update team information"""
    service = MatchService(db)
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
    service = MatchService(db)
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    owner_id = team['owner_id'] if isinstance(team, dict) else team.owner_id
    if owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not team owner")
    
    service.delete_team(team_id)
    return {"message": "Team deleted successfully"}


@router.get("/teams", response_model=List[TeamResponse])
def get_teams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get all teams for the current user (teams they own or are members of)"""
    service = MatchService(db)
    
    # Get teams where user is owner
    owned_teams = service.get_user_teams(current_user.id)
    
    # Get teams where user is a member (but not owner)
    member_teams = db.query(Team).join(TeamMember).filter(
        TeamMember.user_id == current_user.id,
        TeamMember.status == "active",
        Team.owner_id != current_user.id  # Exclude teams they own
    ).all()
    
    # Convert member teams to dict format with stats
    member_teams_dict = [
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
        for team in member_teams
    ]
    
    # Combine and return
    all_teams = owned_teams + member_teams_dict
    return all_teams


@router.get("/teams/{team_id}", response_model=TeamResponse)
def get_team(
    team_id: int,
    db: Session = Depends(get_db_session)
):
    """Get team details"""
    service = MatchService(db)
    team = service.get_team(team_id)
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return team


@router.get("/my-teams", response_model=List[TeamResponse])
def get_my_teams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get teams owned by current user"""
    service = MatchService(db)
    teams = service.get_user_teams(current_user.id)
    return teams


@router.post("/teams/{team_id}/players", response_model=PlayerResponse)
def add_player_to_team(
    team_id: int,
    player_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Add a player to a team"""
    service = MatchService(db)
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
    service = MatchService(db)
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
    service = MatchService(db)
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
    service = MatchService(db)
    
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
    service = MatchService(db)
    
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
    service = MatchService(db)
    
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
    service = MatchService(db)
    
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
    service = MatchService(db)
    
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
    service = MatchService(db)
    
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
# MATCH ENDPOINTS
# ============================================================================

@router.post("/games", response_model=MatchResponse)
def create_match(
    match_data: MatchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Create a new match"""
    service = MatchService(db)
    
    match = service.create_match(
        home_team_id=match_data.home_team_id,
        away_team_id=match_data.away_team_id,
        match_date=match_data.match_date,
        created_by=current_user.id,
        title=match_data.title,
        location=match_data.location,
        description=match_data.description,
        tournament_id=match_data.tournament_id,
        home_players=[player.dict() for player in match_data.home_players],
        away_players=[player.dict() for player in match_data.away_players]
    )
    return match


@router.put("/games/{match_id}", response_model=MatchResponse)
def update_match(
    match_id: int,
    match_data: MatchUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Update match information"""
    service = MatchService(db)
    match = service.get_match(match_id)
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not match creator")
    
    match = service.update_match(
        match_id=match_id,
        title=match_data.title,
        location=match_data.location,
        match_date=match_data.match_date,
        status=match_data.status
    )
    return match


@router.get("/games/{match_id}", response_model=MatchDetailsResponse)
def get_match(
    match_id: int,
    db: Session = Depends(get_db_session)
):
    """Get match details with full information"""
    service = MatchService(db)
    match = service.get_match_with_details(match_id)
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    return match


@router.delete("/games/{match_id}")
def cancel_match(
    match_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Cancel a match"""
    service = MatchService(db)
    match = service.get_match(match_id)
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not match creator")
    
    service.cancel_match(match_id)
    return {"message": "Match cancelled"}


@router.get("/my-games", response_model=List[MatchResponse])
def get_my_games(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get games created by the current user"""
    service = MatchService(db)
    matches = service.get_matches_by_creator(current_user.id)
    return matches


@router.get("/games", response_model=List[MatchResponse])
def get_matches(
    status: str = Query(None, description="Filter by status: scheduled, in_progress, completed, cancelled"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session)
):
    """Get all matches with optional filtering"""
    service = MatchService(db)
    matches = service.get_matches(status=status, limit=limit, offset=offset)
    return matches


@router.get("/upcoming", response_model=List[MatchResponse])
def get_upcoming_matches(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session)
):
    """Get upcoming matches"""
    service = MatchService(db)
    matches = service.get_upcoming_matches(limit=limit, offset=offset)
    return matches


@router.get("/completed", response_model=List[MatchResponse])
def get_completed_matches(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session)
):
    """Get completed matches"""
    service = MatchService(db)
    matches = service.get_completed_matches(limit=limit, offset=offset)
    return matches


@router.get("/teams/{team_id}/matches", response_model=List[MatchResponse])
def get_team_matches(
    team_id: int,
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db_session)
):
    """Get matches for a team"""
    service = MatchService(db)
    team = service.get_team(team_id)
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    matches = service.get_team_matches(team_id, status=status, limit=limit, offset=offset)
    return matches


# ============================================================================
# MATCH EVENTS & SCORING
# ============================================================================

@router.post("/games/{match_id}/events", response_model=MatchEventResponse)
def add_match_event(
    match_id: int,
    event_data: MatchEventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Record a match event (goal, foul, etc.)"""
    service = MatchService(db)
    match = service.get_match(match_id)
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    event = service.add_match_event(
        match_id=match_id,
        player_id=event_data.player_id,
        team_id=event_data.team_id,
        event_type=event_data.event_type,
        points=event_data.points,
        timestamp=event_data.timestamp,
        quarter=event_data.quarter
    )
    return event


@router.get("/games/{match_id}/events", response_model=List[MatchEventResponse])
def get_match_events(
    match_id: int,
    db: Session = Depends(get_db_session)
):
    """Get all events from a match"""
    service = MatchService(db)
    match = service.get_match(match_id)
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    events = service.get_match_events(match_id)
    return events


@router.post("/games/{match_id}/score")
def update_match_score(
    match_id: int,
    score_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Update match score"""
    service = MatchService(db)
    match = service.get_match(match_id)
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    match = service.update_match_score(
        match_id=match_id,
        home_score=score_data["home_score"],
        away_score=score_data["away_score"]
    )
    return match


@router.get("/games/{match_id}/stats", response_model=MatchStatisticsResponse)
def get_match_statistics(
    match_id: int,
    db: Session = Depends(get_db_session)
):
    """Get match statistics"""
    service = MatchService(db)
    match = service.get_match(match_id)
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    stats = service.get_match_statistics(match_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Statistics not found")
    
    return stats


@router.get("/games/{match_id}/players/{player_id}/stats", response_model=PlayerStatsResponse)
def get_player_match_stats(
    match_id: int,
    player_id: int,
    db: Session = Depends(get_db_session)
):
    """Get player statistics for a specific match"""
    service = MatchService(db)
    match = service.get_match(match_id)
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    stats = service.get_player_match_stats(match_id, player_id)
    return stats


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
    service = MatchService(db)
    
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
    service = MatchService(db)
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
    service = MatchService(db)
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
    service = MatchService(db)
    tournaments = service.get_tournaments(status=status, limit=limit, offset=offset)
    return tournaments


@router.delete("/tournaments/{tournament_id}")
def delete_tournament(
    tournament_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Delete a tournament"""
    service = MatchService(db)
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
    service = MatchService(db)
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
    service = MatchService(db)
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
    service = MatchService(db)
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
    service = MatchService(db)
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
    service = MatchService(db)
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
