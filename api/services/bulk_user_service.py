"""
Bulk user creation service for importing players from Fargo.
Generates unique usernames/passwords and exports as CSV.
"""

import csv
import io
import secrets
import string
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session

from api.models.user import User
from api.auth import hash_password


def generate_unique_username(base_name: str, db: Session, max_attempts: int = 100) -> str:
    """
    Build a login username from the player's Fargo name.

    Policy: the username MUST match the player's name as stored in the Fargo DB, so
    operators can hand a player their Fargo name as the first-login credential. The
    name is trimmed and internal whitespace is collapsed to single spaces; case is
    preserved exactly as Fargo has it. Login lookups are case/whitespace-insensitive
    (see api.auth.get_user_by_username), so the handed-out name works regardless of
    how the player types it.

    On a true duplicate name (two distinct players with the same Fargo name), a
    numeric suffix is appended (e.g. "John Smith 2").
    """
    fargo_name = " ".join((base_name or "").split())
    if not fargo_name:
        # Never create a blank username.
        return f"player_{secrets.token_hex(3)}"

    if not db.query(User).filter_by(username=fargo_name).first():
        return fargo_name

    # Same Fargo name already taken — disambiguate with a numeric suffix.
    for i in range(2, max_attempts + 2):
        candidate = f"{fargo_name} {i}"
        if not db.query(User).filter_by(username=candidate).first():
            return candidate

    # Extremely unlikely fallback.
    return f"{fargo_name} {secrets.token_hex(3)}"


def generate_password(length: int = 12) -> str:
    """Generate a secure random password."""
    # Mix uppercase, lowercase, digits, symbols
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits + "!@#$%"
    password = ''.join(secrets.choice(chars) for _ in range(length))
    # Ensure at least one of each type
    password = list(password)
    password[0] = secrets.choice(string.ascii_uppercase)
    password[1] = secrets.choice(string.digits)
    return ''.join(password)


def create_bulk_users_from_fargo(
    fargo_players: List[Dict],
    db: Session,
    associations: Optional[List[str]] = None,
) -> Tuple[List[Dict], List[str]]:
    """
    Create users from Fargo player data.
    
    Args:
        fargo_players: List of player dicts with keys:
            - name: Full name
            - fargo_rating: Fargo rating
            - fargo_id: Fargo player ID (optional)
            - city: City (optional)
            - state: State (optional)
            - associations: List of associations (optional, can also be passed separately)
        db: Database session
        associations: Optional list of associations to assign to all users
    
    Returns:
        created_users: List of dicts with username, password, name, fargo_rating, associations
        errors: List of error messages
    """
    from sqlalchemy import text
    
    created_users = []
    errors = []
    temp_passwords = {}  # user_id -> plaintext password
    
    for player in fargo_players:
        try:
            name = player.get('name', '').strip()
            if not name:
                errors.append(f"Skipped entry: missing name")
                continue
            
            # Get associations from player dict or parameter
            player_associations = player.get('associations', associations or [])
            if isinstance(player_associations, str):
                player_associations = [a.strip() for a in player_associations.split(',') if a.strip()]
            
            # Generate username
            username = generate_unique_username(name, db)
            
            # Generate password
            password = generate_password()
            password_hash = hash_password(password)
            
            # Create placeholder email (will be replaced when user sets their email)
            placeholder_email = f"pending_{username}@fargo.local"
            
            # Check if placeholder email already exists
            email_counter = 1
            while db.query(User).filter_by(email=placeholder_email).first():
                placeholder_email = f"pending_{username}_{email_counter}@fargo.local"
                email_counter += 1
            
            # Create user
            user = User(
                username=username,
                email=placeholder_email,
                password_hash=password_hash,
                nickname=None,  # Player will set their own nickname
                role="user",
                state=player.get('state'),
                country=player.get('country', 'USA'),
                home_pool_room=player.get('pool_room'),
                is_active=True,
                email_verified=False,
                requires_email_setup=True,
                force_password_reset=False,
            )
            
            db.add(user)
            db.flush()  # Get the ID without committing yet
            user_id = user.id
            
            # Store temp password
            temp_passwords[user_id] = password
            
            # Store temp password in user_temp_passwords table
            try:
                db.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_temp_passwords (
                        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                        temp_password TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                db.execute(text("""
                    INSERT INTO user_temp_passwords (user_id, temp_password, created_at)
                    VALUES (:user_id, :password, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        temp_password = EXCLUDED.temp_password,
                        created_at = NOW()
                """), {
                    "user_id": user_id,
                    "password": password
                })
            except Exception as e:
                # Table might not exist - log but continue
                import logging
                logging.getLogger(__name__).warning(f"Could not store temp password: {e}")
            
            # Create user_associations records
            if player_associations:
                for assoc in player_associations:
                    try:
                        db.execute(text("""
                            INSERT INTO user_associations (user_id, association, created_at)
                            VALUES (:user_id, :association, NOW())
                            ON CONFLICT (user_id, association) DO NOTHING
                        """), {
                            "user_id": user_id,
                            "association": assoc
                        })
                    except Exception as e:
                        errors.append(f"Error adding association {assoc} for {name}: {str(e)}")
            
            created_users.append({
                'username': username,
                'password': password,
                'name': name,
                'fargo_rating': player.get('fargo_rating', 'N/A'),
                'state': player.get('state', ''),
                'fargo_id': player.get('fargo_id', ''),
                'associations': player_associations or [],
            })
            
        except Exception as e:
            errors.append(f"Error creating user for {player.get('name', 'Unknown')}: {str(e)}")
    
    # Commit all users at once
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"Database error: {str(e)}")
        return [], errors
    
    return created_users, errors


def export_users_csv(users: List[Dict]) -> str:
    """
    Export users to CSV format.
    
    CSV columns: username, password, name, fargo_rating, state, fargo_id
    """
    output = io.StringIO()
    fieldnames = ['username', 'password', 'name', 'fargo_rating', 'state', 'fargo_id']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    
    writer.writeheader()
    for user in users:
        writer.writerow(user)
    
    return output.getvalue()
