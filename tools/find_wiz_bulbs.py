"""Find WiZ bulbs on your home network, and check this computer can talk to them.

It only *asks* the bulbs for their info (read-only): nothing is changed.

Why this exists: Home Assistant can only control a WiZ bulb if it can reach it
over the local network. If the bulb is on another router's Wi-Fi, or on a
"guest" network, Home Assistant fails with "cannot connect". This script tells
you in a few seconds whether the bulb is reachable, and at which address.

Usage (run with Python 3 on the same computer as Home Assistant):
    python find_wiz_bulbs.py 192.168.1        scan 192.168.1.1 - 192.168.1.254
    python find_wiz_bulbs.py 192.168.1.42     ask one bulb directly

Tip: your network's first three numbers are the start of your computer's own
IPv4 address (Windows: run `ipconfig`; macOS/Linux: `ip addr` or `ifconfig`).
"""
import json
import socket
import sys
import time

WIZ_PORT = 38899  # WiZ bulbs listen for local commands on this UDP port


def ask_all(targets, method, wait=3.0):
    """Send one WiZ query to every target, then collect the answers."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.3)
    message = json.dumps({"method": method, "params": {}}).encode()
    for _ in range(2):  # twice, in case a packet gets lost
        for ip in targets:
            try:
                sock.sendto(message, (ip, WIZ_PORT))
            except OSError:
                pass
        time.sleep(0.3)
    answers = {}
    end = time.time() + wait
    while time.time() < end:
        try:
            data, (ip, _) = sock.recvfrom(4096)
            answers[ip] = json.loads(data.decode(errors="replace"))
        except (socket.timeout, ConnectionResetError, ValueError):
            # ConnectionResetError: Windows reports "nobody listening" this way
            pass
    return answers


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    arg = sys.argv[1].strip()
    parts = arg.split(".")
    if len(parts) == 3:
        targets = [f"{arg}.{i}" for i in range(1, 255)]
        print(f"Scanning {arg}.1 - {arg}.254 for WiZ bulbs ...")
    elif len(parts) == 4:
        targets = [arg]
        print(f"Asking {arg} ...")
    else:
        sys.exit("Give either three numbers (a network, e.g. 192.168.1) or four (one address).")

    configs = ask_all(targets, "getSystemConfig")
    if not configs:
        print("\nNo WiZ bulb answered.")
        print("  - Is the bulb powered on (wall switch on)?")
        print("  - Is it on the same router/Wi-Fi as this computer? Check its IP in the WiZ app.")
        print("  - WiZ app: Settings -> Security -> 'Allow local communication' must be on.")
        sys.exit(2)

    states = ask_all(list(configs), "getPilot", wait=2.0)
    for ip, cfg in sorted(configs.items()):
        res = cfg.get("result", {})
        st = states.get(ip, {}).get("result", {})
        print(f"\nWiZ bulb at {ip}")
        print(f"  model module : {res.get('moduleName', '?')}")
        print(f"  firmware     : {res.get('fwVersion', '?')}")
        if st:
            print(f"  is on        : {st.get('state')}")
            print(f"  brightness   : {st.get('dimming')}%")
            print(f"  Wi-Fi signal : {st.get('rssi')} dBm  (above -70 is fine)")
    print("\nUse that address when adding the WiZ integration in Home Assistant,")
    print("and reserve it in your router (DHCP reservation) so it never changes.")


if __name__ == "__main__":
    main()
