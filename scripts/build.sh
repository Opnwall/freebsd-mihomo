#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
source build.env
export GOOS=freebsd GOARCH=amd64 GOAMD64=v1 CGO_ENABLED=0
mkdir -p dist
cd .build/mihomo
go build -trimpath -tags "$BUILD_TAGS" -ldflags "-X github.com/metacubex/mihomo/constant.Version=${MIHOMO_VERSION}-freebsd -X github.com/metacubex/mihomo/constant.BuildTime=none -s -w -buildid=" -o "$ROOT/dist/clash-meta-freebsd-amd64" .
cd "$ROOT/dist"
xz -T0 -9 -k -f clash-meta-freebsd-amd64
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum clash-meta-freebsd-amd64.xz > SHA256SUMS
else
  shasum -a 256 clash-meta-freebsd-amd64.xz > SHA256SUMS
fi
{
  echo "mihomo: $MIHOMO_VERSION"
  echo "sing-tun: $(cat "$ROOT/.build/sing-tun-version")"
  echo "target: $GOOS/$GOARCH ($GOAMD64), CGO_ENABLED=$CGO_ENABLED"
  echo "tags: $BUILD_TAGS"
  go version
  go version -m clash-meta-freebsd-amd64
} > build-info.txt
