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
python3 "$ROOT/scripts/migrate-patch.py" --source "$ROOT/.build/mihomo" --patch "$ROOT/patches/mihomo-freebsd.patch" --baseline "$ROOT/patches/bases/core" --component core --version "$MIHOMO_VERSION" --output "$ROOT/.build/patch-update"
python3 "$ROOT/scripts/migrate-patch.py" --source "$ROOT/.build/sing-tun" --patch "$ROOT/patches/sing-tun-freebsd.patch" --baseline "$ROOT/patches/bases/sing-tun" --component sing-tun --version "$TUN_VERSION" --output "$ROOT/.build/patch-update"
cd ../mihomo
go mod edit -replace github.com/metacubex/sing-tun=../sing-tun
printf '%s\n' "$TUN_VERSION" > ../sing-tun-version
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  if [[ -f "$ROOT/.build/patch-update/migrated" ]]; then
    echo 'migrated=true' >> "$GITHUB_OUTPUT"
  else
    echo 'migrated=false' >> "$GITHUB_OUTPUT"
  fi
fi
