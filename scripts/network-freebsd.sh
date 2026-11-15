#!/bin/sh
# Sourced by smoke-freebsd.sh inside a disposable FreeBSD VM.
fixture_pid=
capture_pid=
jail_name=tun_fixture
fixture_interface=
fixture_created=false
network_setup() {
  mkdir -p dist/network
  sysctl net.fibs=2
  sysctl net.add_addr_allfibs=1
  fixture_interface=$(ifconfig epair create)
  fixture_peer="${fixture_interface%a}b"
  jail -c name="$jail_name" persist vnet path=/ host.hostname=tun-fixture
  fixture_created=true
  ifconfig "$fixture_peer" vnet "$jail_name"
  ifconfig "$fixture_interface" inet 192.0.2.1/30 up
  ifconfig "$fixture_interface" inet6 fd00:198:18::1/126 -ifdisabled -accept_rtadv
  jexec "$jail_name" ifconfig lo0 inet 127.0.0.1/8 up
  jexec "$jail_name" ifconfig "$fixture_peer" inet 192.0.2.2/30 up
  jexec "$jail_name" ifconfig "$fixture_peer" inet6 fd00:198:18::2/126 -ifdisabled -accept_rtadv
  sleep 2
  jexec "$jail_name" python3 "$PWD/scripts/tun-traffic.py" serve > dist/network/server.log 2>&1 &
  fixture_pid=$!
  sleep 1
  kill -0 "$fixture_pid"
  grep -q 'fixture ready' dist/network/server.log
  # Establish that the isolated server works without the TUN before testing it.
  setfib 0 python3 scripts/tun-traffic.py client --report dist/network/direct-baseline.json
}
network_routes() {
  setfib 1 route add -host 192.0.2.2 -iface tun9
  setfib 1 route add -inet6 -host fd00:198:18::2 -iface tun9
  setfib 1 route -n get 192.0.2.2 | tee "dist/network/$stack-route-ipv4.txt"
  setfib 1 route -n get -inet6 fd00:198:18::2 | tee "dist/network/$stack-route-ipv6.txt"
  grep -q 'interface: tun9' "dist/network/$stack-route-ipv4.txt"
  grep -q 'interface: tun9' "dist/network/$stack-route-ipv6.txt"
  setfib 0 route -n get 192.0.2.2 | grep -q "interface: $fixture_interface"
}
network_check() {
  network_routes
  # With the same route and a live TUN device, no echo may complete while stopped.
  kill -STOP "$pid"
  setfib 1 python3 scripts/tun-traffic.py blocked
  kill -CONT "$pid"
  tcpdump --immediate-mode -B 4096 -n -U -i tun9 -w "$PWD/dist/network/$stack.pcap" > "dist/network/$stack-tcpdump.log" 2>&1 &
  capture_pid=$!
  sleep 1
  kill -0 "$capture_pid"
  setfib 1 python3 scripts/tun-traffic.py client --report "dist/network/$stack-results.json"
  sleep 1
  kill -INT "$capture_pid"
  wait "$capture_pid"
  capture_pid=
  for protocol in tcp udp; do
    for host in 192.0.2.2 fd00:198:18::2; do
      for direction in src dst; do
        count=$(tcpdump -n -r "dist/network/$stack.pcap" "$protocol and $direction host $host and port 18080" 2>/dev/null | wc -l | tr -d ' ')
        test "$count" -gt 0 || {
          echo "No TUN packets: $stack $protocol $direction $host" >&2
          return 1
        }
      done
    done
  done
  echo "TUN $stack IPv4/IPv6 TCP/UDP forwarding, payload integrity and negative controls passed"
}
network_cleanup() {
  netstat -rn > dist/network/final-routes.txt 2>&1 || true
  netstat -s -p tcp > dist/network/tcp-stats.txt 2>&1 || true
  netstat -s -p ip > dist/network/ip-stats.txt 2>&1 || true
  sockstat -46 > dist/network/sockets.txt 2>&1 || true
  if [ -n "$capture_pid" ]; then
    kill -INT "$capture_pid" 2>/dev/null || true
    wait "$capture_pid" || true
    tcpdump -n -vv -r "dist/network/$stack.pcap" > "dist/network/$stack-packets.txt" 2>&1 || true
    head -80 "dist/network/$stack-packets.txt" || true
  fi
  if [ -n "$fixture_pid" ]; then
    kill -TERM "$fixture_pid" 2>/dev/null || true
    wait "$fixture_pid" || true
  fi
  if [ "$fixture_created" = true ]; then jail -r "$jail_name" || true; fi
  if [ -n "$fixture_interface" ]; then ifconfig "$fixture_interface" destroy || true; fi
}
