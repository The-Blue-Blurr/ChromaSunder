#!/usr/bin/env bash
set -euo pipefail

BUILD_DIR="${1:-build-dir}"
REPO_DIR="${2:-repo}"
flatpak-builder --force-clean --disable-rofiles-fuse --repo="$REPO_DIR" "$BUILD_DIR" \
  flatpak/io.github.the_blue_blurr.ChromaSunder.yml

