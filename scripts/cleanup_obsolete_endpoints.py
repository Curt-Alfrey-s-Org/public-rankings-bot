#!/usr/bin/env python3
"""
Cleanup script for obsolete API endpoints.
Removes endpoint registrations from route files that are not used anywhere.
"""

import os
import re
from pathlib import Path

# Obsolete endpoints to remove (from analysis)
obsolete_endpoints = {
    # Admin endpoints
    '/api/admin/cache/refresh',
    '/api/admin/cache/status',
    '/api/admin/login-attempts',
    '/api/admin/security-metrics',
    '/api/admin/security/ip-blocks',
    '/api/admin/start-all',
    '/api/admin/stop-all',

    # Payments
    '/api/payments/cancel/{intent_id}',
    '/api/payments/status/{intent_id}',

    # Player performance (full suite unused)
    '/api/player-performance/me',
    '/api/player-performance/{player_name}/history',
    '/api/player-performance/{player_name}/overview',
    '/api/player-performance/{player_name}/performance-metrics',
    '/api/player-performance/{player_name}/tournaments',

    # Tournament history (full suite unused)
    '/api/tournament-history/search',
    '/api/tournament-history/statistics',
    '/api/tournament-history/tournaments',
    '/api/tournament-history/upcoming',
    '/api/tournament-history/years',

    # User management (unused admin features)
    '/api/users/player-links',
    '/api/users/{username}',
    '/api/users/{username}/reset-password',
    '/api/users/{username}/set-password',

    # V1 mobile endpoints (not used by mobile app)
    '/api/v1/auth/me',
    '/api/v1/health',
    '/api/v1/config',
    '/api/v1/rankings/',
    '/api/v1/rankings/last-update',
    '/api/v1/rankings/player/{player_name}',
    '/api/v1/rankings/refresh',
    '/api/v1/rankings/wpa',
    '/api/v1/rankings/wpba',
    '/api/v1/system',
    '/api/v1/system/health'
}

def cleanup_route_file(filepath: Path, endpoints_to_remove: set):
    """Remove obsolete endpoint definitions from a route file."""
    content = filepath.read_text()
    original_content = content

    # Find and remove endpoint definitions
    lines = content.split('\n')
    new_lines = []
    skip_until_next_endpoint = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this line defines an obsolete endpoint
        if '@router.' in line and any('"' + endpoint.split('/')[-1] + '"' in line for endpoint in endpoints_to_remove):
            # Find the complete endpoint definition (decorator + function)
            endpoint_start = i
            # Skip the decorator line
            i += 1
            # Skip until we find the next endpoint or end of function
            while i < len(lines) and not lines[i].strip().startswith('@router.'):
                i += 1
            print(f"  Removed endpoint definition at line {endpoint_start+1}")
            continue

        new_lines.append(line)
        i += 1

    new_content = '\n'.join(new_lines)

    if new_content != original_content:
        filepath.write_text(new_content)
        return True
    return False

def main():
    """Main cleanup function."""
    print("🧹 CLEANUP OBSOLETE ENDPOINTS")
    print("=" * 50)

    routes_dir = Path("/home/ansible/rankings-bot/api/routes")
    files_modified = []

    for route_file in routes_dir.glob("*.py"):
        if route_file.name == "__init__.py":
            continue

        print(f"\n📁 Processing {route_file.name}...")

        if cleanup_route_file(route_file, obsolete_endpoints):
            files_modified.append(route_file.name)
            print(f"  ✅ Modified {route_file.name}")
        else:
            print(f"  ℹ️  No changes needed in {route_file.name}")

    print(f"\n📊 SUMMARY:")
    print(f"  Files modified: {len(files_modified)}")
    print(f"  Endpoints targeted for removal: {len(obsolete_endpoints)}")

    if files_modified:
        print("\n⚠️  IMPORTANT: After running this script:")
        print("  1. Test that the API still starts without errors")
        print("  2. Verify that no active features were accidentally removed")
        print("  3. Update any documentation that references removed endpoints")
    else:
        print("\n✅ No modifications were needed.")

if __name__ == "__main__":
    main()