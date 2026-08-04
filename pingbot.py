#!/usr/bin/env python3
# =====================================================
# MeshBot 9A3WHY - Meshtastic Serial Bot
# v2.0.0-beta
#
# Connects to a Meshtastic radio over a SERIAL (USB) link ONLY, with
# automatic reconnect/backoff, and answers text commands sent to it over
# the mesh (plain form, e.g. "ping", or legacy "!"-prefixed form, e.g.
# "!ping" - both are accepted). Includes a hidden turn-based "wargames"
# text adventure and a handful of small utility/fun commands.
#
# SCOPE NOTE: this bot is serial-device-only (SerialInterface / USB /
# /dev/ttyACM*, /dev/ttyUSB*, /dev/serial/by-id/*). It intentionally has
# no TCP/network transport. The MeshMonitor + MeshToad Docker stack
# (see MeshMonitor_MeshToad_Handoff.md) is a separate, unrelated
# deployment that talks to meshtasticd over TCP - it is out of scope for
# this script and the two should not be conflated or merged.
#
# Full version history: see CHANGELOG.md
# =====================================================

import glob
import logging
import os
import random
import shutil
import time
from collections import Counter
from datetime import datetime
from logging.handlers import RotatingFileHandler

from meshtastic.serial_interface import SerialInterface
from pubsub import pub
from serial.serialutil import SerialException

# =====================================================
# CONFIG
# =====================================================

VERSION = "2.0.0-beta"
CALLSIGN = "9A3WHY"
WEBSITE = "cromesh.eu"

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

GAME_TIMEOUT = 600          # seconds of inactivity before a game session expires (~10 min)
RECONNECT_DELAY = 5         # initial seconds between reconnect attempts
MAX_RECONNECT_DELAY = 60    # cap for exponential backoff

QUIT_WORDS = ("quit", "exit", "leave", "abort")

# Logging: written to LOG_FILE (next to this script) AND echoed to the console.
# The file rotates so it can't grow without bound: once it hits LOG_MAX_BYTES it
# rolls over to meshbot.log.1, .2, ... keeping LOG_BACKUP_COUNT old files.
LOG_FILE = "meshbot.log"
LOG_MAX_BYTES = 2 * 1024 * 1024   # 2 MB per file
LOG_BACKUP_COUNT = 5              # keep 5 rotated files (~10 MB total)

# =====================================================
# FLAVOR TEXT (fun commands)
# All original text, unattributed / attributed to "MeshBot Log" only -
# no quotes from real people or copyrighted sources.
# =====================================================

MOTD_LINES = [
    "Keep your antenna high and your packets dry.",
    "Mesh grows stronger with every new node.",
    "73 and good propagation to all listening.",
    "LoRa is patient. So are good operators.",
    "A well-placed repeater is worth a thousand watts.",
]

FORTUNES = [
    "Your next packet will find a clear path.",
    "A quiet channel is a productive channel.",
    "Good antennas come to those who climb.",
    "The mesh rewards patience and low power.",
    "Static today, signal tomorrow.",
    "Your callsign will be heard three hops away.",
]

JOKES = [
    "Why did the packet break up with the router? It needed more space.",
    "What does a ham operator say at a party? CQ CQ, anyone home?",
    "Why was the SNR always calm? Good signal, low drama.",
    "How does a mesh node flirt? It sends a beacon.",
    "Why don't LoRa nodes get lost? They always find a hop.",
]

QUOTES = [
    "\"Every hop is a promise kept.\" - MeshBot Log",
    "\"Range is earned, not assumed.\" - MeshBot Log",
    "\"A silent node is not a dead node.\" - MeshBot Log",
    "\"Diplomacy travels faster than any packet.\" - MeshBot Log",
]

# =====================================================
# WARGAMES - fictional, retro-terminal, diplomacy-focused text adventure.
# No real countries/units are referenced; "theaters" are flavor labels only.
# =====================================================

THEATERS = {
    "1": {
        "name": "GLOBAL STRATEGY",
        "events": [
            "SATELLITE ANOMALY DETECTED",
            "BACK-CHANNEL TALKS PROPOSED",
            "COMMUNICATIONS BLACKOUT REPORTED",
            "UNIDENTIFIED SIGNAL LOGGED",
            "ALLIED NODE REQUESTS ORDERS",
            "SENSOR NETWORK FLUCTUATION",
        ],
    },
    "2": {
        "name": "EUROPEAN THEATER",
        "events": [
            "DIPLOMATIC CABLE RECEIVED",
            "BORDER SENSOR TRIGGERED",
            "REGIONAL COUNCIL REQUESTS BRIEFING",
            "WEATHER FRONT DELAYS RESPONSE",
            "CIVILIAN NETWORK CONGESTION",
            "OBSERVER MISSION REPORTS IN",
        ],
    },
    "3": {
        "name": "PACIFIC COMMAND",
        "events": [
            "FLEET STATUS UPDATE RECEIVED",
            "TSUNAMI SENSOR PING",
            "ISLAND RELAY STATION OFFLINE",
            "PATROL REQUESTS INSTRUCTIONS",
            "TRADE ROUTE DISPUTE FLAGGED",
            "LONG-RANGE CONTACT UNCONFIRMED",
        ],
    },
}

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
        self.start_time = time.time()

        # ---- usage statistics (see: monitor / stats commands) ----
        self.stats = {
            "messages_total": 0,
            "replies_total": 0,
            "packets_total": 0,
            "games_started": 0,
            "games_completed": 0,
            "games_aborted": 0,
            "commands": Counter(),
            "node_activity": Counter(),
            "last_packet_time": None,
        }

        self.log("SYSTEM", f"Starting MeshBot Node v{VERSION}...")

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
    # CONNECTION MANAGEMENT (auto-reconnect, serial only)
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

    def _on_ack_response(self, packet):
        # Called asynchronously once the mesh actually confirms (or fails to
        # confirm) delivery of a wantAck=True message. This is the only real
        # signal that a reply left the radio and reached the destination -
        # "sendText() didn't raise" is NOT proof of delivery, it only means
        # the local node accepted the packet over serial.
        try:
            decoded = packet.get("decoded", {})
            routing = decoded.get("routing", {})
            error_reason = routing.get("errorReason", "NONE")

            if error_reason == "NONE":
                self.log("ACK", f"delivered to {packet.get('toId', '?')}")
            else:
                self.log("ACK", f"FAILED ({error_reason}) to {packet.get('toId', '?')}")

        except Exception as e:
            self.log("ACK", f"could not parse ack packet: {e}")

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
            #
            # wantAck=True + onResponse gives us a real delivery signal (see
            # _on_ack_response) instead of just "the serial write worked".
            self.iface.sendText(
                message,
                destinationId=destination,
                wantAck=True,
                onResponse=self._on_ack_response,
            )
            self.stats["replies_total"] += 1
            self.log("TX", "queued (awaiting ack)")

        except (SerialException, OSError) as e:
            # Link is actually broken - don't just log and go silent,
            # trigger the same reconnect path as on_connection_lost.
            self.log("ERROR", f"send failed, link appears down: {e}")
            self.on_connection_lost()

        except Exception as e:
            self.log("ERROR", str(e))

    # =====================================================
    # SYSTEM / DIAGNOSTIC HELPERS
    # =====================================================

    def _format_duration(self, seconds):
        seconds = max(0, int(seconds))
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        m = (seconds % 3600) // 60
        return f"{d}d {h}h {m}m"

    def _format_ago(self, seconds):
        seconds = max(0, int(seconds))
        if seconds < 60:
            return f"{seconds}s ago"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        return f"{seconds // 3600}h ago"

    def get_uptime(self):
        """Raspberry Pi / host system uptime, from /proc/uptime."""
        try:
            with open("/proc/uptime") as f:
                uptime_seconds = float(f.read().split()[0])
            return self._format_duration(uptime_seconds)
        except Exception as e:
            return "N/A"

    def get_bot_uptime(self):
        """How long this bot process has been running."""
        return self._format_duration(time.time() - self.start_time)

    def get_nodes(self):
        try:
            return f"Nodes: {len(self.iface.nodes)}"
        except Exception as e:
            return f"Node error: {e}"

    def get_cpu_temp(self):
        # Raspberry Pi specific; returns N/A gracefully on other hosts.
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                milli = int(f.read().strip())
            return f"{milli / 1000:.1f}C"
        except Exception:
            return "N/A"

    def get_ram_usage(self):
        try:
            info = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    key, _, val = line.partition(":")
                    info[key.strip()] = int(val.strip().split()[0])  # kB

            total = info.get("MemTotal", 0)
            avail = info.get("MemAvailable", info.get("MemFree", 0))
            used = max(0, total - avail)
            pct = (used / total * 100) if total else 0
            return f"{pct:.0f}% ({used // 1024}/{total // 1024} MB)"
        except Exception:
            return "N/A"

    def get_disk_usage(self):
        try:
            total, used, _free = shutil.disk_usage("/")
            pct = (used / total * 100) if total else 0
            return f"{pct:.0f}% ({used // (1024 ** 3)}/{total // (1024 ** 3)} GB)"
        except Exception:
            return "N/A"

    def get_load_avg(self):
        try:
            load1, _, _ = os.getloadavg()
            return f"{load1:.2f}"
        except Exception:
            return "N/A"

    def build_monitor_report(self):
        node_count = 0
        try:
            node_count = len(self.iface.nodes) if self.iface else 0
        except Exception:
            pass

        last_pkt = self.stats.get("last_packet_time")
        last_pkt_str = self._format_ago(time.time() - last_pkt) if last_pkt else "n/a"

        return (
            f"MONITOR v{VERSION}\n"
            f"Node: {self.my_id or '?'}\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}\n"
            f"Bot up: {self.get_bot_uptime()}\n"
            f"Sys up: {self.get_uptime()}\n"
            f"Mesh nodes: {node_count}\n"
            f"Games active: {len(self.games)}\n"
            f"RAM: {self.get_ram_usage()}\n"
            f"CPU: load {self.get_load_avg()}, {self.get_cpu_temp()}\n"
            f"Disk: {self.get_disk_usage()}\n"
            f"Last pkt: {last_pkt_str}\n"
            f"Pkts/Replies: {self.stats['packets_total']}/{self.stats['replies_total']}"
        )

    def build_stats_report(self):
        top_cmd_list = self.stats["commands"].most_common(1)
        top_cmd = f"{top_cmd_list[0][0]} x{top_cmd_list[0][1]}" if top_cmd_list else "n/a"

        top_node_list = self.stats["node_activity"].most_common(1)
        top_node = f"{top_node_list[0][0]} x{top_node_list[0][1]}" if top_node_list else "n/a"

        return (
            "STATS\n"
            f"Messages rx: {self.stats['messages_total']}\n"
            f"Replies tx: {self.stats['replies_total']}\n"
            f"Top command: {top_cmd}\n"
            f"Top node: {top_node}\n"
            f"Games started: {self.stats['games_started']}\n"
            f"Games done: {self.stats['games_completed']}\n"
            f"Games quit: {self.stats['games_aborted']}"
        )

    def build_lastheard_report(self):
        try:
            nodes = self.iface.nodes or {}
        except Exception:
            return "Node list unavailable"

        now = time.time()
        entries = []

        for node_id, info in nodes.items():
            if node_id == self.my_id:
                continue
            last = info.get("lastHeard")
            if not last:
                continue
            short = info.get("user", {}).get("shortName", node_id)
            entries.append((now - last, f"{short} {self._format_ago(now - last)}"))

        if not entries:
            return "No recently heard nodes"

        entries.sort(key=lambda e: e[0])
        top = entries[:5]

        return "LAST HEARD\n" + "\n".join(line for _age, line in top)

    # =====================================================
    # GAME ENGINE - "wargames" (hidden command)
    # =====================================================

    def start_game(self, sender):

        self.log("GAME", f"started by {sender}")

        self.games[sender] = {
            "state": "menu",
            "theater": None,
            "turn": 0,
            "tension": 50,
            "choices": [],
            "last_seen": time.time(),
        }
        self.stats["games_started"] += 1

        return (
            f"GREETINGS PROFESSOR {CALLSIGN}\n\n"
            "SHALL WE PLAY A GAME?\n\n"
            "1 GLOBAL STRATEGY\n"
            "2 EUROPEAN THEATER\n"
            "3 PACIFIC COMMAND\n\n"
            "TYPE QUIT TO EXIT"
        )

    def _turn_prompt(self, theater_name):
        return (
            f"{theater_name}\n"
            "A) OPEN CHANNEL\n"
            "B) GATHER INTEL\n"
            "C) SHOW OF FORCE"
        )

    def _ending(self, game):

        tension = game["tension"]

        if tension <= 30:
            outcome = "CRISIS AVERTED THROUGH DIALOGUE"
        elif tension <= 70:
            outcome = "UNEASY CALM ACHIEVED"
        else:
            outcome = "TENSION CRITICAL - DIPLOMATS RECALLED"

        dominant = Counter(game.get("choices", [])).most_common(1)
        dominant_choice = dominant[0][0] if dominant else "B"
        approach = {
            "A": "APPROACH: DIPLOMATIC",
            "B": "APPROACH: CAUTIOUS",
            "C": "APPROACH: ASSERTIVE",
        }.get(dominant_choice, "APPROACH: CAUTIOUS")

        return (
            "SIMULATION COMPLETE\n\n"
            f"{outcome}\n"
            f"{approach}\n\n"
            "A STRANGE GAME.\n"
            "THE ONLY WINNING MOVE IS NOT TO PLAY.\n\n"
            "SHALL WE PLAY A NICE GAME OF CHESS?\n\n"
            f"TY for playing {CALLSIGN} rPi-bot"
        )

    def cleanup_games(self):

        now = time.time()
        expired = []

        for user, g in self.games.items():
            if now - g.get("last_seen", now) > GAME_TIMEOUT:
                expired.append(user)

        for u in expired:
            self.log("GAME", f"timeout {u}")
            del self.games[u]
            self.stats["games_aborted"] += 1

    def process_game(self, sender, text):

        self.cleanup_games()

        raw = text.strip()
        low = raw.lower()

        game = self.games.get(sender)

        # ---- standalone easter eggs: work regardless of active game state,
        #      and never require the user to already be "in" the game. ----
        if low == "admin":
            # Easter egg reply only - grants no real privileges, just a joke line.
            return "ADMIN MODE ACCESS GRANTED"

        if low == "amir":
            return "HELLO AMIR\nHOW ARE YOU FEELING TODAY?"

        if low == "list games":
            return (
                "LIST OF AVAILABLE GAMES\n\n"
                "BLACK JACK\nGIN RUMMY\nCHESS\nGLOBAL STRATEGY"
            )

        if low == CALLSIGN.lower():
            # Typing the bot's own callsign is a secret alias for !wargames.
            return self.start_game(sender)

        if not game:
            return None

        game["last_seen"] = time.time()

        self.log("GAME", f"{sender}: {raw}")

        if low in QUIT_WORDS:
            del self.games[sender]
            self.stats["games_aborted"] += 1
            return "SIMULATION TERMINATED"

        # ---- theater selection ----
        if game["state"] == "menu":

            if raw not in THEATERS:
                return "ENTER 1, 2, OR 3"

            theater = THEATERS[raw]
            game["state"] = "active"
            game["theater"] = raw

            return (
                f"{theater['name']} SELECTED\n\n"
                f"{self._turn_prompt(theater['name'])}"
            )

        # ---- gameplay ----
        if game["state"] == "active":

            choice = raw.upper()
            if choice not in ("A", "B", "C"):
                return "ENTER A / B / C"

            theater = THEATERS[game["theater"]]

            game["turn"] += 1
            game["choices"].append(choice)

            # Nudges toward diplomacy without forbidding other choices:
            # A (diplomacy) lowers tension, C (show of force) raises it.
            delta = {
                "A": random.randint(-8, -2),
                "B": random.randint(-2, 2),
                "C": random.randint(2, 10),
            }[choice]
            game["tension"] = max(0, min(100, game["tension"] + delta))

            event = random.choice(theater["events"])

            if game["turn"] >= 5:
                reply = self._ending(game)
                del self.games[sender]
                self.stats["games_completed"] += 1
                return reply

            return (
                f"{event}\n"
                f"TENSION: {game['tension']}\n"
                f"TURN {game['turn']}/5\n\n"
                f"{self._turn_prompt(theater['name'])}"
            )

        return None

    # =====================================================
    # COMMAND HANDLING
    # =====================================================

    def handle_command(self, command, sender, packet):

        command = command.strip().lower()

        if command.startswith("!"):
            command = command[1:]

        self.log("CMD", f"{sender}: {command}")

        reply = None

        if command in ("cmd", "help", "?"):
            reply = (
                "CMDS: ping time uptime nodes info monitor stats "
                "lastheard dice coin fortune joke quote motd"
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
            reply = (
                f"MeshBot v{VERSION}\n"
                f"{WEBSITE}\n"
                f"73 de {CALLSIGN}\n"
                "Type !cmd for commands."
            )

        elif command == "monitor":
            reply = self.build_monitor_report()

        elif command == "stats":
            reply = self.build_stats_report()

        elif command == "lastheard":
            reply = self.build_lastheard_report()

        elif command == "dice":
            reply = f"DICE: {random.randint(1, 6)}"

        elif command == "coin":
            reply = f"COIN: {random.choice(['HEADS', 'TAILS'])}"

        elif command == "fortune":
            reply = random.choice(FORTUNES)

        elif command == "joke":
            reply = random.choice(JOKES)

        elif command == "quote":
            reply = random.choice(QUOTES)

        elif command == "motd":
            reply = random.choice(MOTD_LINES)

        elif command in ("wargames", "game"):
            # Hidden: deliberately NOT listed in cmd/help output.
            reply = self.start_game(sender)

        if reply is None:
            return

        self.stats["commands"][command] += 1
        self.send_reply(sender, reply)

    # =====================================================

    def on_receive(self, packet, interface):

        try:
            # Count every packet the radio hands us, even ones we ignore
            # below (telemetry, position, etc.) - useful for "monitor".
            self.stats["packets_total"] += 1
            self.stats["last_packet_time"] = time.time()

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
            self.stats["messages_total"] += 1
            self.stats["node_activity"][sender] += 1

            game_reply = self.process_game(sender, text)
            if game_reply:
                self.send_reply(sender, game_reply)
                return

            self.handle_command(text, sender, packet)

        except Exception as e:
            # Never let a malformed/unexpected packet take the bot down.
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
