"""
Authentication API routes
Handles user registration, login, profile management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from .database import get_db_session
from .models import User, UserProfile, UserStats, FAVORITE_PLAYERS, HandStyle, TeamMember
from .security import create_access_token, create_refresh_token, verify_access_token
from .services_auth import AuthService
from .schemas_auth import (
    UserRegister, UserLogin, UserProfileUpdate, ChangePassword,
    TokenResponse, AuthResponse, UserResponse, UserSearchResponse
)
from .services_auth import AuthService

# JWT Authentication dependency
def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db_session)) -> User:
    """Get current authenticated user from JWT token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token
    token = authorization.split(" ")[1]

    # Verify token
    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database with profile relationship
    user = db.query(User).options(joinedload(User.profile)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# OPTIONS endpoints for CORS preflight
@router.options("/login")
async def options_login():
    """Handle CORS preflight for login"""
    return {}


@router.options("/register")
async def options_register():
    """Handle CORS preflight for register"""
    return {}


@router.options("/logout")
async def options_logout():
    """Handle CORS preflight for logout"""
    return {}


@router.get("/test-auth")
async def test_auth(authorization: Optional[str] = Header(None, alias="Authorization")):
    """Test endpoint to check authorization header"""
    return {"authorization": authorization, "type": type(authorization).__name__}


@router.get("/favorite-players")
async def get_favorite_players():
    """Get list of available favorite basketball players"""
    return {
        "favorite_players": FAVORITE_PLAYERS,
        "count": len(FAVORITE_PLAYERS)
    }


@router.get("/hand-styles")
async def get_hand_styles():
    """Get list of available hand style options"""
    return {
        "hand_styles": [style.value for style in HandStyle],
        "count": len(HandStyle)
    }


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db = Depends(get_db_session)):
    """Register a new user"""
    user, error = AuthService.register_user(db, user_data)
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return {
        "message": "User registered successfully",
        "user": UserResponse.model_validate(user)
    }


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db = Depends(get_db_session)):
    """Login user and return access/refresh tokens"""
    try:
        user, error = AuthService.authenticate_user(db, credentials)
        
        if error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error
            )
        
        # Create tokens
        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user)
        }
    except Exception as e:
        import traceback
        print(f"❌ Login error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout user by clearing client-side tokens"""
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db = Depends(get_db_session)
):
    """Get current authenticated user profile"""
    # Re-fetch user with eager loading of relationships
    user = db.query(User).filter(User.id == current_user.id).first()
    print(f"Fetched user {user.id} with profile: {user.profile}")
    return UserResponse.model_validate(user)


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db_session)
):
    """Update current user's profile"""
    print(f"Profile update request for user {current_user.id}:")
    print(f"  Data received: {profile_data.model_dump(exclude_unset=True)}")
    
    user, error = AuthService.update_profile(
        db,
        current_user.id,
        **profile_data.model_dump(exclude_unset=True)
    )
    
    if error:
        print(f"  Error: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    print(f"  Success: Profile updated")
    return UserResponse.model_validate(user)


@router.post("/change-password")
async def change_password(
    pwd_data: ChangePassword,
    current_user: User = Depends(get_current_user),
    db = Depends(get_db_session)
):
    """Change password for current user"""
    success, message = AuthService.change_password(
        db,
        current_user.id,
        pwd_data.old_password,
        pwd_data.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return {"message": message}


@router.get("/users/{username}", response_model=UserResponse)
async def get_user_by_username(username: str, db = Depends(get_db_session)):
    """Get public user profile by username"""
    user = AuthService.get_user_by_username(db, username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.model_validate(user)


@router.get("/users/id/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id: int, db = Depends(get_db_session)):
    """Get public user profile by user ID"""
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.model_validate(user)


@router.get("/search-users", response_model=List[UserSearchResponse])
async def search_users(
    q: str = Query(..., description="Search query for user name or phone"),
    team_id: Optional[int] = Query(None, description="Team ID to exclude existing members"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Search for users by name or phone number for team invitations"""
    if len(q.strip()) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query must be at least 1 character long"
        )

    # Build search query
    search_term = f"%{q.strip()}%"
    
    # Also create a search term with spaces replaced by underscores for username matching
    underscore_term = f"%{q.strip().replace(' ', '_')}%"

    # Base query - search by first_name, last_name, username, or phone
    query = db.query(User).filter(
        User.is_active == True,
        User.id != current_user.id,  # Exclude current user
        or_(
            User.first_name.ilike(search_term),
            User.last_name.ilike(search_term),
            User.username.ilike(search_term),
            User.username.ilike(underscore_term),  # Also search with underscores
            User.phone.ilike(search_term)
        )
    )

    # Exclude users already in the team if team_id is provided
    if team_id:
        existing_member_ids = db.query(TeamMember.user_id).filter(
            TeamMember.team_id == team_id,
            TeamMember.status.in_(["active", "pending"])
        ).subquery()

        query = query.filter(~User.id.in_(existing_member_ids))

    # Limit results to prevent overwhelming responses
    users = query.limit(20).all()

    # Convert to response format
    results = []
    for user in users:
        results.append(UserSearchResponse(
            id=user.id,
            username=user.username,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            phone=user.phone or ""
        ))

    return results


@router.post("/deactivate")
async def deactivate_account(
    current_user: User = Depends(get_current_user),
    db = Depends(get_db_session)
):
    """Deactivate current user account"""
    success, message = AuthService.deactivate_user(db, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return {"message": message}
