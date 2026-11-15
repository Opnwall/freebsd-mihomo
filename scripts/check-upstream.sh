#!/usr/bin/env bash
set -euo pipefail
version=$(gh api repos/MetaCubeX/mihomo/releases/latest --jq '.tag_name')
[[ "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "Unexpected upstream stable release: $version" >&2
  exit 1
}
echo "version=${version#v}" >> "$GITHUB_OUTPUT"
build=true
if [[ "$GITHUB_EVENT_NAME" == schedule ]]; then
  # Only a successfully published binary counts; failed builds retry next hour.
  published=$(gh api --paginate "repos/$GITHUB_REPOSITORY/releases?per_page=100" --jq '.[] | select(.draft == false and .prerelease == false) | select(any(.assets[]; .name == "clash-meta-freebsd-amd64.xz" and .state == "uploaded")) | .tag_name')
  while IFS= read -r tag; do
    if [[ "$tag" == "${version}-freebsd-amd64-"* ]]; then
      build=false
      break
    fi
  done <<< "$published"
fi
echo "build=$build" >> "$GITHUB_OUTPUT"
echo "Upstream: $version; build: $build"
