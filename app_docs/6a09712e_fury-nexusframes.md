# Fury System (mod-fury) + NexusFrames addon — build write-up

What shipped: an **account-wide progression system** where every XP-eligible creature kill grants **Fury** points (party-shared, as if each member killed alone), feeding an account-leveled ladder (max **300**) whose levels grant permanent account-wide stat bonuses; plus the **NexusFrames** addon that renders the UI. Implemented exactly per the locked design (`specs/fury-nexusframes-design.md`), with the code-verified corrections below. Reviewer verdict: **APPROVED — 24/24 requirements met, no blocking items**. Nothing was committed, compiled, packed, or applied to a live DB (the run is `--no-commit`; modules are gitignored clones; the engineer builds/packs manually).

## Files that carry the change

| Path | What |
|---|---|
| `modules/mod-fury/` (gitignored, not in git status) | The server module, modeled on `modules/mod-random-enchants/` |
| `modules/mod-fury/src/fury.h` · `fury.cpp` · `fury_loader.cpp` | `FuryPlayerScript` (kill earning, login re-apply, save persistence) + `FuryCommandScript` (`.fury` addon-channel status query); loader entry `Addmod_furyScripts()` → `AddFuryScripts()` (matches CMake name derivation) |
| `modules/mod-fury/conf/fury.conf.dist` | All 13 §2.7 keys with the specified defaults, documented per-key |
| `modules/mod-fury/data/sql/db-auth/001_mod_fury_account_fury.sql` | `account_fury` DDL for **acore_auth** (exact §2.3 schema, backticked); no world SQL |
| `modules/mod-fury/README.md` + repo bits (`include.sh`, `.gitignore`, `.editorconfig`, `.gitattributes`, `.github/…`) | Standard module installer/CI scaffolding, mirrored from `mod-random-enchants` |
| `client-resources/NexusFrames/NexusFrames.toc` · `NexusFrames.lua` | Addon source (3.3.5a): micro-menu button, Fury window, progress bar, 300-entry horizontal reward list, level-up popup, addon-channel transport |
| `documentation/fury-nexusframes-handoff.md` · `documentation/README.md` (+4) | Handoff doc of verified facts/gotchas; README now links it under "Working docs" |
| `specs/fury-nexusframes-design.md` (locked design) · `specs/6a09712e_fury-nexusframes-build.md` (build plan) · `requests/fury-nexusframes-build.md` (prompt) | The spec/plan trail for this build |

## How the module works

- **Kill hook (design correction).** The design's `OnPlayerKilledByCreature(Player*, Creature*)` is inverted in this fork — `PlayerScript.h:255` is `OnPlayerKilledByCreature(Creature* killer, Player* killed)` (fires when a *player* is killed *by* a creature). The module hooks **`OnPlayerCreatureKill(Player*, Creature*)`** (`PlayerScript.h:249`, `PLAYERHOOK_ON_CREATURE_KILL`), fired per creature kill at `Unit.cpp:18138`. Core untouched.
- **Gate = XP-eligible, not XP-awarded.** A kill counts only when the victim is non-grey for the killer: `killed->GetLevel() > Acore::XP::GetGrayLevel(killer->GetLevel())` — the same mechanism `KillRewarder`/`Player::isHonorOrXPTarget` use. Max-level players still earn (no XP is ever awarded at max, so a strict awarded-XP gate would starve them).
- **Earning.** `gain = victimLevel × 5 + 10`, × `BossMultiplier` (5) for bosses (`killed->IsDungeonBoss()` — `CREATURE_FLAG_EXTRA_DUNGEON_BOSS`, set dynamically — or `rank == CREATURE_ELITE_WORLDBOSS`). In a group/raid every member within reward distance gets the full gain for their own **account** (`GetFirstMember()` loop + `IsAtGroupRewardDistance`, mirroring `KillRewarder`); a `std::set` of account ids guards against double-awarding one account twice in the same group.
- **Level curve.** `threshold(n) = CurveBase × n` (100, 200, …, 30,000); total to 300 = **4,515,000**. `CurveIncrement` is a reserved config key (v1 curve is flat +100 — only the percentage tapers).
- **Storage.** `acore_auth.account_fury` (account_id PK, fury, level), lazily populated (`INSERT … ON DUPLICATE KEY UPDATE`; no row until an account's first real write). In-memory `unordered_map<accountId, FuryAccount>` guarded by a mutex, shared across the account's online characters; account id via `WorldSession::GetAccountId()` (`WorldSession.h:429` — the design's :268 is a different class).
- **Persistence cadence.** Per kill: memory only. Level-up: immediate DB write in the level-up code path (a crash never eats a level). Periodic + logout: `OnPlayerSave` persists the shared accumulator (last-writer-wins, correct) — verified the hook fires from the logout save path (`WorldSession.cpp:756` → `PlayerStorage.cpp:7089`) and the 15-min cadence.
- **Rewards — computed from level, never accumulated.** Login re-applies full totals; level-ups apply the **delta** to every online character of the account (`sWorldSessionMgr->GetAllSessions()` filtered by account id). Per the locked rule, AP and SP are **both flat** (this fork has no spell-power % mechanic). APIs (all re-verified):
  - Haste +0.1%/level: `ApplyAttackTimePercentMod(BASE/OFF/RANGED_ATTACK, …)` + `ApplyCastTimePercentMod(…)` — the core's haste-aura wrappers (`Unit.cpp:17154/17170`), not raw `ApplyPercentModFloatValue`.
  - AP/SP +50 per 5 levels: `HandleStatModifier(UNIT_MOD_ATTACK_POWER / _RANGED, TOTAL_VALUE, …)` + `Player::ApplySpellPowerBonus(int32, bool)` (flat, `StatSystem.cpp:167`).
  - Class-primary +100 per 10 levels: `ApplyStatBuffMod(STAT_*, …)` (inline `Unit.h:1024`). Map: warrior/paladin/DK→STR, hunter/rogue→AGI, priest/shaman/mage/warlock/druid→INT, unknown→INT.
  - Item rewards: structure only (addon `FURY_ITEM_REWARDS` table + item-link renderer); level-300 item out of scope.

## Addon-channel protocol (module ⇄ addon, both sides must agree)

- **Routing:** the module registers a plain `CommandScript` with a `fury` command (SEC_PLAYER, `Console::No`) — `AddonChannelCommandHandler` routes it automatically: `ParseCommands` (`Chat.cpp:1050`, 12-byte `"AzerothCore\t"` prefix, opcode at [12], 4-char counter [13..16], command at [17]) → `_ParseCommands` → `TryExecuteCommand` → the CommandScript map. Replies flow through the handler's overridden `SendSysMessage` as LANG_ADDON whispers.
- **Wire grammar:** query `"i" + 4-char counter + "fury"`; reply `m <echo> fury:<level>:<currentFury>:<nextThreshold>:<totalFury>`; server push `m LVLU levelup:<level>:<currentFury>:<nextThreshold>:<totalFury>`. Zero-state reply is `fury:0:0:100:0`.
- **3.3.5 receive pattern:** no `RegisterAddonMessagePrefix`/`CHAT_MSG_ADDON` (Cataclysm+). The addon sends `SendAddonMessage("AzerothCore", …)` and receives via `CHAT_MSG_WHISPER` whose language is LANG_ADDON (4294967295, canonical 3rd arg — flagged for live confirmation) and whose body starts with `AzerothCore\t` (also prefix-checked as a defensive fallback). Query on window open + 45 s slow poll while open; level-up pushes arrive even with the window closed.

## The addon (`client-resources/NexusFrames/`)

- `NexusFrames.toc`: `## Interface: 30300` (3.3.5a/client 12340; no in-repo TOC existed to cross-check — flagged).
- Micro-menu button on `MicroButtonAndBagsBar`, anchored right of `HelpMicroButton`, `UI-MicroButton-Achievements` textures, tooltip "NexusFrames", toggles the window (canonical 3.3.5 frame/texture names — not verifiable in-repo, flagged).
- Window sized once at init: `screenW × 0.55` × `screenH × 0.6`, clamped 800×500–1600×1000, `SetResizable(false)`, children edge-anchored; single custom tab "Fury".
- Fury tab: `StatusBar` with `SetMinMaxValues(threshold[level], threshold[level+1])`, label `Level N — X / Y Fury`, MAX handling at 300; the **exact disclaimer line** (byte-verified, em dash included): `* Each entry shows the total bonus at that level — not an addition on top of the previous level.`; a horizontal `ScrollFrame` with one entry per level 1..300, multi-line rewards (haste / AP·SP / primary / item link), centered on the current level (offset = `(idx−1)·(width+gap)+width/2 − viewport/2`, clamped). Reward rules are generated locally from deterministic constants mirroring `fury.conf.dist`; item links render via `GameTooltip:SetHyperlink` on hover and the `SetItemRef` hook on click.
- Level-up popup: UIParent-anchored top-center, `DIALOG` strata, shows `Fury level N` + gained deltas, 4 s fade; shown regardless of window state.

## Build-time verification findings (design §5)

1. Addon-channel framing + routing — **resolved** (see protocol above; no leading dot over the channel — both sides send `"fury"`).
2. Micro-bar anchor + textures — **flagged**: canonical 3.3.5 names (`MicroButtonAndBagsBar`, `HelpMicroButton`, `UI-MicroButton-Achievements*`); not verifiable in-repo (no FrameXML sources).
3. `## Interface` — **30300**, flagged (no in-repo TOC reference; standard for 3.3.5a).
4. `OnPlayerSave` fires on logout — **confirmed** (save path `WorldSession.cpp:756` → `PlayerStorage.cpp:7089`).
5. Ranged AP mod + grey formula — **resolved**: `UNIT_MOD_ATTACK_POWER_RANGED` exists (`Unit.h:165`); gate uses `Acore::XP::GetGrayLevel` (`Formulas.h:46`).
6. `ApplySpellPowerBonus` flat — **confirmed** (`StatSystem.cpp:167`; same API as the enchant path).

## How to use / verify

1. Apply `modules/mod-fury/data/sql/db-auth/001_mod_fury_account_fury.sql` to **acore_auth** (the core SQL updater picks up `data/sql/db-auth/` automatically; statement is idempotent).
2. Build worldserver as usual (module auto-discovered by its `src/`; no module CMakeLists needed); `conf/fury.conf.dist` is auto-copied to `env/dist/etc/modules/fury.conf`.
3. Pack `client-resources/NexusFrames/` into `patch-4.MPQ` at `Interface\AddOns\NexusFrames\` (engineer does this manually; MPQ changes need a client relaunch).
4. In-game: kill an XP-eligible mob (Fury accrues in memory — no per-kill DB write), open the window (`.fury` query → bar/label/total update), trigger a level-up (top-center popup + immediate `account_fury` row + delta applied to all online characters of the account). `AddonChannel = true` is the default.
5. If you retune `fury.conf.dist`, keep the `FURY_*` constants at the top of `NexusFrames.lua` in sync (the addon generates its reward list locally) and restart the server (config is snapshotted in `AddFuryScripts`).

## Flags / notes

- The two unverifiable-in-repo items (micro-bar anchor/textures, `## Interface` 30300) are implemented per canonical 3.3.5 and flagged for live confirmation.
- The `CHAT_MSG_WHISPER` language-arg index (3rd arg = LANG_ADDON) is canonical but flagged; the `AzerothCore\t` prefix fallback makes reception robust either way.
- Everything here is source-only and uncommitted; the engineer compiles, runs, applies SQL, and packs the MPQ manually.
