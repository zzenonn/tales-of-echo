#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/discord-fetch.env"
OUTPUT_DIR="${SCRIPT_DIR}/threads"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: $ENV_FILE not found. Copy discord-fetch.env.example and fill in your values." >&2
    exit 1
fi
source "$ENV_FILE"

if [[ -z "${DISCORD_TOKEN:-}" ]]; then
    echo "Error: DISCORD_TOKEN not set in $ENV_FILE" >&2
    exit 1
fi

usage() {
    echo "Usage: $0 <thread_id> [output_name]"
    echo ""
    echo "  thread_id    - Discord thread/channel ID"
    echo "  output_name  - Optional filename (default: thread_id)"
    echo ""
    echo "Examples:"
    echo "  $0 1495958495789584414"
    echo "  $0 1495958495789584414 session-12-recap"
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi

THREAD_ID="$1"
OUTPUT_NAME="${2:-$THREAD_ID}"

mkdir -p "$OUTPUT_DIR"

fetch_messages() {
    local params="limit=50"
    if [[ -n "${1:-}" ]]; then
        params+="&before=$1"
    fi

    curl -s "https://discord.com/api/v9/channels/${THREAD_ID}/messages?${params}" \
        --compressed \
        -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0' \
        -H 'Accept: */*' \
        -H 'Accept-Language: en-US,en;q=0.9' \
        -H 'Accept-Encoding: gzip, deflate, br, zstd' \
        -H "Authorization: ${DISCORD_TOKEN}" \
        -H "X-Super-Properties: ${DISCORD_SUPER_PROPERTIES:-}" \
        -H 'X-Discord-Locale: en-US' \
        -H 'X-Discord-Timezone: Asia/Manila' \
        -H 'DNT: 1' \
        -H 'Connection: keep-alive' \
        -H "Cookie: ${DISCORD_COOKIE:-}" \
        -H 'Sec-Fetch-Dest: empty' \
        -H 'Sec-Fetch-Mode: cors' \
        -H 'Sec-Fetch-Site: same-origin'
}

echo "Fetching thread ${THREAD_ID}..."

ALL_MESSAGES="[]"
BEFORE_ID=""
PAGE=0

while true; do
    PAGE=$((PAGE + 1))
    echo "  Page ${PAGE}..." >&2

    BATCH=$(fetch_messages "$BEFORE_ID")

    # Check for errors
    if echo "$BATCH" | jq -e '.message' &>/dev/null; then
        echo "API error: $(echo "$BATCH" | jq -r '.message')" >&2
        if [[ "$PAGE" -eq 1 ]]; then
            exit 1
        fi
        break
    fi

    COUNT=$(echo "$BATCH" | jq 'length')

    if [[ "$COUNT" -eq 0 ]]; then
        break
    fi

    # Append batch to all messages
    ALL_MESSAGES=$(jq -s '.[0] + .[1]' <(echo "$ALL_MESSAGES") <(echo "$BATCH"))

    echo "  Got ${COUNT} messages (total: $(echo "$ALL_MESSAGES" | jq 'length'))" >&2

    if [[ "$COUNT" -lt 50 ]]; then
        break
    fi

    # Get the oldest message ID in this batch for pagination
    BEFORE_ID=$(echo "$BATCH" | jq -r '.[-1].id')

    # Rate limit: Discord allows ~5 requests/sec for user accounts
    sleep 1
done

TOTAL=$(echo "$ALL_MESSAGES" | jq 'length')

# Sort messages oldest-first and write
echo "$ALL_MESSAGES" | jq 'sort_by(.timestamp)' > "${OUTPUT_DIR}/${OUTPUT_NAME}.json"

echo "Done. ${TOTAL} messages saved to ${OUTPUT_DIR}/${OUTPUT_NAME}.json"
