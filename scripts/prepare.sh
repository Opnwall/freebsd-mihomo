#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
source build.env
[[ "$MIHOMO_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
mkdir -p .build
if [[ -e .build/mihomo || -e .build/sing-tun ]]; then
  echo 'Sources already exist; remove .build before preparing again.' >&2
  exit 1
fi
curl --fail --location --retry 3 "https://github.com/MetaCubeX/mihomo/archive/refs/tags/v${MIHOMO_VERSION}.tar.gz" -o .build/mihomo.tar.gz
tar -xzf .build/mihomo.tar.gz -C .build
mv ".build/mihomo-${MIHOMO_VERSION}" .build/mihomo
cd .build/mihomo
# Resolve the exact go.mod dependency, including pseudo-versions, through Go.
TUN_VERSION=$(go mod edit -json | jq -er '.Require[] | select(.Path == "github.com/metacubex/sing-tun") | .Version')
TUN_DIR=$(go mod download -json "github.com/metacubex/sing-tun@${TUN_VERSION}" | jq -er '.Dir')
cp -R "$TUN_DIR" ../sing-tun
chmod -R u+w ../sing-tun
patch --batch --fuzz=0 -p1 < "$ROOT/patches/mihomo-freebsd.patch"
cd ../sing-tun
patch --batch --fuzz=0 -p1 < "$ROOT/patches/sing-tun-freebsd.patch"
cd ../mihomo
go mod edit -replace github.com/metacubex/sing-tun=../sing-tun
printf '%s\n' "$TUN_VERSION" > ../sing-tun-version
