#!/bin/bash
# Reset super admin password to rtRT

cd /home/ansible/rankings-bot/Rankings-Bot
source .env

# Python one-liner to hash the password
HASHED_PW=$(python3 -c "
import sys
sys.path.insert(0, '/home/ansible/rankings-bot/Rankings-Bot')
from api.auth import hash_password
print(hash_password('rtRT'))
")

# Update the database
psql "$DATABASE_URL" <<SQL
UPDATE users 
SET password_hash = '$HASHED_PW',
    failed_login_attempts = 0,
    account_locked_until = NULL
WHERE username = 'tornybotca1';

SELECT 'Password reset complete for: ' || username || ' (role: ' || role || ')'
FROM users 
WHERE username = 'tornybotca1';
SQL

echo "Done. You can now login with:"
echo "  Username: tornybotca1"
echo "  Password: rtRT"
