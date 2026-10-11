#!/usr/bin/env python3
"""
Create user accounts for Fargo-rated players with association tracking.

Reads player names from Fargo archives (or JSON/CSV file), deduplicates across
associations, and creates user accounts with temporary passwords. Tracks which
associations each player belongs to in the user_associations table.

Players will need to:
1. Login with temporary credentials
2. Provide their email address
3. Verify email
4. Set a new password
"""

import argparse
import json
import csv
import sys
import os
from typing import Dict, List, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db, get_database_manager
from api.models.user import User
from api.services.bulk_user_service import generate_unique_username, generate_password
from api.services.fargo_client import normalized_match_key
from api.auth import hash_password


def read_fargo_players_json(json_file: str) -> Dict[str, Dict]:
    """Read player data from JSON file created by extract_fargo_player_names.py."""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    player_map = {}
    for item in data:
        key = item.get('normalized_key') or normalized_match_key(item['name'])
        player_map[key] = {
            'name': item['name'],
            'associations': set(item.get('associations', []))
        }
    
    return player_map


def read_fargo_players_csv(csv_file: str) -> Dict[str, Dict]:
    """Read player data from CSV file."""
    player_map = {}
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('name', '').strip()
            if not name:
                continue
            
            key = normalized_match_key(name)
            if not key:
                continue
            
            associations = set()
            assoc_str = row.get('associations', '').strip()
            if assoc_str:
                associations = set(a.strip() for a in assoc_str.split(',') if a.strip())
            
            if key not in player_map:
                player_map[key] = {
                    'name': name,
                    'associations': associations
                }
            else:
                player_map[key]['associations'].update(associations)
    
    return player_map


def create_fargo_accounts(
    player_map: Dict[str, Dict],
    db: Session,
    dry_run: bool = False
) -> Tuple[List[Dict], List[str]]:
    """
    Create user accounts for Fargo players.
    
    Args:
        player_map: Dict mapping normalized_key -> {name, associations}
        db: Database session
        dry_run: If True, don't actually create accounts
    
    Returns:
        Tuple of (created_users list, errors list)
    """
    created_users = []
    errors = []
    temp_passwords = {}  # user_id -> plaintext password (for CSV export)
    
    # Check if user_associations table exists
    try:
        db.execute(text("SELECT 1 FROM user_associations LIMIT 1"))
    except Exception:
        errors.append("user_associations table does not exist. Run migration 045 first.")
        return [], errors
    
    for key, player_info in sorted(player_map.items(), key=lambda x: x[1]['name']):
        try:
            name = player_info['name']
            associations = player_info['associations']
            
            if not name or not associations:
                continue
            
            # Check if user already exists (by username pattern or email)
            # We'll generate username and check
            potential_username = generate_unique_username(name, db)
            
            # Check if a user with this name already exists
            existing_user = db.query(User).filter_by(username=potential_username).first()
            if existing_user:
                # User already exists, just update associations
                user_id = existing_user.id
                print(f"User {potential_username} already exists, updating associations...")
            else:
                # Generate username
                username = potential_username
                
                # Generate password
                password = generate_password()
                password_hash = hash_password(password)
                
                # Create placeholder email (will be replaced when user sets their email)
                placeholder_email = f"pending_{username}@fargo.local"
                
                # Check if placeholder email already exists (shouldn't happen, but be safe)
                email_counter = 1
                while db.query(User).filter_by(email=placeholder_email).first():
                    placeholder_email = f"pending_{username}_{email_counter}@fargo.local"
                    email_counter += 1
                
                if dry_run:
                    print(f"[DRY RUN] Would create user: {username} for {name}")
                    created_users.append({
                        'username': username,
                        'password': password,
                        'name': name,
                        'associations': sorted(list(associations)),
                        'email': '',  # Empty, user will provide
                        'user_id': None
                    })
                    continue
                
                # Create user
                user = User(
                    username=username,
                    email=placeholder_email,
                    password_hash=password_hash,
                    nickname=None,  # Player will set their own nickname
                    role="user",
                    is_active=True,
                    email_verified=False,
                    requires_email_setup=True,
                    force_password_reset=False,
                )
                
                db.add(user)
                db.flush()  # Get the ID
                user_id = user.id
                
                # Store temp password for CSV export
                temp_passwords[user_id] = password
                
                print(f"Created user: {username} (ID: {user_id}) for {name}")
            
            # Create/update user_associations records
            if not dry_run:
                for assoc in associations:
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
                
                # Store temp password in a way we can retrieve it later
                # We'll use a simple approach: store in user_temp_passwords table
                # (created in migration or on first use)
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
                        "password": temp_passwords.get(user_id, '')
                    })
                except Exception as e:
                    # Table might not exist or other error - log but continue
                    print(f"Warning: Could not store temp password for user {user_id}: {e}")
            
            if not dry_run:
                created_users.append({
                    'username': username if 'username' in locals() else existing_user.username,
                    'password': temp_passwords.get(user_id, ''),
                    'name': name,
                    'associations': sorted(list(associations)),
                    'email': '',  # Empty, user will provide
                    'user_id': user_id
                })
            
        except Exception as e:
            error_msg = f"Error creating user for {player_info.get('name', 'Unknown')}: {str(e)}"
            errors.append(error_msg)
            print(f"ERROR: {error_msg}", file=sys.stderr)
    
    if not dry_run:
        try:
            db.commit()
            print(f"\nSuccessfully created/updated {len(created_users)} user accounts")
        except Exception as e:
            db.rollback()
            errors.append(f"Database commit error: {str(e)}")
            return [], errors
    
    return created_users, errors


def export_accounts_csv(users: List[Dict], output_file: str):
    """Export account data to CSV."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['username', 'password', 'name', 'email', 'associations']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        for user in users:
            writer.writerow({
                'username': user['username'],
                'password': user['password'],
                'name': user['name'],
                'email': user.get('email', ''),
                'associations': ', '.join(user['associations'])
            })
    
    print(f"Exported {len(users)} accounts to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Create user accounts for Fargo-rated players'
    )
    parser.add_argument(
        '--input',
        '-i',
        help='Input JSON or CSV file from extract_fargo_player_names.py (optional, will query DB if not provided)'
    )
    parser.add_argument(
        '--output',
        '-o',
        default='fargo_accounts.csv',
        help='Output CSV file with account credentials (default: fargo_accounts.csv)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run - show what would be created without actually creating accounts'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of accounts to create (for testing)'
    )
    
    args = parser.parse_args()
    
    # Get database connection
    db = next(get_db())
    
    try:
        # Load player data
        if args.input:
            if args.input.endswith('.json'):
                print(f"Reading player data from {args.input}...")
                player_map = read_fargo_players_json(args.input)
            elif args.input.endswith('.csv'):
                print(f"Reading player data from {args.input}...")
                player_map = read_fargo_players_csv(args.input)
            else:
                print(f"Error: Input file must be .json or .csv", file=sys.stderr)
                sys.exit(1)
        else:
            # Extract directly from database
            print("Extracting player data from database...")
            db_manager = get_database_manager()
            conn = db_manager.get_connection()
            try:
                # Import and use the extraction function
                import sys
                extract_script_path = os.path.join(os.path.dirname(__file__), "extract_fargo_player_names.py")
                if os.path.exists(extract_script_path):
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("extract_fargo_player_names", extract_script_path)
                    extract_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(extract_module)
                    player_map = extract_module.extract_fargo_players(conn)
                else:
                    print(f"Error: Could not find extract_fargo_player_names.py at {extract_script_path}", file=sys.stderr)
                    sys.exit(1)
            finally:
                conn.close()
        
        if args.limit:
            # Limit to first N players
            items = list(player_map.items())[:args.limit]
            player_map = dict(items)
            print(f"Limited to {len(player_map)} players for testing")
        
        print(f"Found {len(player_map)} unique players to process")
        
        # Create accounts
        created_users, errors = create_fargo_accounts(
            player_map,
            db,
            dry_run=args.dry_run
        )
        
        if errors:
            print(f"\nErrors encountered: {len(errors)}")
            for error in errors[:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more errors")
        
        # Export CSV
        if created_users:
            export_accounts_csv(created_users, args.output)
            print(f"\nDone! Created {len(created_users)} accounts.")
            if not args.dry_run:
                print(f"CSV exported to {args.output}")
        else:
            print("\nNo accounts created.")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    main()
