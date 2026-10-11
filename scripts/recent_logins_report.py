#!/usr/bin/env python3
"""
Write last N successful logins (IP, username, timestamp) to a file on the server.
IPs are not exposed in the admin UI for security; use this script on the server instead.

Output: /home/ansible/recent_logins.txt (or RECENT_LOGINS_FILE env)

  cd /path/to/Rankings-Bot
  source .env 2>/dev/null || true
  python3 scripts/recent_logins_report.py

  # Custom output file:
  RECENT_LOGINS_FILE=/tmp/logins.txt python3 scripts/recent_logins_report.py

  # More entries:
  RECENT_LOGINS_LIMIT=50 python3 scripts/recent_logins_report.py
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

# Load .env
env_path = os.path.join(PROJECT_ROOT, ".env")
if os.path.isfile(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip("'\"")
                os.environ.setdefault(k, v)

# When run on host, Docker hostname "postgres" does not resolve
import re
url = os.environ.get("DATABASE_URL", "")
if url and "postgres" in url:
    url = re.sub(r"@postgres([:/])", r"@127.0.0.1\1", url)
    os.environ["DATABASE_URL"] = url

OUTPUT_FILE = os.environ.get("RECENT_LOGINS_FILE", "/home/ansible/recent_logins.txt")
LIMIT = int(os.environ.get("RECENT_LOGINS_LIMIT", "10"))


def main():
    from database import get_db_context
    from api.models.audit import AuditLog
    from api.models.user import User

    with get_db_context() as db:
        rows = (
            db.query(AuditLog, User.username)
            .join(User, AuditLog.user_id == User.id)
            .filter(AuditLog.event_type == "login", AuditLog.success == True)
            .order_by(AuditLog.timestamp.desc())
            .limit(LIMIT)
            .all()
        )

    lines = [
        "# Last {} successful logins (IP, username, timestamp)".format(LIMIT),
        "# Run: python3 scripts/recent_logins_report.py",
        "",
        "{:<45} {:<24} {}".format("IP", "Username", "Timestamp"),
        "-" * 90,
    ]
    for a, u in rows:
        ip = a.ip_address or "—"
        ts = a.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if a.timestamp else "—"
        lines.append("{:<45} {:<24} {}".format(ip[:44], (u or "")[:23], ts))

    try:
        with open(OUTPUT_FILE, "w") as f:
            f.write("\n".join(lines) + "\n")
        print("Wrote {} entries to {}".format(len(rows), OUTPUT_FILE))
    except OSError as e:
        print("Failed to write {}: {}".format(OUTPUT_FILE, e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
