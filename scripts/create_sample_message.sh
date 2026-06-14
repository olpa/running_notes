#!/usr/bin/env bash
# Drop a sample RFC822 message into the Maildir via docker cp and notify Dovecot.
set -euo pipefail

# Support both docker compose (V2) and docker-compose (V1).
COMPOSE="docker compose"
if ! docker compose version &>/dev/null; then
  COMPOSE="docker-compose"
fi

CONTAINER=$($COMPOSE ps -q dovecot 2>/dev/null)
if [ -z "$CONTAINER" ]; then
  echo "Dovecot container not running — start it with: $COMPOSE up -d"
  exit 1
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DATE_RFC2822=$(date -R)
UNIQUE="${TIMESTAMP//[^0-9]/}.$$"
TMPFILE=$(mktemp)

cat > "$TMPFILE" <<EOF
Date: $DATE_RFC2822
From: voiceinbox@localhost
To: user@localhost
Subject: Voice note $TIMESTAMP
Message-ID: <sample-$UNIQUE@voiceinbox.local>
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8

This is a sample message created by create_sample_message.sh at $TIMESTAMP.
EOF

docker cp "$TMPFILE" "$CONTAINER:/var/mail/voiceinbox/new/${UNIQUE}.voiceinbox"
rm "$TMPFILE"

echo "Copied message to container."

docker exec "$CONTAINER" doveadm force-resync -u voiceinbox INBOX
echo "Dovecot notified."
