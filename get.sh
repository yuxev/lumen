#!/usr/bin/env bash
# Install Nimbus in one line (no git, no sudo), then open it:
#
#   curl -fsSL https://raw.githubusercontent.com/yuxev/nimbus/main/get.sh | bash
#
# Run the same line again to update.
set -euo pipefail

REPO=yuxev/nimbus
BRANCH=${NIMBUS_BRANCH:-main}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

echo "Downloading Nimbus…"
curl -fsSL "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH" | tar -xz -C "$tmp"
bash "$tmp"/nimbus-*/install.sh

# open the window, detached from this terminal
(setsid "$HOME/.local/share/nimbus/nimbus" >/dev/null 2>&1 &)
echo "Opening Nimbus. Next time, find it in your apps or run: nimbus"
