#!/usr/bin/env bash
set -euo pipefail

: "${GPG_KEY_ID:?Set GPG_KEY_ID to the dedicated Flatpak signing key}"
: "${PAGES_REPOSITORY:?Set PAGES_REPOSITORY to the checked-out Pages repository path}"

test -d repo
mkdir -p "$PAGES_REPOSITORY/repo"
flatpak build-update-repo --generate-static-deltas --gpg-sign="$GPG_KEY_ID" repo
cp -a repo/. "$PAGES_REPOSITORY/repo/"
cp flatpak/ChromaSunder.flatpakrepo flatpak/ChromaSunder.flatpakref "$PAGES_REPOSITORY/"
echo "Signed repository staged in $PAGES_REPOSITORY. Commit and publish it through the protected Pages workflow."
