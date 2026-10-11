#!/usr/bin/env bash
# Download official WPA and WPBA rule PDFs into docs/rules/.
# URLs scraped from wpapool.com/rules/ and wpba.com (update if links change).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WPA_DIR="$ROOT/docs/rules/wpa"
WPBA_DIR="$ROOT/docs/rules/wpba"
HTTP_FETCH_SH="${HTTP_FETCH_SH:-$ROOT/../alfa-ai/scripts/lib/http_fetch.sh}"

mkdir -p "$WPA_DIR" "$WPBA_DIR"

if [[ -f "$HTTP_FETCH_SH" ]]; then
  # shellcheck source=/dev/null
  source "$HTTP_FETCH_SH"
fi

download() {
  local url="$1"
  local dest="$2"
  echo "Downloading: $dest"
  if command -v http_fetch_to >/dev/null 2>&1; then
    http_fetch_to "$url" "$dest"
  else
    curl -fsSL --max-time 120 -o "$dest" "$url"
  fi
}

# WPA — source: https://wpapool.com/rules/ (verify periodically)
download "https://wpapool.com/wp-content/uploads/2026/01/2026.01.02-WPA-Rules.pdf" \
  "$WPA_DIR/2026.01.02-WPA-Rules.pdf"
download "https://wpapool.com/wp-content/uploads/2025/10/2025.09.15-WPA-Regs-NP.pdf" \
  "$WPA_DIR/2025.09.15-WPA-Regs-NP.pdf"
download "https://wpapool.com/wp-content/uploads/2024/01/2022-WPA-Sports-Regulations-v2-1.pdf" \
  "$WPA_DIR/2022-WPA-Sports-Regulations-v2-1.pdf"
download "https://wpapool.com/wp-content/uploads/2025/04/2025.02.12-WPA-Sanctioning-Regulations.pdf" \
  "$WPA_DIR/2025.02.12-WPA-Sanctioning-Regulations.pdf"
download "https://wpapool.com/wp-content/uploads/2024/01/RECOMMENDED-EQUIPMENT-SPECIFICATIONS.pdf" \
  "$WPA_DIR/RECOMMENDED-EQUIPMENT-SPECIFICATIONS.pdf"
download "https://wpapool.com/wp-content/uploads/2025/07/2025.07.19-Pyramid-Rules.pdf" \
  "$WPA_DIR/2025.07.19-Pyramid-Rules.pdf"
download "https://wpapool.com/wp-content/uploads/2025/08/250816-Rules-of-Heyball.pdf" \
  "$WPA_DIR/250816-Rules-of-Heyball.pdf"
download "https://wpapool.com/wp-content/uploads/2025/07/APD-Guidelines-FINAL-3_5_25-W_WPA-Update-Notes.pdf" \
  "$WPA_DIR/APD-Guidelines-FINAL-WPA-Update-Notes.pdf"
download "https://wpapool.com/wp-content/uploads/2025/07/International_8_Ball_Rules_1a_Feb2021_38fb4d6d68.pdf" \
  "$WPA_DIR/International_8_Ball_Rules_Feb2021.pdf"

# WPBA — same sources as rankings-bot frontend Rules.tsx
download "https://wpba.com/s/WPBA-9-Ball-Rules-Rev-51625.pdf" \
  "$WPBA_DIR/WPBA-9-Ball-Rules-Rev-51625.pdf"
download "https://wpba.com/s/WPBA-Point-System-rev-12326jpg.png" \
  "$WPBA_DIR/WPBA-Point-System-rev-12326.png"

echo "Done. WPA: $WPA_DIR  WPBA: $WPBA_DIR"
