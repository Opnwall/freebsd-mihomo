#!/bin/sh
set -eu
[ "$(uname -s)" = FreeBSD ]
[ "$(uname -m)" = amd64 ]
cd "$(dirname "$0")/.."
xz -dkf dist/clash-meta-freebsd-amd64.xz
chmod +x dist/clash-meta-freebsd-amd64
binary="$PWD/dist/clash-meta-freebsd-amd64"
"$binary" -v
pid=
cleanup() {
  if [ -n "$pid" ]; then
    kill -TERM "$pid" 2>/dev/null || true
    wait "$pid" || true
  fi
}
trap cleanup EXIT INT TERM
for stack in system gvisor mixed; do
  mkdir -p "dist/test-$stack"
  cat > "dist/test-$stack/config.yaml" <<EOF
mode: direct
log-level: debug
ipv6: false
find-process-mode: off
dns:
  enable: false
tun:
  enable: true
  device: tun9
  stack: $stack
  mtu: 1500
  inet4-address: [172.19.0.1/30]
  dns-mode: disabled
  auto-route: false
  auto-detect-interface: false
rules:
  - MATCH,DIRECT
EOF
  "$binary" -t -d "$PWD/dist/test-$stack"
  "$binary" -d "$PWD/dist/test-$stack" > "dist/smoke-$stack.log" 2>&1 &
  pid=$!
  sleep 3
  if ! kill -0 "$pid" 2>/dev/null; then
    cat "dist/smoke-$stack.log"
    exit 1
  fi
  if ! ifconfig tun9; then
    cat "dist/smoke-$stack.log"
    exit 1
  fi
  if grep -Eiq 'level=(error|fatal)|panic:' "dist/smoke-$stack.log"; then
    cat "dist/smoke-$stack.log"
    exit 1
  fi
  kill -TERM "$pid"
  wait "$pid"
  pid=
  if ifconfig tun9 >/dev/null 2>&1; then
    echo "TUN device was not cleaned up for $stack" >&2
    exit 1
  fi
  echo "TUN $stack startup and cleanup passed"
done
