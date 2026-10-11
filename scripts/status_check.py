#!/usr/bin/env python3
"""Comprehensive status check - writes to file for display"""
import os
import subprocess
import psycopg2
from datetime import datetime
from pathlib import Path

output = []
output.append("=" * 80)
output.append(f"RANKINGS BOT STATUS CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
output.append("=" * 80)
output.append("")

# 1. Check stops_played status
output.append("1. STOPS_PLAYED COLUMN STATUS")
output.append("-" * 80)
try:
    conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot"))
    cur = conn.cursor()
    
    cur.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END) as with_stops,
               ROUND(AVG(stops_played), 2) as avg_stops,
               MAX(stops_played) as max_stops
        FROM rankings
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
    """)
    total, with_stops, avg_stops, max_stops = cur.fetchone()
    
    output.append(f"   Total players: {total}")
    output.append(f"   With stops > 0: {with_stops} ({with_stops/total*100 if total > 0 else 0:.1f}%)")
    output.append(f"   Average stops: {avg_stops}")
    output.append(f"   Max stops: {max_stops}")
    
    if with_stops == 0:
        output.append("")
        output.append("   ⚠️  WARNING: No players have stops_played > 0")
        output.append("   Run: python3 scripts/update_stops_simple.py")
    else:
        output.append("")
        output.append("   ✓ Stops data populated")
    
    output.append("")
    output.append("   By ranking system:")
    cur.execute("""
        SELECT ranking_system, 
               COUNT(*) as total,
               SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END) as with_stops
        FROM rankings
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
        GROUP BY ranking_system
        ORDER BY ranking_system
    """)
    for system, sys_total, sys_with_stops in cur.fetchall():
        pct = sys_with_stops/sys_total*100 if sys_total > 0 else 0
        output.append(f"      {system:25} {sys_with_stops:4}/{sys_total:<4} ({pct:5.1f}%)")
    
    conn.close()
    
except Exception as e:
    output.append(f"   ❌ Error checking database: {e}")

output.append("")
output.append("")

# 2. Check backups
output.append("2. DATABASE BACKUPS")
output.append("-" * 80)
backup_dir = Path("/home/ansible/rankings-bot/backups")
if backup_dir.exists():
    dump_files = sorted(backup_dir.glob("rankings_*.dump"), key=lambda p: p.stat().st_mtime, reverse=True)
    sql_files = sorted(backup_dir.glob("rankings_*.sql"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    output.append(f"   Location: {backup_dir}")
    output.append(f"   .dump backups: {len(dump_files)}")
    output.append(f"   .sql backups: {len(sql_files)}")
    output.append("")
    
    if dump_files:
        output.append("   Recent .dump backups (last 10):")
        for f in dump_files[:10]:
            stat = f.stat()
            size_mb = stat.st_size / 1024 / 1024
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            output.append(f"      {f.name:40} {size_mb:7.2f} MB  {mtime}")
    
    if sql_files:
        output.append("")
        output.append("   SQL backups:")
        for f in sql_files:
            stat = f.stat()
            size_mb = stat.st_size / 1024 / 1024
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            output.append(f"      {f.name:40} {size_mb:7.2f} MB  {mtime}")
    
    # Total size
    total_size = sum(f.stat().st_size for f in backup_dir.glob("rankings_*.*")) / 1024 / 1024
    output.append("")
    output.append(f"   Total backup size: {total_size:.2f} MB")
    output.append("")
    output.append("   ℹ️  Automated backups run every 2 hours (configured in cron)")
else:
    output.append(f"   ⚠️  Backup directory not found: {backup_dir}")

output.append("")
output.append("")

# 3. Check Docker containers
output.append("3. DOCKER CONTAINERS")
output.append("-" * 80)
try:
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=rankings-bot", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
        capture_output=True, text=True, timeout=5
    )
    if result.returncode == 0 and result.stdout.strip():
        lines = result.stdout.strip().split('\n')
        output.append(f"   Running containers: {len(lines)}")
        for line in lines:
            parts = line.split('\t')
            if len(parts) >= 2:
                output.append(f"      {parts[0]:30} {parts[1]}")
    else:
        output.append("   No rankings-bot containers running")
except Exception as e:
    output.append(f"   Could not check Docker: {e}")

output.append("")
output.append("")

# 4. Check API health
output.append("4. API HEALTH")
output.append("-" * 80)
try:
    result = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:8003/health"],
        capture_output=True, text=True, timeout=5
    )
    status_code = result.stdout.strip()
    if status_code == "200":
        output.append("   ✓ API responding at http://localhost:8003/health")
    else:
        output.append(f"   ⚠️  API returned status {status_code}")
except Exception as e:
    output.append(f"   ❌ Could not reach API: {e}")

output.append("")
output.append("=" * 80)

# Write to file
result_text = "\n".join(output)
output_file = Path("/home/ansible/status_check.txt")
output_file.write_text(result_text)
print(result_text)
