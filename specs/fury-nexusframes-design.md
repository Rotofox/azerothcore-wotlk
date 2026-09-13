# Fury System + NexusFrames — Design Spec

> **STATUS: implemented — built and shipped.** This spec is retained as the design record. For
> current state see `documentation/modules.md` and `documentation/wow-handoff.md` §2.

Status: **implemented**. Every decision below was confirmed through engineer discussion. Build the server module first (factory-shaped), then the addon (direct build).

---

## 1. System overview

An **account-wide progression system**: every XP-eligible creature kill grants **Fury** points (shared by the whole party, as if each member killed alone). Fury accumulates toward an account-leveled ladder (max **300**), where each level grants **permanent account-wide stat bonuses** that apply to every character under the account. A client addon (**NexusFrames**, MPQ-shipped) provides the UI: a micro-menu button opening a tabbed window whose first tab shows a Fury progress bar, a scrollable reward list, and a top-center level-up popup.

Flow: `kill → OnPlayerKilledByCreature → in-memory account Fury += (level×5+10) [×boss mult] → level-up check → apply reward delta to ALL online account characters → immediate DB save on level-up (+ periodic/logout save) → notify addon`.

---

## 2. Server module (new: `modules/mod-fury/`)

Follows the existing module conventions (`modules/mod-random-enchants/` is the reference: `src/`, `conf/`, `data/sql/{db-auth,db-world}/`, a loader file, no commits ever).

### 2.1 Fury earning

- **Hook:** `PlayerScript::OnPlayerKilledByCreature(Player* killer, Creature* killed)` — `src/server/game/Scripting/ScriptDefines/PlayerScript.h:255`. Fires per creature kill.
- **Gate — XP-eligible, NOT XP-awarded:** use "victim is not grey relative to the killer" (within the XP range), **not** the XP actually awarded — at max level no XP is ever awarded, so a strict gate would starve max-level players. (Verify the fork's grey-level formula at build.)
- **Formula:** `Fury = (victim level × 5 + 10) × bossMultiplier` per eligible kill, **per party member** (group/raid/dungeon: every member gains as if they killed alone).
- **Boss multiplier:** dungeon/raid bosses award more (configurable, e.g. ×5). Detect via `CREATURE_FLAG_EXTRA_DUNGEON_BOSS` (`src/server/game/Entities/Creature/CreatureData.h:73`, 0x10000000 — set dynamically by the core) and/or creature rank.
- **Skull bosses have real levels** (verified: Lich King/Malygos/Onyxia/Kel'Thuzad = 83; dungeon bosses = 37–82) — the formula uses the creature's actual `minlevel/maxlevel`.

### 2.2 Level curve

`threshold(n) = 100 × n` → level 0→1 = 100, 1→2 = 200, 2→3 = 300, … 299→300 = 30,000. Growth **percentage** tapers (100% → 50% → … → 0.33%); absolute increment stays +100. **Total Fury to reach level 300 = 4,515,000.** (Sanity: at ~410 Fury/kill (lvl-80) ≈ 11k kills; boss multipliers and party sharing accelerate it.)

### 2.3 Storage

New table in **acore_auth** (`data/sql/db-auth/`):

```sql
CREATE TABLE IF NOT EXISTS `account_fury` (
  `account_id` INT UNSIGNED NOT NULL,
  `fury` BIGINT UNSIGNED NOT NULL DEFAULT 0,
  `level` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (`account_id`)
) ENGINE=InnoDB;
```

Lazily inserted on the first kill (`INSERT … ON DUPLICATE KEY UPDATE`). Account id via `WorldSession::GetAccountId()` (`src/server/game/Server/WorldSession.h:268`). Keep an **in-memory per-account cache** in the module (keyed by account id; shared across the account's online characters).

### 2.4 Persistence cadence (mirrors XP/rep/honor — the "efficient pattern")

- **Per kill:** in-memory only. **Never a DB write per kill.**
- **On level-up:** immediate DB write, in the level-up code path (a crash must never eat a level).
- **Periodic + logout:** hook `PlayerScript::OnPlayerSave(Player*)` (`PlayerScript.h:350`) — fires on the core's save cadence (`PlayerSaveInterval = 900000` ms = 15 min, plus logout). Any online character of the account persists the shared accumulator (last-writer-wins, correct).

### 2.5 Rewards — computed from level, never accumulated

All bonuses derive from the account level at login; level-ups apply the **delta** (new minus old). This keeps re-login always correct.

| Milestone | Reward | Application API (verified) |
|---|---|---|
| Every level | +0.1% Haste (×300 = +30%) | `ApplyPercentModFloatValue(UNIT_FIELD_BASEATTACKTIME+hand, pct)` per melee hand + ranged, and `ApplyPercentModFloatValue(UNIT_MOD_CAST_SPEED, pct)` — `src/server/game/Entities/Unit/Unit.cpp:17160/17173` (the core's own haste primitives) |
| Every 5 levels | **+50 AP and +50 SP (FLAT)** — both flat because spell power has **no percentage mechanism** in this fork (no `SPELL_AURA_MOD_SPELL_POWER_PCT`); per the engineer's rule, if one can't be %, both are flat | AP: `HandleStatModifier(UNIT_MOD_ATTACK_POWER, TOTAL_VALUE, …)`; SP: `Player::ApplySpellPowerBonus(amount, apply)` (`Player.h:1945` — the same API the working matrix SP enchants use). Also apply ranged AP. |
| Every 10 levels | +100 class-primary stat (per **character's** class: warrior→Str, mage→Int…) | `ApplyStatBuffMod(STAT_*, …)` (`src/server/game/Entities/Player/PlayerStorage.cpp:4445+` — proven) |
| Any level (extensible) | **Item rewards** (level 300 item planned separately) — reward table supports `{level: [rewards]}` where a reward can be an item id; the addon renders a standard item link | — |

- **Compute-from-level formulas:** `hastePct = 0.1×level`; `apSp = 50×⌊level/5⌋` (each); `primary = 100×⌊level/10⌋` (character's own class primary).
- **Account-wide live updates:** on a level-up, apply the delta to **every online character of the account** (each with its own class primary), not just the killer.
- **Logout:** no explicit removal needed — player stat mods live on the Player object and die with it; login re-applies from the account level.

### 2.6 Level-up flow

1. `level = level+1` in the account cache; **write `account_fury` immediately**.
2. Compute old/new reward totals; apply the delta to all online account characters.
3. Push a level-up notification to the client (addon channel) so the UI popup + window update even if the window is closed.

### 2.7 Config (`conf/fury.conf.dist`, all tunable — build first, balance later)

`Fury.Enable`, `Fury.FuryPerLevelBase = 5`, `Fury.FuryPerLevelBonus = 10`, `Fury.BossMultiplier = 5`, `Fury.CurveBase = 100`, `Fury.CurveIncrement = 100`, `Fury.MaxLevel = 300`, `Fury.HastePerLevelPct = 0.1`, `Fury.APPerMilestone = 50`, `Fury.SPPerMilestone = 50`, `Fury.APSPEveryNLevels = 5`, `Fury.PrimaryPerMilestone = 100`, `Fury.PrimaryEveryNLevels = 10`.

### 2.8 Data protocol (addon ⇄ server)

- **Client→server:** the addon sends a `.fury`-family command over the **AzerothCore addon channel** (the server's `AddonChannelCommandHandler` protocol — `src/server/game/Chat/Chat.cpp:1050`: message starts with `"AzerothCore\t"` + opcode + 4-char counter + command). The module registers the command so the handler routes it. Response: `level, currentFury, nextThreshold, totalFury` (+ on level-up: push a notification).
- **Server→client:** replies are sent as LANG_ADDON whispers via the same channel.
- **WotLK receive pattern (important):** the addon receives via `CHAT_MSG_WHISPER` with the addon-language flag and parses the message body. `RegisterAddonMessagePrefix`/`CHAT_MSG_ADDON` are **4.1+ (Cataclysm)** and do **not** exist in 3.3.5.

---

## 3. NexusFrames addon (deliverables → `client-resources/`)

All addon source ships in **`client-resources/NexusFrames/`** (with build/pack instructions in the client-resources README); the packed addon lives inside **`patch-4.MPQ`** at `Interface\AddOns\NexusFrames\` so every player gets it automatically (the client loads addons from MPQs).

### 3.1 Packaging
```
client-resources/NexusFrames/
  NexusFrames.toc      (## Interface: 30300 for 3.3.5a — confirm exact value at build)
  NexusFrames.lua
```
→ packed into `patch-4.MPQ` at `Interface\AddOns\NexusFrames\*` (same archive as the two DBC patches; MPQ changes need a client relaunch).

### 3.2 Micro-menu button
A `Button` anchored to the micro bar (`MicroButtonAndBagsBar`), right of the existing micro buttons, using `Interface\Buttons\UI-MicroButton-*` textures; tooltip "NexusFrames"; toggles the window. (Exact anchor verified at build.)

### 3.3 The window
- Sized **once at init**: `width = GetScreenWidth() × 0.55`, `height = GetScreenHeight() × 0.6` (≈ half screen), clamped; `SetResizable(false)`.
- **Responsive across 720p–4k** via fraction-based sizing + children anchored to frame edges; the UI scale setting handles the rest.
- Tab strip (custom tab buttons) — first and only tab: **Fury**.

### 3.4 Fury tab
- **Top:** `StatusBar` — `SetMinMaxValues(threshold[level], threshold[level+1])` (`threshold(n)=100n`), `SetValue(currentFury)`, label "Level N — X / Y Fury"; full/MAX at 300.
- **Below the bar, a disclaimer line (exact wording):** `* Each entry shows the total bonus at that level — not an addition on top of the previous level.`
- **Below that:** a **horizontal** `ScrollFrame` with one entry per level (**1, 2, 3, … 300** — every level), **multi-line rewards** (one reward per line: haste / AP·SP / primary / item link), **centered on the current level** (scroll offset = currentEntry × entryWidth − viewport/2, clamped).
- Reward table is **generated locally** from the deterministic rules (the server only sends live state).
- **Item links:** entries can carry a standard item link (`|cff…|Hitem:…|h[name]|h|r`) — hover shows the tooltip via `GameTooltip:SetHyperlink`, click via the game's item-link machinery (`SetItemRef` hook).

### 3.5 Level-up popup
A transient `UIParent`-anchored frame at **top-center** (DBM-style), high strata, showing "Fury level N — +X" bonuses, fading out; shown **regardless of whether the window is open** (standard addon capability).

### 3.6 Transport
`SendAddonMessage("AzerothCore", <framed command>, …)` on the addon channel; receive via `CHAT_MSG_WHISPER` + LANG_ADDON parsing (see §2.8). Query on window open; server pushes level-up updates; optional slow poll (30–60 s) while open.

---

## 4. Verified technical facts (with locations)

- `OnPlayerKilledByCreature` — PlayerScript.h:255 · `OnPlayerSave` — PlayerScript.h:350
- `Player::GiveXP` — Player.cpp:2385 · `RewardPlayerAndGroupAtKill` — Player.cpp:12764 · `RewardHonor` — Player.cpp:6118
- `PlayerSaveInterval` — WorldConfig.cpp:160 (900000 ms); `PlayerSave.Stats.SaveOnlyOnLogout = true`
- Haste primitives — Unit.cpp:17160 (`UNIT_FIELD_BASEATTACKTIME`+hand) and :17173 (`UNIT_MOD_CAST_SPEED`)
- `ApplyPercentModFloatValue` exists; unit-mod percent types `BASE_PCT=1`/`TOTAL_PCT=3` — Unit.h:128–130; `UNIT_MOD_ATTACK_POWER` / `_RANGED` — Unit.h:164–165
- `Player::ApplySpellPowerBonus` / `ApplySpellDamageBonus` — Player.h:1945–1946
- `ApplyStatBuffMod` — used by the core enchant path, PlayerStorage.cpp:4445+
- Addon channel: `AddonChannelCommandHandler` — Chat.cpp:1050 (protocol prefix `"AzerothCore\t"` + opcode + 4-char counter + command); dispatch — ChatHandler.cpp:288; `AddonChannel = true` — WorldConfig.cpp:146
- Boss flag: `CREATURE_FLAG_EXTRA_DUNGEON_BOSS` — CreatureData.h:73 (0x10000000, set dynamically)
- Account id: `WorldSession::GetAccountId()` — WorldSession.h:268
- Boss internal levels verified in the live DB (Lich King = 83, etc.)

## 5. Open build-time items

1. The exact addon-channel framing constants the AC protocol expects (channel/target; how module commands route through `AddonChannelCommandHandler::_ParseCommands`).
2. The micro-bar anchor frame name + micro-button texture ids.
3. `NexusFrames.toc` `## Interface` version.
4. Confirm `OnPlayerSave` fires on logout (it fires from the save path).
5. Confirm ranged AP mod (`UNIT_MOD_ATTACK_POWER_RANGED`) + the grey-level formula for the XP-eligible gate.
6. `ApplySpellPowerBonus` behavior for flat SP (matches the working matrix enchants).

## 6. Non-goals (v1)

- Honor-based Fury (explicitly skipped).
- The level-300 item reward (planned later; the system must be prepared — extensible reward table + item-link rendering).
- No balance pass (build first, balance later).
- No core (`src/server/game/`) changes — everything rides existing hooks/APIs.
