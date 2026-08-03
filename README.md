# MeshBot for Meshtastic

```text
 __  __           _     ____        _
|  \/  | ___  ___| |__ | __ )  ___ | |_
| |\/| |/ _ \/ __| '_ \|  _ \ / _ \| __|
| |  | |  __/\__ \ | | | |_) | (_) | |_
|_|  |_|\___||___/_| |_|____/ \___/ \__|

 Lightweight Meshtastic Python Bot
```

> **Hack the mesh. Not the spectrum.**

A lightweight Python bot for the **Meshtastic** mesh network. MeshBot listens for incoming messages, processes commands, and responds over LoRa using the Meshtastic Python API.

Designed for Raspberry Pi and Linux systems with a USB-connected Meshtastic radio.

---

## Features

- Automatic USB serial detection
- Automatic reconnect with exponential backoff
- ACK-based delivery confirmation
- Private and channel messaging
- RSSI / SNR diagnostics
- Interactive Wargames simulation
- Rotating log files (`meshbot.log`)
- Lightweight and easily hackable Python code

---

## Requirements

- Python 3.10+
- Linux (Debian, Ubuntu, Raspberry Pi OS)

Install dependencies:

```bash
pip install meshtastic pubsub
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

| Command | Function |
|---------|----------|
| `!help` / `!cmd` | Help |
| `!info` | Bot information |
| `!ping` | RSSI / SNR |
| `!time` | Current time |
| `!uptime` | System uptime |
| `!nodes` | Known nodes |
| `!game` | Wargames simulation |

---

## Logging

```text
[RX]   packet received
[CMD]  command parsed
[TX]   reply transmitted
[ACK]  delivered
[ACK]  FAILED (<reason>)
[GAME] simulation event
[ERR]  system error
```

Rotating logs are written to `meshbot.log`.

---

## Known Issue (v1.7.0-beta)

Direct-message replies may fail with `NO_CHANNEL` when a remote node has a stale cached public key. Rebuild the node database or remove/re-add the affected contact.

---

# Release History

### v1.7.0-beta
- True ACK delivery confirmation
- Delivery callback logging
- Removed temporary debug output
- Fixed `!ping` formatting
- Documented DM routing issue

### v1.6.0
- Initial ACK callback framework

### v1.2.x
- Automatic USB detection
- Automatic reconnect
- Rotating logs
- Startup/shutdown improvements
- Generic MeshBot branding

### v1.2.0
- Connection retry scaffold
- Version cleanup
- Improved startup

### v1.1.0
- Initial public release
- !ping, !time, !uptime, !nodes, !info, !cmd
- Wargames simulation
- Hidden admin easter egg

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

Licensed under the **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**.

You are free to use, modify and redistribute this software provided that:

- Attribution to the original creator is preserved.
- Derivative works remain licensed under **CC BY-SA 4.0**.

https://creativecommons.org/licenses/by-sa/4.0/

---

```text
mesh all over the world -73 de 9A3WHY @ cromesh.eu
```
