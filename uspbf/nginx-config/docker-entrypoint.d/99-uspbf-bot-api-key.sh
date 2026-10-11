#!/bin/sh
# Generate nginx snippet so X-API-Key is never exposed to the browser (server-side only).
# Runs before nginx starts (official nginx image docker-entrypoint.d).
#
# BOT_API_KEY is required: the static-site /api/ proxy (example.com, www, LAN :8089) injects it
# for the allowlisted public endpoints. Fail fast with a clear error instead of silently
# proxying with an empty key. The value is substituted into a quoted nginx directive, so it is
# restricted to characters that cannot break out of the string or be read as nginx variables.
#
# Paths can be overridden for tests (tests/nginx/run.sh); production uses the defaults.
set -eu
TEMPLATE="${USPBF_BOT_API_KEY_TEMPLATE:-/etc/nginx/bot-api-key-headers.conf.template}"
SNIP="${USPBF_BOT_API_KEY_SNIPPET:-/etc/nginx/snippets/bot-api-key-headers.conf}"

if [ ! -f "$TEMPLATE" ]; then
  echo "USPBF nginx: missing $TEMPLATE" >&2
  exit 1
fi

BOT_API_KEY="${BOT_API_KEY:-}"
if [ -z "$BOT_API_KEY" ]; then
  echo "USPBF nginx: BOT_API_KEY is not set. Set it in .env (same value as rankings-bot-api BOT_API_KEY); see env.example." >&2
  exit 1
fi

case "$BOT_API_KEY" in
  *[!A-Za-z0-9._~+/=-]*)
    echo "USPBF nginx: BOT_API_KEY contains unsupported characters. Use only A-Z a-z 0-9 . _ ~ + / = - (e.g. openssl rand -hex 32)." >&2
    exit 1
    ;;
esac

export BOT_API_KEY
mkdir -p "$(dirname "$SNIP")"
umask 077
envsubst '${BOT_API_KEY}' < "$TEMPLATE" > "$SNIP"
