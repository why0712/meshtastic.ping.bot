# =====================================================
# Meshtastic Bot
# GitHub-ready example
# bot includes WAR GAMES and other easter eggs :)
# =====================================================
# MESHTASTIC BOT BY 9A3WHY @ cromesh.eu
# created with use of ChatGPT
# =====================================================

#!/usr/bin/env python3

import time
import random
from datetime import datetime

from meshtastic.serial_interface import SerialInterface
from pubsub import pub


# =====================================================
# CONFIG
# =====================================================

SERIAL_PORT = None
BOT_VERSION = "v1.1.1-clean"
NODE_LOG_INTERVAL = 60
GAME_TIMEOUT = 300


# =====================================================
# BOT CLASS
# =====================================================

class MeshBot:

    def __init__(self):
        self.log("SYSTEM", "Starting MeshBot...")

        # Connect to Meshtastic device
        try:
            self.iface = SerialInterface(devPath=SERIAL_PORT)
        except Exception as e:
            self.log("FATAL", f"SerialInterface failed: {e}")
            raise

        # Get node ID safely
        try:
            self.my_id = self.iface.getMyUser().get("id")
        except Exception:
            self.my_id = None

        self.games = {}
        self.last_node_log = 0

        pub.subscribe(self.on_receive, "meshtastic.receive")

        self.log("SYSTEM", f"Running as {self.my_id}")
        self.log("SYSTEM", "Ready")

    # =====================================================
    # LOGGER
    # =====================================================

    def log(self, tag, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [{tag}] {msg}")

    # =====================================================
    # SAFE SENDER
    # =====================================================

    def send_reply(self, destination, message):
        try:
            self.iface.sendText(message, destinationId=destination)
            self.log("TX", f"to={destination}")
        except Exception as e:
            self.log("ERROR", f"send_reply failed: {e}")

    # =====================================================
    # SYSTEM INFO
    # =====================================================

    def get_uptime(self):
        try:
            with open("/proc/uptime") as f:
                sec = float(f.read().split()[0])
            return f"{int(sec//86400)}d {int((sec%86400)//3600)}h {int((sec%3600)//60)}m"
        except:
            return "uptime unavailable"

    def get_nodes(self):
        try:
            nodes = getattr(self.iface, "nodes", {})
            return f"Nodes: {len(nodes)}"
        except Exception as e:
            return f"Node error: {e}"

    # =====================================================
    # GAME ENGINE
    # =====================================================

    def start_game(self, sender):
        self.games[sender] = {
            "state": "menu",
            "turn": 0,
            "score": 50,
            "last_seen": time.time()
        }

        return (
            "=== STRATEGIC SIMULATION ===\n"
            "1 START\n"
            "2 SCENARIO\n"
            "3 RANDOM\n\n"
            "TYPE QUIT TO EXIT"
        )

    def cleanup_games(self):
        now = time.time()
        expired = [
            user for user, g in self.games.items()
            if now - g.get("last_seen", now) > GAME_TIMEOUT
        ]

        for u in expired:
            self.log("GAME", f"expired {u}")
            self.games.pop(u, None)

    def process_game(self, sender, text):
        self.cleanup_games()

        raw = text.strip()
        low = raw.lower()

        game = self.games.get(sender)

        if low in ("admin",):
            return "ADMIN MODE"

        if not game:
            return None

        game["last_seen"] = time.time()

        if low in ("quit", "exit", "abort"):
            self.games.pop(sender, None)
            return "GAME EXITED"

        # MENU STATE
        if game["state"] == "menu":
            if raw not in ("1", "2", "3"):
                return "ENTER 1-3"

            game["state"] = "active"
            return "ACTIVE: A/B/C"

        # ACTIVE STATE
        if game["state"] == "active":

            if raw.upper() not in ("A", "B", "C"):
                return "ENTER A/B/C"

            game["turn"] += 1
            game["score"] = max(0, min(100, game["score"] + random.randint(-5, 5)))

            event = random.choice([
                "SIGNAL DETECTED",
                "LATENCY SPIKE",
                "ANOMALY",
                "SYSTEM FLUCTUATION"
            ])

            if game["turn"] >= 5:
                self.games.pop(sender, None)
                return "SIMULATION COMPLETE"

            return f"{event}\nSCORE: {game['score']}\nTURN {game['turn']}/5"

        return None

    # =====================================================
    # COMMAND HANDLER
    # =====================================================

    def handle_command(self, command, sender, packet):
        cmd = command.strip().lower().lstrip("!")

        if cmd == "cmd":
            reply = "ping\ntime\nuptime\nnodes\ninfo\nwargames\necho <text>"

        elif cmd == "time":
            reply = str(datetime.now())

        elif cmd == "uptime":
            reply = self.get_uptime()

        elif cmd == "nodes":
            reply = self.get_nodes()

        elif cmd == "ping":
            reply = (
                f"PONG\n"
                f"RSSI: {packet.get('rxRssi', '?')}\n"
                f"SNR: {packet.get('rxSnr', '?')}"
            )

        elif cmd == "info":
            reply = f"MeshBot {BOT_VERSION}"

        elif cmd == "wargames":
            reply = self.start_game(sender)

        elif cmd.startswith("echo "):
            reply = command[5:]

        else:
            return

        self.send_reply(sender, reply)

    # =====================================================
    # RECEIVE LOOP
    # =====================================================

    def on_receive(self, packet, interface):
        try:
            decoded = packet.get("decoded", {})
            text = decoded.get("text") or decoded.get("payload")

            if not text:
                return

            sender = packet.get("fromId")
            if not sender:
                return

            if sender == self.my_id:
                return

            self.log("RX", f"{sender}: {text}")

            self.last_node_log = 0

            # GAME FIRST
            game_reply = self.process_game(sender, text)
            if game_reply:
                self.send_reply(sender, game_reply)
                return

            # COMMANDS
            self.handle_command(text, sender, packet)

        except Exception as e:
            self.log("ERROR", str(e))

    # =====================================================
    # MAIN LOOP
    # =====================================================

    def run(self):
        self.log("SYSTEM", "loop running")

        try:
            while True:
                time.sleep(1)

                if time.time() - self.last_node_log >= NODE_LOG_INTERVAL:
                    self.log("NODES", self.get_nodes())
                    self.last_node_log = time.time()

        except KeyboardInterrupt:
            self.log("SYSTEM", "shutdown")
            try:
                self.iface.close()
            except:
                pass


# =====================================================
# ENTRY POINT
# =====================================================

if __name__ == "__main__":
    MeshBot().run()