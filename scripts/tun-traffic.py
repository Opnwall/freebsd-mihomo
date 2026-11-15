#!/usr/bin/env python3
"""Local TCP/UDP echo fixture and integrity-checked TUN client; no Internet endpoints."""
import argparse
import hashlib
import json
import os
import socket
import socketserver
import struct
import threading
import time

PORT = 18080


def receive(sock, size):
    chunks = bytearray()
    while len(chunks) < size:
        block = sock.recv(size - len(chunks))
        if not block:
            raise OSError('Truncated TCP response')
        chunks.extend(block)
    return bytes(chunks)


class TCP(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        try:
            length = struct.unpack('!I', receive(self.request, 4))[0]
            if not 0 < length <= 1048576:
                raise ValueError('Invalid frame size')
            payload = receive(self.request, length)
            self.request.sendall(payload)
            print(json.dumps({'protocol': 'tcp', 'peer': self.client_address[0], 'bytes': length, 'sha256': hashlib.sha256(payload).hexdigest()}), flush=True)
        except (OSError, ValueError):
            pass  # Negative controls deliberately time out and close their sockets.


class UDP(socketserver.BaseRequestHandler):
    def handle(self):
        payload, sock = self.request
        sock.sendto(payload, self.client_address)
        print(json.dumps({'protocol': 'udp', 'peer': self.client_address[0], 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}), flush=True)


def serve():
    servers = []
    for family, address in [(socket.AF_INET, '0.0.0.0'), (socket.AF_INET6, '::')]:
        for base, handler in [(socketserver.ThreadingTCPServer, TCP), (socketserver.ThreadingUDPServer, UDP)]:
            class Server(base):
                address_family = family
                allow_reuse_address = True
                daemon_threads = True

                def server_bind(self):
                    if self.address_family == socket.AF_INET6:
                        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                    super().server_bind()
            server = Server((address, PORT), handler)
            servers.append(server)
            threading.Thread(target=server.serve_forever, daemon=True).start()
    print('TCP/UDP IPv4/IPv6 fixture ready', flush=True)
    threading.Event().wait()


def exchange(family, host, source, protocol, size, timeout):
    payload = os.urandom(size)
    kind = socket.SOCK_STREAM if protocol == 'tcp' else socket.SOCK_DGRAM
    with socket.socket(family, kind) as sock:
        sock.settimeout(timeout)
        sock.bind((source, 0))
        sock.connect((host, PORT))
        if protocol == 'tcp':
            sock.sendall(struct.pack('!I', size) + payload)
            response = receive(sock, size)
        else:
            sock.send(payload)
            response = sock.recv(65535)
    if response != payload:
        raise ValueError('Forwarded payload differs from the original')
    result = {'family': 'ipv4' if family == socket.AF_INET else 'ipv6', 'protocol': protocol, 'bytes': size, 'sha256': hashlib.sha256(payload).hexdigest()}
    print(json.dumps(result), flush=True)
    return result


def client(blocked, report):
    results = []
    for family, host, source in [(socket.AF_INET, '192.0.2.2', '192.0.2.1'), (socket.AF_INET6, 'fd00:198:18::2', 'fd00:198:18::1')]:
        for protocol in ['tcp', 'udp']:
            sizes = [64] if blocked else ([262144] if protocol == 'tcp' else [64, 1200, 4096])
            for size in sizes:
                if blocked:
                    try:
                        exchange(family, host, source, protocol, size, 0.7)
                    except OSError:
                        print(f'Negative control blocked {family}/{protocol}', flush=True)
                    else:
                        raise RuntimeError('Traffic bypassed the stopped TUN proxy')
                else:
                    results.append(exchange(family, host, source, protocol, size, 8))
    if report:
        with open(report, 'w') as output:
            json.dump({'passed': True, 'negative_control': blocked, 'checks': results}, output, indent=2)
            output.write('\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['serve', 'client', 'blocked'])
    parser.add_argument('--report')
    args = parser.parse_args()
    if args.mode == 'serve':
        serve()
    else:
        client(args.mode == 'blocked', args.report)
