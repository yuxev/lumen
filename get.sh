#!/usr/bin/env bash
# Install Lumen in one line (no git, no sudo), then open it:
#
#   curl -fsSL https://raw.githubusercontent.com/yuxev/lumen/main/get.sh | bash
#
# Run the same line again to update.
set -euo pipefail

REPO=yuxev/lumen
BRANCH=${LUMEN_BRANCH:-main}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

echo "Downloading Lumen…"
curl -fsSL "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH" | tar -xz -C "$tmp"
bash "$tmp"/lumen-*/install.sh

# open the window, detached from this terminal
(setsid "$HOME/.local/share/lumen/lumen" >/dev/null 2>&1 &)
echo "Opening Lumen. Next time, find it in your apps or run: lumen"
