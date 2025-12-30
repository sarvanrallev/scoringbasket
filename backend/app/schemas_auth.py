"""
Pydantic schemas for authentication and user management
Used for request validation and response serialization
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class UserRegister(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=72)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    mobile_number: Optional[str] = Field(None, pattern=r'^\+?1?\d{9,15}$')  # International phone number format

    class Config:
        schema_extra = {
            "example": {
                "email": "john@example.com",
                "username": "johndoe",
                "password": "securepass123",
                "first_name": "John",
                "last_name": "Doe",
                "mobile_number": "+1234567890"
            }
        }


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str

    class Config:
        schema_extra = {
            "example": {
                "email": "john@example.com",
                "password": "securepass123"
            }
        }


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    mobile_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    preferred_position: Optional[str] = None
    jersey_number: Optional[int] = Field(None, ge=0, le=99)
    hand_style: Optional[str] = Field(None, pattern=r'^(right_hand|left_hand)$')
    favorite_player: Optional[str] = None
    height_cm: Optional[int] = None

    class Config:
        schema_extra = {
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "bio": "Professional basketball player",
                "city": "New York",
                "country": "USA",
                "mobile_number": "+1234567890",
                "preferred_position": "PG",
                "jersey_number": 23,
                "hand_style": "right_hand",
                "favorite_player": "LeBron James",
                "height_cm": 185
            }
        }


class ChangePassword(BaseModel):
    """Schema for changing password"""
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=72)

    class Config:
        schema_extra = {
            "example": {
                "old_password": "oldpass123",
                "new_password": "newpass456"
            }
        }


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class UserProfileResponse(BaseModel):
    """Response schema for user profile"""
    id: int
    bio: Optional[str]
    avatar_url: Optional[str]
    city: Optional[str]
    country: Optional[str]
    mobile_number: Optional[str]
    date_of_birth: Optional[datetime]
    preferred_position: Optional[str]
    jersey_number: Optional[int]
    hand_style: Optional[str]
    favorite_player: Optional[str]
    height_cm: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserStatsResponse(BaseModel):
    """Response schema for user statistics"""
    id: int
    total_matches: int
    total_points: int
    total_assists: int
    total_rebounds: int
    matches_won: int
    matches_lost: int
    win_rate: float
    points_per_game: float
    assists_per_game: float
    rebounds_per_game: float

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """Response schema for user information"""
    id: int
    email: str
    username: str
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    is_active: bool
    profile: Optional[UserProfileResponse]
    stats: Optional[UserStatsResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Response schema for authentication tokens"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

    class Config:
        schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "user": {
                    "id": 1,
                    "email": "john@example.com",
                    "username": "johndoe"
                }
            }
        }


class AuthResponse(BaseModel):
    """Response schema for auth endpoints"""
    message: str
    user: UserResponse

    class Config:
        schema_extra = {
            "example": {
                "message": "User registered successfully",
                "user": {
                    "id": 1,
                    "email": "john@example.com",
                    "username": "johndoe"
                }
            }
        }


class UserSearchResponse(BaseModel):
    """Response schema for user search results"""
    id: int
    username: str
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": 1,
                "username": "johndoe",
                "first_name": "John",
                "last_name": "Doe",
                "phone": "+1234567890"
            }
        }
