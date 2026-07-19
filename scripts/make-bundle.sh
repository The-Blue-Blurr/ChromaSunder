#!/usr/bin/env bash
set -euo pipefail

: "${VERSION:?Set VERSION, for example VERSION=v1.0.0}"
flatpak build-bundle repo "ChromaSunder-${VERSION}.flatpak" io.github.the_blue_blurr.ChromaSunder stable \
  --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
sha256sum "ChromaSunder-${VERSION}.flatpak" > "ChromaSunder-${VERSION}.flatpak.sha256"
