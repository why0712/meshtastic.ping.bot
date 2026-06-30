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
GAME_TIMEOUT = 300

# =====================================================
# BOT
# =====================================================

class MeshBot:

    def __init__(self):

        self.log("SYSTEM", "Starting MeshBot Node...")

        # TCP CONNECTION (NOT SERIAL)
        self.iface = SerialInterface(devPath=SERIAL_PORT)

        # safer node ID handling (new + old versions)
        try:
            self.my_id = self.iface.getMyUser().get("id", "")
        except Exception:
            self.my_id = None

        self.games = {}
        self.last_activity = time.time()

        pub.subscribe(self.on_receive, "meshtastic.receive")

        self.log("SYSTEM", f"Connected as {self.my_id}")
        self.log("SYSTEM", "Ready")

    # =====================================================
    # LOGGER
    # =====================================================

    def log(self, tag, message):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [{tag}] {message}")

    # =====================================================

    def send_reply(self, destination, message):

        self.log("TX", f"to={destination}")
        self.log("TX", message)

        try:
            # compatibility-safe sendText
            self.iface.sendText(message, destinationId=destination)
            self.log("TX", "success")

        except Exception as e:
            self.log("ERROR", str(e))

    # =====================================================

    def get_uptime(self):

        try:
            with open("/proc/uptime") as f:
                uptime_seconds = float(f.read().split()[0])

            d = int(uptime_seconds // 86400)
            h = int((uptime_seconds % 86400) // 3600)
            m = int((uptime_seconds % 3600) // 60)

            return f"{d}d {h}h {m}m"

        except Exception as e:
            return str(e)

    # =====================================================

    def get_nodes(self):

        try:
            return f"Nodes: {len(self.iface.nodes)}"
        except Exception as e:
            return f"Node error: {e}"

    # =====================================================
    # GAME ENGINE
    # =====================================================

    def start_game(self, sender):

        self.log("GAME", f"started by {sender}")

        self.games[sender] = {
            "state": "menu",
            "turn": 0,
            "score": 50,
            "last_seen": time.time()
        }

        return (
            "=== STRATEGIC SIMULATION ===\n\n"
            "SYSTEM READY\n\n"
            "1 START SIMULATION\n"
            "2 LOAD SCENARIO\n"
            "3 RANDOM EVENT\n\n"
            "TYPE QUIT TO EXIT"
        )

    # =====================================================

    def cleanup_games(self):

        now = time.time()
        expired = []

        for user, g in self.games.items():
            if now - g.get("last_seen", now) > GAME_TIMEOUT:
                expired.append(user)

        for u in expired:
            self.log("GAME", f"timeout {u}")
            del self.games[u]

    # =====================================================

    def process_game(self, sender, text):

        self.cleanup_games()

        raw = text.strip()
        low = raw.lower()

        game = self.games.get(sender)

        if low == "admin":
            return "ADMIN MODE ACCESS GRANTED"

        if not game:
            return None

        game["last_seen"] = time.time()

        self.log("GAME", f"{sender}: {raw}")

        if low in ("quit", "exit", "abort"):
            del self.games[sender]
            return "SIMULATION TERMINATED"

        if game["state"] == "menu":

            if raw not in ("1", "2", "3"):
                return "ENTER 1-3"

            game["state"] = "active"

            return (
                "SIMULATION ACTIVE\n"
                "A) STABILIZE SYSTEM\n"
                "B) ANALYZE SIGNALS\n"
                "C) EXECUTE PROTOCOL"
            )

        if game["state"] == "active":

            if raw.upper() not in ("A", "B", "C"):
                return "ENTER A / B / C"

            game["turn"] += 1
            game["score"] += random.randint(-5, 5)

            game["score"] = max(0, min(100, game["score"]))

            event = random.choice([
                "SIGNAL DETECTED",
                "NETWORK LATENCY SPIKE",
                "ANOMALY DETECTED",
                "SYSTEM FLUCTUATION"
            ])

            if game["turn"] >= 5:
                del self.games[sender]
                return (
                    "SIMULATION COMPLETE\n\n"
                    "SYSTEM STABILIZED\n"
                    "SESSION CLOSED"
                )

            return (
                f"{event}\n"
                f"SYSTEM SCORE: {game['score']}\n"
                f"TURN: {game['turn']}/5"
            )

        return None

    # =====================================================

    def handle_command(self, command, sender, packet):

        command = command.strip().lower()

        if command.startswith("!"):
            command = command[1:]

        self.log("CMD", f"{sender}: {command}")

        if command == "cmd":
            reply = (
                "ping\n"
                "time\n"
                "uptime\n"
                "nodes\n"
                "info\n"
                "wargames"
            )

        elif command == "time":
            reply = str(datetime.now())

        elif command == "uptime":
            reply = self.get_uptime()

        elif command == "nodes":
            reply = self.get_nodes()

        elif command == "ping":
            rssi = packet.get("rxRssi", "?")
            snr = packet.get("rxSnr", "?")

            reply = (
                "PONG\n"
                f"RSSI: {rssi} dBm\n"
                f"SNR: {snr} dB\n\n"
                "pls type info in pvt"
                "... for more ..."
            )

        elif command == "info":
            reply = "MeshBot\nType !cmd for the list of commands."

        elif command == "wargames":
            reply = self.start_game(sender)

        else:
            return

        self.send_reply(sender, reply)

    # =====================================================

    def on_receive(self, packet, interface):

        try:
            if "decoded" not in packet:
                return

            decoded = packet["decoded"]

            if decoded.get("portnum") != "TEXT_MESSAGE_APP":
                return

            text = decoded.get("text", "").strip()
            if not text:
                return

            sender = packet.get("fromId")

            if sender == self.my_id:
                return

            self.log("RX", f"{sender}: {text}")

            self.last_activity = time.time()

            game_reply = self.process_game(sender, text)
            if game_reply:
                self.send_reply(sender, game_reply)
                return

            self.handle_command(text, sender, packet)

        except Exception as e:
            self.log("ERROR", str(e))

    # =====================================================

    def run(self):

        self.log("SYSTEM", "loop running")

        try:
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            self.log("SYSTEM", "shutdown")
            try:
                self.iface.close()
            except:
                pass


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    MeshBot().run()

