# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [1.7.0-beta] - 2026-07-10

Marked **BETA**: private-message (DM) delivery reliability is still under
active investigation on some node/firmware combinations (see Known Issues
below). Broadcast/channel replies and all local commands are stable.

### Added
- Real delivery confirmation for outgoing replies: `sendText()` now uses
  `wantAck=True` with an `onResponse` callback, logging a genuine `[ACK]
  delivered` or `[ACK] FAILED (<reason>)` line instead of a `[TX] success`
  log that only meant "the local node accepted the packet over serial" and
  said nothing about whether it actually reached the destination.

### Changed
- Cleaned up temporary `[DEBUG]` packet-field logging (channel /
  pkiEncrypted / toId / hopLimit) that was added mid-development to
  diagnose delivery failures. No longer needed for normal operation; can be
  re-added easily if a similar issue resurfaces.

### Fixed
- `!ping` reply had a string concatenation bug producing a run-together
  line (`"...in pvt"` immediately followed by `"...for more..."` with no
  space). Now reads correctly as `pls type info in pvt ... for more ...`.

### Known Issues
- Direct-message replies can fail with a `NO_CHANNEL` routing error when a
  peer node's cached public key is stale (e.g. after a firmware reflash or
  factory reset on either side). Workaround: run `--reset-nodedb` on the
  affected node and let it re-exchange node info, or remove/re-add the
  stale contact on the sending device. A more automatic fix is being
  evaluated for a future release.

---

## [1.6.0] - 2026-07-09

### Added
- `_on_ack_response` groundwork and initial ack-based delivery debugging
  (superseded/cleaned up in 1.7.0).

---

## [1.2.3] - 2026-07-XX

### Changed
- Switched transport from a hardcoded TCP host to a **serial (USB)
  connection**, with automatic port discovery (`/dev/serial/by-id/*` first,
  falling back to common `ttyACM*` / `ttyUSB*` device names).
- Added automatic reconnect with exponential backoff on connection loss,
  driven off the `meshtastic.connection.lost` event.
- Added rotating file logging (console + `meshbot.log`, capped size with
  backups) alongside the existing console output.

### Removed
- All personal/identifying data: callsign, project URL, and "created with
  ChatGPT" credit stripped from source and reply text. Bot now identifies
  generically as `MeshBot`.

---

## [1.1.0] - Initial public functionality

### Added
- Core command set: `!ping`, `!time`, `!uptime`, `!nodes`, `!info`,
  `!cmd` (help list).
- `!wargames` — small turn-based text "simulation" game with a menu state,
  5-turn active state, randomized score/events, and session timeout
  cleanup (`GAME_TIMEOUT`).
- Hidden `admin` easter-egg reply.
