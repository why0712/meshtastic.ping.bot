#!/usr/bin/env python3
# =====================================================
# Meshtastic Bot
#
# Connects to a Meshtastic radio over a serial (USB) link with automatic
# reconnect/backoff, and answers simple text commands sent to it over the
# mesh (!ping, !time, !uptime, !nodes, !info, !wargames), plus a small
# turn-based "wargames" text game.
# =====================================================

import glob
import logging
import os
import random
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

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

# Logging: written to LOG_FILE (next to this script) AND echoed to the console.
# The file rotates so it can't grow without bound: once it hits LOG_MAX_BYTES it
# rolls over to meshbot.log.1, .2, ... keeping LOG_BACKUP_COUNT old files.
LOG_FILE = "meshbot.log"
LOG_MAX_BYTES = 2 * 1024 * 1024   # 2 MB per file
LOG_BACKUP_COUNT = 5              # keep 5 rotated files (~10 MB total)

# =====================================================
# LOGGING SETUP
# =====================================================


def setup_logging():
    """Configure the shared 'meshbot' logger once: console + rotating file.

    Falls back to console-only if the log file can't be opened (e.g. read-only
    directory) so the bot never fails to start just because logging to disk
    is unavailable."""

    logger = logging.getLogger("meshbot")

    if logger.handlers:            # already configured (e.g. re-imported)
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    try:
        log_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), LOG_FILE
        )
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"[SYSTEM] file logging disabled: {e}")

    return logger


LOG = setup_logging()

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
        # Routed through the shared logger so every line goes to both the
        # console and the rotating log file.
        LOG.info(f"[{tag}] {message}")

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

    def send_reply(self, destination, message):

        self.log("TX", f"to={destination}")
        self.log("TX", message)

        try:
            # Reply as a plain direct message to the sender. We deliberately
            # do NOT pass channelIndex here: PKI-encrypted direct messages
            # carry no channel index, and forcing channelIndex=0 would
            # encrypt the reply with the Primary channel PSK instead of PKI,
            # so the sender couldn't decode it (TX "succeeds" locally, but
            # nothing arrives). Letting the library pick the encryption is
            # what a plain DM reply needs.
            self.iface.sendText(
                message,
                destinationId=destination,
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
                "pls type info in pvt "
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
                if self.iface:
                    self.iface.close()
            except Exception:
                pass


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    MeshBot().run()
