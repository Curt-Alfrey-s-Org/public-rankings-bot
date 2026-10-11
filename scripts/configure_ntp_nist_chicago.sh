#!/bin/bash
# Configure server time: NIST time servers + America/Chicago timezone.
# Run with sudo. Use for Rankings Bot server when clock shows wrong time.
#
# Usage:
#   sudo ./scripts/configure_ntp_nist_chicago.sh
#
# After running:
#   timedatectl status          # Verify timezone and NTP sync
#   timedatectl timesync-status # Show sync details

set -e

echo "[1/4] Setting timezone to America/Chicago (Central)..."
timedatectl set-timezone America/Chicago

echo "[2/4] Configuring NTP to use NIST time servers..."
mkdir -p /etc/systemd/timesyncd.conf.d
cat > /etc/systemd/timesyncd.conf.d/nist-chicago.conf << 'EOF'
# NIST time servers (authoritative US time)
# America/Chicago = Central Time (CST/CDT)
[Time]
NTP=time.nist.gov time-a.nist.gov time-b.nist.gov
FallbackNTP=pool.ntp.org
EOF

echo "[3/4] Enabling NTP synchronization..."
timedatectl set-ntp true

echo "[4/4] Restarting systemd-timesyncd..."
systemctl restart systemd-timesyncd 2>/dev/null || true

echo ""
echo "Done. Verifying..."
timedatectl status
echo ""
echo "For API process: set TZ=America/Chicago in .env or systemd Environment."
echo "Example (systemd): Environment=\"TZ=America/Chicago\""
