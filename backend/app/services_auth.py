"""
Authentication service for user management
Handles user registration, login, and profile operations
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text
from typing import Optional, Tuple
from datetime import datetime
from .models import User, UserProfile, UserStats, HandStyle
from .security import hash_password, verify_password, create_access_token, create_refresh_token
from .schemas_auth import UserRegister, UserLogin


class AuthService:
    """Service for authentication operations"""

    @staticmethod
    def register_user(db: Session, user_data: UserRegister) -> Tuple[Optional[User], Optional[str]]:
        """
        Register a new user
        Returns: (User object, error message)
        """
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            return None, "Email already registered"

        # Check if username already exists
        existing_user = db.query(User).filter(User.username == user_data.username).first()
        if existing_user:
            return None, "Username already taken"

        # Create new user
        try:
            user = User(
                email=user_data.email,
                username=user_data.username,
                password_hash=hash_password(user_data.password),
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                is_active=True
            )
            db.add(user)
            db.flush()  # Flush to get user.id

            # Create associated profile
            profile = UserProfile(
                user_id=user.id,
                mobile_number=user_data.mobile_number
            )
            db.add(profile)

            # Create associated stats
            stats = UserStats(user_id=user.id)
            db.add(stats)

            db.commit()
            db.refresh(user)
            return user, None
        except Exception as e:
            db.rollback()
            return None, str(e)

    @staticmethod
    def authenticate_user(db: Session, user_data: UserLogin) -> Tuple[Optional[User], Optional[str]]:
        """
        Authenticate user by email and password
        Returns: (User object, error message)
        """
        user = db.query(User).filter(User.email == user_data.email).first()
        
        if not user:
            return None, "Invalid email or password"

        if not verify_password(user_data.password, user.password_hash):
            return None, "Invalid email or password"

        if not user.is_active:
            return None, "User account is disabled"

        return user, None

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID with relationships"""
        return db.query(User).options(
            joinedload(User.profile),
            joinedload(User.stats)
        ).filter(User.id == user_id).first()

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """Get user by username with relationships"""
        return db.query(User).options(
            db.joinedload(User.profile),
            db.joinedload(User.stats)
        ).filter(User.username == username).first()

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def update_profile(db: Session, user_id: int, **kwargs) -> Tuple[Optional[User], Optional[str]]:
        """Update user profile information using upsert pattern"""
        try:
            # Get user
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None, "User not found"

            # Validate required user fields
            first_name = kwargs.get('first_name')
            last_name = kwargs.get('last_name')
            if not first_name or not str(first_name).strip():
                return None, "First name is required"
            if not last_name or not str(last_name).strip():
                return None, "Last name is required"

            # Update user fields
            user.first_name = str(first_name).strip()
            user.last_name = str(last_name).strip()

            # Parse and validate date_of_birth if provided
            date_of_birth_value = kwargs.get('date_of_birth')
            parsed_date = None
            if date_of_birth_value:
                try:
                    # Handle different date formats
                    if 'T' in str(date_of_birth_value):
                        date_str = str(date_of_birth_value).split('T')[0]  # Get just the date part
                        parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
                    else:
                        parsed_date = datetime.strptime(str(date_of_birth_value), '%Y-%m-%d')
                except ValueError as e:
                    return None, f"Invalid date format for date_of_birth. Use YYYY-MM-DD format. Error: {str(e)}"

            # Validate jersey_number
            jersey_number = None
            jersey_number_value = kwargs.get('jersey_number')
            if jersey_number_value is not None:
                try:
                    jersey_num = int(jersey_number_value)
                    if not (0 <= jersey_num <= 99):
                        return None, "Jersey number must be between 0 and 99"
                    jersey_number = jersey_num
                except (ValueError, TypeError):
                    return None, "Jersey number must be a valid integer"
            
            # Validate and convert height_cm
            height_cm = None
            height_cm_value = kwargs.get('height_cm')
            if height_cm_value is not None:
                try:
                    height = int(height_cm_value)
                    if height <= 0:
                        return None, "Height must be a positive number"
                    height_cm = height
                except (ValueError, TypeError):
                    return None, "Height must be a valid positive integer"
            
            # Handle and validate hand_style enum
            hand_style = None
            hand_style_value = kwargs.get('hand_style')
            if hand_style_value and str(hand_style_value).strip():
                try:
                    # Normalize the hand_style value - convert any format to lowercase with underscore
                    hand_style_str = str(hand_style_value).strip().lower().replace(' ', '_').replace('-', '_')
                    hand_style = HandStyle(hand_style_str)
                except ValueError as e:
                    return None, f"Invalid hand_style. Must be 'right_hand' or 'left_hand'. Error: {str(e)}"
            
            # Check if profile exists
            profile_exists = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
            print(f"Profile exists for user {user_id}: {profile_exists is not None}")
            
            if profile_exists:
                # Update the existing profile - only UPDATE, no INSERT
                update_query = text("""
                    UPDATE user_profiles 
                    SET bio = :bio,
                        avatar_url = :avatar_url,
                        city = :city,
                        country = :country,
                        mobile_number = :mobile_number,
                        date_of_birth = :date_of_birth,
                        preferred_position = :preferred_position,
                        jersey_number = :jersey_number,
                        hand_style = :hand_style,
                        favorite_player = :favorite_player,
                        height_cm = :height_cm,
                        updated_at = NOW()
                    WHERE user_id = :user_id
                """)
                result = db.execute(update_query, {
                    'user_id': user_id,
                    'bio': kwargs.get('bio') if kwargs.get('bio') else None,
                    'avatar_url': kwargs.get('avatar_url') if kwargs.get('avatar_url') else None,
                    'city': kwargs.get('city') if kwargs.get('city') else None,
                    'country': kwargs.get('country') if kwargs.get('country') else None,
                    'mobile_number': kwargs.get('mobile_number') if kwargs.get('mobile_number') else None,
                    'date_of_birth': parsed_date,
                    'preferred_position': kwargs.get('preferred_position') if kwargs.get('preferred_position') else None,
                    'favorite_player': kwargs.get('favorite_player') if kwargs.get('favorite_player') else None,
                    'jersey_number': jersey_number,
                    'hand_style': hand_style.value if hand_style else None,
                    'height_cm': height_cm,
                })
                print(f"Profile update result - rows affected: {result.rowcount}")
            else:
                # Profile doesn't exist - INSERT new one
                insert_query = text("""
                    INSERT INTO user_profiles 
                    (user_id, bio, avatar_url, city, country, mobile_number, date_of_birth, 
                     preferred_position, jersey_number, hand_style, favorite_player, height_cm, created_at, updated_at)
                    VALUES 
                    (:user_id, :bio, :avatar_url, :city, :country, :mobile_number, :date_of_birth,
                     :preferred_position, :jersey_number, :hand_style, :favorite_player, :height_cm, NOW(), NOW())
                """)
                result = db.execute(insert_query, {
                    'user_id': user_id,
                    'bio': kwargs.get('bio') if kwargs.get('bio') else None,
                    'avatar_url': kwargs.get('avatar_url') if kwargs.get('avatar_url') else None,
                    'city': kwargs.get('city') if kwargs.get('city') else None,
                    'country': kwargs.get('country') if kwargs.get('country') else None,
                    'mobile_number': kwargs.get('mobile_number') if kwargs.get('mobile_number') else None,
                    'date_of_birth': parsed_date,
                    'preferred_position': kwargs.get('preferred_position') if kwargs.get('preferred_position') else None,
                    'favorite_player': kwargs.get('favorite_player') if kwargs.get('favorite_player') else None,
                    'jersey_number': jersey_number,
                    'hand_style': hand_style.value if hand_style else None,
                    'height_cm': height_cm,
                })
                print(f"Profile insert result - rows affected: {result.rowcount}")

            # Commit all changes
            db.commit()
            
            # Refresh user to get updated profile
            db.refresh(user)
            
            # Explicitly reload the profile relationship
            # After raw SQL update, we need to clear the session cache
            db.expire_all()
            
            # Fetch fresh user with profile relationship loaded
            user = db.query(User).filter(User.id == user_id).first()
            
            print(f"User after update: id={user.id}, profile={user.profile}")
            
            return user, None
        except Exception as e:
            db.rollback()
            import traceback
            error_trace = traceback.format_exc()
            print(f"Profile update error: {error_trace}")
            return None, f"Failed to update profile: {str(e)}"

    @staticmethod
    def change_password(db: Session, user_id: int, old_password: str, new_password: str) -> Tuple[bool, str]:
        """Change user password"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "User not found"

        if not verify_password(old_password, user.password_hash):
            return False, "Incorrect old password"

        try:
            user.password_hash = hash_password(new_password)
            db.commit()
            return True, "Password changed successfully"
        except Exception as e:
            db.rollback()
            return False, str(e)

    @staticmethod
    def deactivate_user(db: Session, user_id: int) -> Tuple[bool, str]:
        """Deactivate user account"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "User not found"

            user.is_active = False
            db.commit()
            return True, "User account deactivated"
        except Exception as e:
            db.rollback()
            return False, str(e)
