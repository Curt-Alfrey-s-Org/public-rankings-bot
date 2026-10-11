#!/usr/bin/env bash
# Stop mobile app: Metro bundler (React Native).
#
# Usage: ./scripts/stop_mobile.sh

set -e

echo "Stopping mobile app (Metro)..."

pkill -f "react-native start" 2>/dev/null || true
pkill -f "metro" 2>/dev/null || true
pkill -f "node.*react-native" 2>/dev/null || true
# npm start in mobile runs "react-native start" - match the node process
pkill -f "node.*mobile.*metro" 2>/dev/null || true
pkill -f "node.*cli.js start" 2>/dev/null || true

# Metro often listens on 8081
pid=$(lsof -t -i ":8081" 2>/dev/null || true)
[ -n "$pid" ] && kill "$pid" 2>/dev/null || true

echo "✅ Mobile app stopped."
