#!/usr/bin/env bash
# Drop a sample RFC822 message into the Maildir and notify Dovecot.
set -euo pipefail

MAILDIR="$(cd "$(dirname "$0")/.." && pwd)/maildir"
NEW_DIR="$MAILDIR/new"

mkdir -p "$NEW_DIR"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DATE_RFC2822=$(date -R)
UNIQUE="${TIMESTAMP//[^0-9]/}.$$"
FILENAME="$NEW_DIR/${UNIQUE}.voiceinbox"

cat > "$FILENAME" <<EOF
Date: $DATE_RFC2822
From: voiceinbox@localhost
To: user@localhost
Subject: Voice note $TIMESTAMP
Message-ID: <sample-$UNIQUE@voiceinbox.local>
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8

This is a sample message created by create_sample_message.sh at $TIMESTAMP.
EOF

echo "Created: $FILENAME"

# Tell Dovecot to pick up new messages in the maildir.
# doveadm runs inside the container; fall back silently if Docker isn't up.
if docker compose ps dovecot 2>/dev/null | grep -q "running"; then
  docker compose exec dovecot doveadm force-resync -u voiceinbox INBOX
  echo "Dovecot notified."
else
  echo "Dovecot container not running — start it with: docker compose up -d"
fi
