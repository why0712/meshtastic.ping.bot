# MeshBot for Meshtastic

```text
       _             ____        _
 _ __ (_)_ __   __ _| __ )  ___ | |_
| '_ \| | '_ \ / _` |  _ \ / _ \| __|
| |_) | | | | | (_| | |_) | (_) | |_
| .__/|_|_| |_|\__, |____/ \___/ \__|
|_|            |___/                 

 Lightweight Meshtastic Python Bot
```

> **Hack the mesh. Not the spectrum.**

A lightweight Python bot for the **Meshtastic** mesh network. MeshBot listens for incoming messages, processes commands, and responds over LoRa using the Meshtastic Python API.

Designed for Raspberry Pi and Linux systems with a **USB-connected (serial)** Meshtastic radio. There is no TCP/network transport - if you're looking for a web dashboard talking to `meshtasticd` over TCP, that's a separate project (MeshMonitor), not this bot.

**Current release: `v2.0.0-beta`** — see [CHANGELOG.md](CHANGELOG.md) for full version history.

---

## Features

- Automatic USB serial detection (`/dev/serial/by-id/*`, falls back to `ttyACM*`/`ttyUSB*`)
- Automatic reconnect with exponential backoff
- True ACK-based delivery confirmation (not just "the serial write worked")
- Private (DM) messaging, correctly handles PKI-encrypted replies
- RSSI / SNR diagnostics
- System/mesh monitoring (`monitor`) and usage statistics (`stats`)
- Last-heard node summary (`lastheard`)
- Small utility/fun commands: `dice`, `coin`, `fortune`, `joke`, `quote`, `motd`
- Interactive, diplomacy-themed **Wargames** simulation (hidden command, three selectable "theaters")
- Rotating log files (`meshbot.log`)
- Lightweight and easily hackable Python code, minimal dependencies

---

## Requirements

- Python 3.10+
- Linux (Debian, Ubuntu, Raspberry Pi OS)
- A Meshtastic radio connected over **USB serial**

Install dependencies:

```bash
pip install -r requirements.txt
```

If required:

```bash
sudo usermod -aG dialout $USER
sudo systemctl stop ModemManager
```

---

## Installation

```bash
git clone https://github.com/why0712/meshtastic.ping.bot.git
cd meshtastic.ping.bot
pip install -r requirements.txt
python3 pingbot.py
```

---

## Commands

Commands may be entered with or without a leading `!` (e.g. `ping` and `!ping` both work).

| Command | Function |
|---------|----------|
| `help`, `cmd`, `?` | List available commands |
| `info` | Bot version / project info |
| `ping` | RSSI / SNR |
| `time` | Current time |
| `uptime` | Host/Pi system uptime |
| `nodes` | Known mesh node count |
| `monitor` | Full system + mesh + bot status report (RAM, CPU, disk, uptime, node count, active games, packet/reply counters) |
| `stats` | Usage statistics (messages, replies, top command, top node, games started/completed/quit) |
| `lastheard` | Most recently heard mesh nodes |
| `dice` | Roll a six-sided die |
| `coin` | Flip a coin |
| `fortune` | Random fortune-cookie-style line |
| `joke` | Random one-liner |
| `quote` | Random line from the MeshBot log |
| `motd` | Message of the day |

There is also a hidden `wargames` (alias `game`) command — not listed above on purpose. If you find it, `SHALL WE PLAY A GAME?`

---

## Logging

```text
[RX]     packet received
[CMD]    command parsed
[TX]     reply transmitted
[ACK]    delivered
[ACK]    FAILED (<reason>)
[GAME]   simulation event
[SYSTEM] startup / connect / reconnect
[ERROR]  system error
```

Logs are written to the console and to a rotating file, `meshbot.log`, next to the script.

---

## Known Issues (v2.0.0-beta)

- Direct-message replies can fail with a `NO_CHANNEL` routing error when a peer node has a stale cached public key (e.g. after a firmware reflash or factory reset on either side). Workaround: re-exchange node info on the affected node, or remove/re-add the stale contact on the sending device.
- `monitor`'s CPU-temperature reading is Raspberry Pi specific (`/sys/class/thermal/thermal_zone0`) and reports `N/A` on other hosts — expected, not a bug, useful for local testing off-Pi.
- `weather` from the original feature wishlist is intentionally not implemented — it needs outbound internet access, which doesn't fit this bot's offline/serial field-deployment model. May be revisited if a connectivity story exists for these nodes.

---

## Release History

Short summary below; **full, detailed changelog (including the historical parallel-branch bug and how it was fixed) lives in [CHANGELOG.md](CHANGELOG.md)**.

### v2.0.0-beta (current)
- New commands: `monitor`, `stats`, `lastheard`, `dice`, `coin`, `fortune`, `joke`, `quote`, `motd`
- Wargames overhaul: proper intro/outro text, three theaters, tension meter, branching endings, `amir`/`list games`/callsign easter eggs, `leave` added to quit words, timeout restored to 10 minutes
- Usage statistics and system-monitoring plumbing feeding `monitor`/`stats`
- `!cmd`/`!help` output condensed to save LoRa airtime now that the list has grown
- Repository cleanup: single canonical `pingbot.py` entry point going forward (no more per-release filenames); versions are tracked via git tags and `CHANGELOG.md`, not filenames

### v1.7.0-beta
- True ACK delivery confirmation via `wantAck` + `onResponse`
- Fixed `!ping` reply formatting bug

### v1.6.0
- Initial ACK callback framework (superseded by v1.7.0)

### v1.2.x
- Automatic USB detection, automatic reconnect, rotating logs
- Fixed a PKI-encrypted DM delivery bug introduced by an earlier "reply on incoming channel index" change

### v1.1.0
- Initial public release: `ping`, `time`, `uptime`, `nodes`, `info`, `cmd`/`help`
- Wargames simulation (early stub version), hidden `admin` easter egg

---

# Credits

## Creator

**9A3WHY**
Original author, project architecture, development and maintenance.

## Contributor

**9A3VEX**
Development, testing, documentation and feature contributions.

---

# License

© 2026 **9A3WHY** and contributors.

Licensed under the **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**. Full terms in [LICENSE](LICENSE).

You are free to use, modify and redistribute this software provided that:

- Attribution to the original creator is preserved.
- Derivative works remain licensed under **CC BY-SA 4.0**.

https://creativecommons.org/licenses/by-sa/4.0/

---

```text
mesh all over the world -73 de 9A3WHY @ cromesh.eu
```
