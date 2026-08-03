#!/usr/bin/env python3
# =====================================================
# Meshtastic Bot - MeshBot v1.2.2
# GitHub-ready example
# bot includes WAR GAMES and other easter eggs :)
# =====================================================
# MESHTASTIC BOT BY 9A3WHY @ cromesh.eu
# created with use of ChatGPT
# =====================================================
#
# CHANGELOG (v1.2.1 -> v1.2.2)
# - Fixed TX-not-arriving bug: replies were always sent on channel index 0
#   (Primary), regardless of which channel the incoming message was on. If
#   someone messaged the bot on a secondary channel (different PSK), the
#   reply went out on the wrong channel/key and their radio silently could
#   not decode it - RX worked, TX "succeeded" locally, but nothing arrived.
#   Now the bot reads the channel index off the incoming packet and replies
#   on that same channel.
#
# CHANGELOG (v1.1.2 -> v1.2.1)
# - Merged the v1.2.0 "connect with retry" scaffold into the full v1.1.2
#   bot logic, and extended it into real auto-reconnect (not just a
#   connect-at-startup loop):
#     * Tries /dev/serial/by-id/* symlinks first (stable across USB
#       replugs/reboots), then falls back to common ttyACM/ttyUSB names.
#     * Subscribes to meshtastic's "connection.lost" pubsub topic and
#       automatically reconnects (with exponential backoff) if the radio
#       disconnects while the bot is running.
#     * send_reply() now detects a broken serial link and triggers a
#       reconnect instead of just logging the error and going silent.
# - Fixed a string-concatenation bug in the !ping reply where
#   "...in pvt" and "... for more ..." were glued together with no
#   space/newline between them.
# - SERIAL_PORT is now a list of candidates instead of one hardcoded path.
# - Minor robustness fixes (guarding getMyUser()/nodes access, closing the
#   interface cleanly on shutdown and on reconnect).
# =====================================================

import glob
import random
import time
from datetime import datetime

from meshtastic.serial_interface import SerialInterface
from pubsub import pub
from serial.serialutil import SerialException

# =====================================================
# CONFIG
# =====================================================

# Fallback device names, tried in order if nothing is found under
# /dev/serial/by-id. Add more here if your board enumerates differently.
SERIAL_PORT_CANDIDATES = [
    "/dev/ttyACM0",
    "/dev/ttyACM1",
    "/dev/ttyUSB0",
    "/dev/ttyUSB1",
]

# Glob for stable-by-id serial symlinks (preferred: survives replugging
# into a different USB port / reboot order).
SERIAL_BYID_GLOB = "/dev/serial/by-id/*"

GAME_TIMEOUT = 300          # seconds of inactivity before a game session expires
RECONNECT_DELAY = 5         # initial seconds between reconnect attempts
MAX_RECONNECT_DELAY = 60    # cap for exponential backoff

# =====================================================
# BOT
# =====================================================


class MeshBot:

    def __init__(self):

        self.iface = None
        self.my_id = None
        self.games = {}
        self.last_activity = time.time()

        self.log("SYSTEM", "Starting MeshBot Node...")

        pub.subscribe(self.on_receive, "meshtastic.receive")
        pub.subscribe(self.on_connection_lost, "meshtastic.connection.lost")

        self.connect()

        self.log("SYSTEM", f"Connected as {self.my_id}")
        self.log("SYSTEM", "Ready")

    # =====================================================
    # LOGGER
    # =====================================================

    def log(self, tag, message):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [{tag}] {message}")

    # =====================================================
    # CONNECTION MANAGEMENT (auto-reconnect)
    # =====================================================

    def _candidate_ports(self):
        # Prefer stable by-id symlinks, then fall back to raw device names.
        ports = sorted(glob.glob(SERIAL_BYID_GLOB))
        ports += SERIAL_PORT_CANDIDATES
        return ports

    def connect(self):
        """Blocks until a serial connection to the radio is established.
        Retries forever with exponential backoff, trying every known
        candidate port each pass."""

        delay = RECONNECT_DELAY

        while True:
            candidates = self._candidate_ports()

            if not candidates:
                self.log("SYSTEM", "No serial candidates found yet...")

            for port in candidates:
                try:
                    self.log("SYSTEM", f"Trying {port} ...")
                    self.iface = SerialInterface(devPath=port)

                    try:
                        self.my_id = self.iface.getMyUser().get("id", "")
                    except Exception:
                        self.my_id = None

                    self.log("SYSTEM", f"Connected on {port}")
                    return

                except Exception as e:
                    self.log("SYSTEM", f"{port}: {e}")

            self.log("SYSTEM", f"Retrying in {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, MAX_RECONNECT_DELAY)

    def on_connection_lost(self, interface=None):
        # Fired by the meshtastic library itself when the serial link drops
        # (e.g. radio unplugged / power loss). Reconnect automatically.
        self.log("SYSTEM", "Connection lost - attempting to reconnect...")

        try:
            if self.iface:
                self.iface.close()
        except Exception:
            pass

        self.iface = None
        self.connect()
        self.log("SYSTEM", f"Reconnected as {self.my_id}")

    # =====================================================

    def send_reply(self, destination, message, channel_index=0):

        self.log("TX", f"to={destination} channel={channel_index}")
        self.log("TX", message)

        try:
            self.iface.sendText(
                message,
                destinationId=destination,
                channelIndex=channel_index,
            )
            self.log("TX", "success")

        except (SerialException, OSError) as e:
            # Link is actually broken - don't just log and go silent,
            # trigger the same reconnect path as on_connection_lost.
            self.log("ERROR", f"send failed, link appears down: {e}")
            self.on_connection_lost()

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

        # Easter egg reply only - grants no real privileges, just a joke line.
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

    def handle_command(self, command, sender, packet, channel_index=0):

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

            # Fixed: was missing a separator between "...in pvt" and
            # "... for more ...", which glued the two phrases together.
            reply = (
                "PONG\n"
                f"RSSI: {rssi} dBm\n"
                f"SNR: {snr} dB\n\n"
                "pls type info in pvt "
                "... for more ..."
            )

        elif command == "info":
            reply = "MeshBot\nType !cmd for the list of commands."

        elif command == "wargames":
            reply = self.start_game(sender)

        else:
            return

        self.send_reply(sender, reply, channel_index)

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

            # Meshtastic omits "channel" for the default/Primary channel (0),
            # so this defaults to 0 when the key is absent.
            channel_index = packet.get("channel", 0)

            self.log("RX", f"{sender}: {text} (channel={channel_index})")

            self.last_activity = time.time()

            game_reply = self.process_game(sender, text)
            if game_reply:
                self.send_reply(sender, game_reply, channel_index)
                return

            self.handle_command(text, sender, packet, channel_index)

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
                if self.iface:
                    self.iface.close()
            except Exception:
                pass


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    MeshBot().run()
