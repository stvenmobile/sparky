import socket
import time
import math
import json

UDP_IP = "127.0.0.1"
UDP_PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
print("Sparky is talking... (Ctrl+C to stop)")

try:
    t = 0
    while True:
        # Create a sine wave 0.0 to 1.0
        val = (math.sin(t) + 1) / 2
        sock.sendto(json.dumps({"mouth": val}).encode(), (UDP_IP, UDP_PORT))
        time.sleep(0.05)
        t += 0.5
except KeyboardInterrupt:
    sock.sendto(json.dumps({"mouth": 0.0}).encode(), (UDP_IP, UDP_PORT))