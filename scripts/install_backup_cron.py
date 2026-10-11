#!/usr/bin/env python3
"""
Install Cron Job for Automated Database Backups
Runs every 2 hours, keeps backups for 1 month
Usage: sudo python3 scripts/install_backup_cron.py
"""

import os
import subprocess
import sys
from pathlib import Path

def main():
    # Get project root
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    backup_script = project_root / "scripts" / "automated_backup_with_retention.sh"
    
    if not backup_script.exists():
        print(f"Error: Backup script not found: {backup_script}", file=sys.stderr)
        sys.exit(1)
    
    # Make script executable
    backup_script.chmod(0o755)
    
    # Cron job: Run every 2 hours
    cron_entry = f"0 */2 * * * {backup_script} >> {project_root}/logs/backup_cron.log 2>&1\n"
    
    # Check if cron job already exists
    try:
        result = subprocess.run(
            ['crontab', '-l'],
            capture_output=True,
            text=True,
            check=False
        )
        existing_crontab = result.stdout if result.returncode == 0 else ""
        
        if str(backup_script) in existing_crontab:
            print("✅ Backup cron job already installed")
            print(f"   Runs: Every 2 hours")
            print(f"   Retention: 30 days")
            print(f"   Script: {backup_script}")
            return
        
        # Add new cron job
        new_crontab = existing_crontab + cron_entry
        
        # Install crontab
        proc = subprocess.Popen(
            ['crontab', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate(input=new_crontab)
        
        if proc.returncode != 0:
            print(f"Error installing crontab: {stderr}", file=sys.stderr)
            sys.exit(1)
        
        print("✅ Backup cron job installed successfully!")
        print(f"   Schedule: Every 2 hours (0 */2 * * *)")
        print(f"   Script: {backup_script}")
        print(f"   Retention: 30 days")
        print(f"   Log: {project_root}/logs/backup_cron.log")
        print("")
        print("To view cron jobs: crontab -l")
        print("To remove: crontab -e (then delete the line)")
        print("")
        print("First backup will run at the next 2-hour mark (00:00, 02:00, 04:00, etc.)")
        print("Or run manually now: ./scripts/automated_backup_with_retention.sh")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if os.geteuid() == 0:
        print("Warning: Running as root will install cron for root user")
        print("Consider running as the service user (e.g., 'ansible' or 'www-data')")
        print("")
    main()
