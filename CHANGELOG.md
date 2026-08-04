# MeshBot 9A3WHY - Changelog

Scope note: this changelog covers the **serial-only** Meshtastic bot
(`pingbot_9A3WHY_*.py`, connects via `SerialInterface` over USB). It does
**not** cover the MeshMonitor / MeshToad Docker + TCP stack described in
`MeshMonitor_MeshToad_Handoff.md` - that is a separate, unrelated
deployment (web dashboard talking to `meshtasticd` over TCP:4403) and is
out of scope for this project going forward, per request.

Two lines of development fed into this history:
- **Main line**: v1.0.0 -> v1.1.0 -> v1.2.1 -> v1.2.2 -> v1.2.3 -> v1.3.0
  -> v1.6.0 -> v1.7.0 -> **v2.0.0-beta**
- **Parallel branch (v1.2.5)**: produced by a different AI session working
  from an earlier snapshot. It re-introduced a bug that the main line had
  already fixed and dropped persistent logging. It was **not** merged
  forward - see its entry below for details.

---

## v2.0.0-beta (this release)

Built on top of v1.7.0 (main line), not v1.2.5. Adds the feature set from
`Meshtastic_rPi_Bot_Project_Export.md` that had never actually been coded
yet (it was documented but only the two easter eggs and hidden-command
behavior existed in outline form), plus general cleanup.

**New commands**
- `monitor` (now shown in `!cmd`, matching spec) - node ID, current time,
  bot process uptime, host system uptime, mesh node count, active game
  count, RAM %, CPU load average, CPU temperature, disk usage, time since
  last packet, and running packet/reply counters.
- `stats` - messages received, replies sent, most-used command, most
  active node, and games started/completed/quit.
- `lastheard` - the 5 most recently heard mesh nodes with short name and
  "Xm/Xs/Xh ago", read from `iface.nodes[...]["lastHeard"]`.
- `dice`, `coin`, `fortune`, `joke`, `quote`, `motd` - small fun/utility
  commands, each pulling from a short list of original, non-copyrighted
  lines.
- `help` added as an alias for `cmd` (both return the same command list).

**Wargames overhaul** (was a stub 3-choice loop with placeholder text;
now matches the spec in `Meshtastic_rPi_Bot_Project_Export.md`)
- Intro/outro text now matches the requested *WarGames*-style copy exactly
  ("GREETINGS PROFESSOR 9A3WHY... SHALL WE PLAY A GAME?" /
  "THE ONLY WINNING MOVE IS NOT TO PLAY...").
- Three selectable theaters (GLOBAL STRATEGY / EUROPEAN THEATER / PACIFIC
  COMMAND), each with its own flavor-text event pool. All content stays
  abstract/fictional - no real countries, units, or weapons are named, in
  keeping with the "no real military simulation, encourage diplomacy"
  requirement.
- Added a `tension` meter (0-100) instead of the old generic `score`.
  Choice A (open channel) lowers tension, C (show of force) raises it,
  B (gather intel) is roughly neutral - so diplomacy is mechanically
  rewarded without forbidding the other options.
- Ending text now varies with both the final tension level and the
  player's dominant choice across the session (a light form of the
  "branch based on previous choices" requirement), while always keeping
  the same non-violent, anti-escalation closing message.
- `!wargames` remains hidden from `!cmd`/`!help`, as specified.
- Added the `amir`, `list games`, and callsign (`9A3WHY`) easter eggs from
  the spec doc (previously only `admin` existed in code). Typing the
  callsign is now a secret alias for `!wargames`.
- Added `leave` to the quit-word list (was `quit`/`exit`/`abort` only).
- `GAME_TIMEOUT` raised from 300s to 600s (~10 minutes) to match the
  "expire inactive sessions after approximately 10 minutes" requirement -
  this had drifted to 5 minutes back in v1.1.0 and was never revisited.

**Statistics / monitoring plumbing**
- New `self.stats` dict tracks packets seen, messages processed, replies
  sent, per-command usage (`Counter`), per-node message activity
  (`Counter`), last-packet timestamp, and game start/complete/abort
  counts - feeds the new `monitor` and `stats` commands.
- Game timeouts (via `cleanup_games`) now also count as an aborted game
  in stats, same as an explicit `quit`.

**Housekeeping**
- `!cmd`/`!help` output condensed from one-line-per-command to a single
  space-separated line. With 6 commands the old one-per-line format was
  fine; with 14 it wastes LoRa airtime for no benefit.
- `info` reply now folds in the `73 de 9A3WHY` / `cromesh.eu` sign-off
  described in `Meshtastic_Bot_Project_Context.md` (that text had only
  ever existed in project notes, not in any shipped version) alongside
  the existing "type !cmd" hint, so neither version of the spec is lost.
- Confirmed the stray "TCP CONNECTION (NOT SERIAL)" comment from v1.1.0
  (a leftover/incorrect comment on a call that was always
  `SerialInterface`) is gone - it had already been removed by v1.2.x, but
  the header now explicitly documents serial-only scope to prevent it
  from being reintroduced or confused with the MeshToad/TCP stack.
- Version string, callsign, and website centralized into `VERSION`,
  `CALLSIGN`, `WEBSITE` constants instead of being hardcoded in multiple
  places (`info`, wargames intro/outro, etc).
- `get_uptime()` (host/Pi uptime via `/proc/uptime`) and the new
  `get_bot_uptime()` (process uptime) are both available and both surface
  in `monitor`, since they answer different questions.
- All new system-stat helpers (`get_cpu_temp`, `get_ram_usage`,
  `get_disk_usage`, `get_load_avg`) fail soft to `"N/A"` so the bot still
  runs (e.g. for local testing off-Pi) on hosts without a thermal zone
  file, without needing any new third-party dependency (no `psutil`).

**Not implemented in this beta (deliberately deferred)**
- `weather` - needs outbound internet/API access, which conflicts with
  this bot's serial/offline field-deployment model. Left out rather than
  shipping something that silently fails without connectivity; can be
  revisited if/when a connectivity story exists for these nodes.

---

## v1.7.0

- Added `_on_ack_response()` and switched `send_reply()` to
  `wantAck=True` + `onResponse=...`. Previously "TX success" only meant
  the local node accepted the packet over serial, not that it was
  actually delivered; this adds a real over-the-air delivery signal,
  logged as `[ACK] delivered to ...` / `[ACK] FAILED (...) to ...`.

## v1.6.0

- No functional changes from v1.3.0. Moved the growing inline changelog
  out of the file header (it had become larger than the code) and
  reworded some comments for clarity. Bare-DM `sendText()` (no
  `channelIndex`) and rotating file logging both carried forward
  unchanged.

## v1.3.0

- Identical to v1.2.3 plus one clarifying comment. Confirms v1.2.3 (not
  the parallel v1.2.5 branch) is the version that continued forward.

## v1.2.5 (parallel branch - not merged forward)

Produced by a different AI engine/session working from an older snapshot
that predated the v1.2.3 hotfix below. Listed here for the record, since
it's part of the uploaded history, but it is a **regression** relative to
v1.2.3 and was correctly not carried into v1.3.0/v1.6.0/v1.7.0/v2.0.0:
- Re-introduced the "reply on the incoming channel's index" behavior that
  v1.2.3 had explicitly reverted. Since this bot's real traffic is
  PKI-encrypted direct messages with no channel field, this forces
  `channelIndex=0` on every reply, which re-encrypts it with the Primary
  channel PSK instead of PKI - the reply is sent but the recipient's
  radio can't decode it (RX works, TX "succeeds", nothing arrives).
- Dropped the rotating file logging added in v1.2.3 (back to console-only
  `print()`).

**v2.0.0-beta builds on the corrected v1.2.3 -> v1.3.0 -> v1.6.0 -> v1.7.0
line, not on v1.2.5.**

## v1.2.3 (hotfix)

- **Reverted** the v1.2.2 "reply on the incoming channel's index" change
  (see v1.2.2 below) after runtime logs showed it was based on a
  misdiagnosis and had re-broken delivery. Replies went back to bare
  direct messages (`destinationId` only, no `channelIndex`), matching
  every previously-working version.
- Added persistent logging: log lines now also go to a rotating file
  (`meshbot.log`, next to the script) in addition to the console.
- Verified on hardware: DM `!ping`/`!info` replies actually arrive at the
  sender (RX + TX + over-the-air delivery all confirmed).

## v1.2.2 (superseded by v1.2.3 above)

- Attempted fix for a TX-not-arriving bug by having replies go out on
  whatever channel index the incoming packet carried, instead of always
  channel 0. Based on a misdiagnosis (real traffic is PKI DMs with no
  channel field) and made delivery worse, not better; reverted in v1.2.3.

## v1.2.1

- Merged the earlier "connect with retry" scaffold into the full bot
  logic and extended it into real auto-reconnect (not just a
  connect-once-at-startup loop):
  - Tries `/dev/serial/by-id/*` symlinks first (stable across USB
    replugs/reboots), then falls back to common `ttyACM`/`ttyUSB` names.
  - Subscribes to meshtastic's `connection.lost` pubsub topic and
    reconnects automatically, with exponential backoff, if the radio
    disconnects while the bot is running.
  - `send_reply()` now detects a broken serial link and triggers a
    reconnect instead of logging the error and going silent.
- Fixed a string-concatenation bug in the `!ping` reply where
  `"...in pvt"` and `"... for more ..."` were glued together with no
  space between them.
- `SERIAL_PORT` (a single hardcoded path) replaced with a list of
  candidate ports.
- Minor robustness fixes: guarded `getMyUser()`/`.nodes` access, closes
  the interface cleanly on shutdown and on reconnect.

## v1.1.0

- Command list renamed from `help` to `cmd`; game command renamed from
  `game` to `wargames`.
- Fixed a score-clamping order bug (the min/max clamp was applied to the
  wrong step, allowing a stale unclamped score to be reported for one
  turn).
- `sendText()` call switched to positional-arg style for broader library
  version compatibility.
- `getMyUser()` wrapped in try/except so a slow/odd radio response can't
  crash startup.
- `GAME_TIMEOUT` changed from 600s to 300s.
- Note: this version's connect step is annotated with a comment reading
  "TCP CONNECTION (NOT SERIAL)" despite still calling `SerialInterface`
  in code - the comment was simply wrong/leftover and never reflected
  real behavior. It disappeared by v1.2.x; v2.0.0-beta's header now
  states the serial-only scope explicitly so this kind of stale comment
  doesn't resurface.

## v1.0.0

- Initial release. `SerialInterface` on a hardcoded `/dev/ttyACM0`, no
  reconnect logic, no persistent logging (console `print()` only).
- Commands: `help`, `ping` (RSSI/SNR), `time`, `uptime` (`/proc/uptime`),
  `nodes`, `info`, `game` (a 3-turn generic "stabilize the system"
  mini-game with a numeric score, no theaters/branching).
- `admin` easter egg (static joke reply, no real privileges).
