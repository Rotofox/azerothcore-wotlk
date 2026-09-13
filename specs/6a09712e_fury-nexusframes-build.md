# Build Plan — Fury System (mod-fury) + NexusFrames addon

Authoritative design: `specs/fury-nexusframes-design.md` (status: **implemented** — built and shipped; every decision locked — implement as specified, do NOT re-design or re-litigate).
Verified-facts summary + gotchas: `documentation/fury-nexusframes-handoff.md`.
This plan re-verified **every line number in the code** on 2026-08-17. Where the design's line numbers were wrong, the corrected values are below in **bold** — trust these.

**MODE: `--no-commit`. NO git operations of any kind** (no add/commit/push/pull/checkout/reset/clean). No building (no cmake/make/ninja, no compiling, no worldserver/authserver, no SQL applied to any live DB, no MPQ packing, no DBC regeneration, no client verification). All work products stay in the working tree, uncommitted.

---

## 0. CRITICAL DESIGN CORRECTION (verified against the code)

**The design's kill hook is INVERTED.** `PlayerScript.h:255` is NOT `OnPlayerKilledByCreature(Player*, Creature*)`. The actual signature at that line is:

```cpp
// PlayerScript.h:255
virtual void OnPlayerKilledByCreature(Creature* /*killer*/, Player* /*killed*/) { }
```

That hook fires when a **player is killed BY a creature** (the inverse of what Fury needs). It is invoked from `Unit.cpp:18143` in the death path (`sScriptMgr->OnPlayerKilledByCreature(killerCre, killed)`).

**Use `OnPlayerCreatureKill(Player* killer, Creature* killed)` instead** — this is the hook the design's text actually describes ("fires per creature kill", killer is the player, victim is the creature):

```cpp
// PlayerScript.h:249  (enum PLAYERHOOK_ON_CREATURE_KILL at PlayerScript.h:39)
virtual void OnPlayerCreatureKill(Player* /*killer*/, Creature* /*killed*/) { }
```

Fired from `Unit.cpp:18138` (`sScriptMgr->OnPlayerCreatureKill(killerPlr, killedCre)`), in the same `Unit::DealDamage` kill path that calls `RewardPlayerAndGroupAtKill` (`Unit.cpp:17926`). Register it in the PlayerScript constructor hook list as `PLAYERHOOK_ON_CREATURE_KILL` (mirror `RandomEnchantsPlayer`'s constructor in `modules/mod-random-enchants/src/random_enchants.h:107-116`).

Do NOT "fix" the core — `src/server/game/` is out of scope. The module just hooks the correct script.

---

## 1. Verified code facts (re-verified, with corrected lines)

### Hooks
| Fact | Location (verified) |
|---|---|
| `OnPlayerCreatureKill(Player*, Creature*)` — **THE hook to use** | `src/server/game/Scripting/ScriptDefines/PlayerScript.h:249` (enum `PLAYERHOOK_ON_CREATURE_KILL` at `:39`); fired from `src/server/game/Entities/Unit/Unit.cpp:18138` |
| `OnPlayerSave(Player*)` — periodic + logout | `PlayerScript.h:350`; invoked from `Player::SaveToDB` at `src/server/game/Entities/Player/PlayerStorage.cpp:7089` (only when `!create`); `SaveToDB` is called on the periodic save path (`Player.cpp:1655`) and on logout (`src/server/game/Server/WorldSession.cpp:756`, `_player->SaveToDB(false, true)`) — **confirmed it fires on logout** |
| `OnPlayerLogin(Player*)` | `PlayerScript.h:332` |

### XP / grey-level / group (the gate mechanism)
- `Player::GiveXP` — `Player.cpp:2385` (design line correct).
- `Player::RewardPlayerAndGroupAtKill` — `Player.cpp:12764` (design line correct); delegates to `KillRewarder` (`src/server/game/Entities/Player/KillRewarder.cpp`).
- **Grey-level formula: `Acore::XP::GetGrayLevel(uint8 pl_level)` — `src/server/game/Miscellaneous/Formulas.h:46`** (inline):
  ```cpp
  if (pl_level <= 5) level = 0;
  else if (pl_level <= 39) level = pl_level - 5 - pl_level / 10;
  else if (pl_level <= 59) level = pl_level - 1 - pl_level / 5;
  else level = pl_level - 9;
  ```
- **XP-eligibility test the module must mirror** (victim is not grey for the killer):
  - `KillRewarder.cpp:105` (`uint32 grayLevel = Acore::XP::GetGrayLevel(lvl); if (_victim->GetLevel() > grayLevel ...)`)
  - `Player.cpp:12710-12713` (`uint8 k_grey = Acore::XP::GetGrayLevel(GetLevel()); ... if (v_level <= k_grey) return;`)
  - So: **eligible ⇔ `victim->GetLevel() > Acore::XP::GetGrayLevel(killer->GetLevel())`**. Include `Formulas.h` (path: `#include "Formulas.h"`).
- **Group iteration to mirror** (from `KillRewarder::_InitGroupData`, `KillRewarder.cpp:87-100`, and `_RewardGroup`, `KillRewarder.cpp:250-260`; also `Player::RewardPlayerAndGroupAtEvent`, `Player.cpp:12782-12791`):
  ```cpp
  for (GroupReference* itr = group->GetFirstMember(); itr != nullptr; itr = itr->next())
  {
      if (Player* member = itr->GetSource())
          if (_killer == member || member->IsAtGroupRewardDistance(_victim)) { ... }
  }
  ```
  Include `Group.h`. `IsAtGroupRewardDistance` is `Player.cpp:12806` (returns true for dungeon maps; distance check `CONFIG_GROUP_XP_DISTANCE` otherwise). For Fury v1: iterate all group members (or just the killer when no group), award the **full** per-kill Fury to each (the design says "every member gains as if they killed alone" — no per-member grey check needed; the grey gate is applied to the **killer** only per design §2.1).

### Storage / account
- `WorldSession::GetAccountId()` — **`src/server/game/Server/WorldSession.h:429`** (design claimed :268 — that line is `LoginQueryHolder::GetAccountId()`; the real `WorldSession::GetAccountId()` is at :429, class `WorldSession` starts :378): `uint32 GetAccountId() const { return _accountId; }`. Call as `player->GetSession()->GetAccountId()` (verified pattern in `modules/mod-account-mounts/src/mod_account_mount.cpp:45`).
- **`LoginDatabase` global is usable from modules** — declared `src/server/database/Database/DatabaseEnv.h:41` (`extern DatabaseWorkerPool<LoginDatabaseConnection> LoginDatabase;`). Example core usage: `src/server/game/Misc/BanMgr.cpp:56,183`. Use `LoginDatabase.Query(...)` / `LoginDatabase.Execute(...)` with the modern fmt-style string API (mirror `modules/mod-random-enchants/src/random_enchants.cpp` which uses `WorldDatabase.Query("SELECT ... WHERE x = {}", arg)`).

### Boss detection
- `CREATURE_FLAG_EXTRA_DUNGEON_BOSS = 0x10000000` — `src/server/game/Entities/Creature/CreatureData.h:73`, comment "SET DYNAMICALLY, DO NOT ADD IN DB" — confirmed the core sets it dynamically. Access via `creature->HasFlagExtra(CREATURE_FLAG_EXTRA_DUNGEON_BOSS)` (see `Creature.h:118` for the `HasFlagExtra`/rank helper pattern).
- Creature rank enum: `src/server/shared/SharedDefines.h:2981-2985` — `CREATURE_ELITE_NORMAL=0, CREATURE_ELITE_ELITE=1, CREATURE_ELITE_RAREELITE=2, CREATURE_ELITE_WORLDBOSS=3, CREATURE_ELITE_RARE=4`. Creature rank via `creature->GetCreatureTemplate()->rank`.
- Victim level: `creature->GetLevel()` (uses template `minlevel/maxlevel` — `CreatureData.h:195-196`; skull bosses carry real levels).

### Stat APIs (re-verified)
| Reward | API (verified) | Detail |
|---|---|---|
| Haste % | **`Unit::ApplyAttackTimePercentMod(WeaponAttackType, float, bool)` — `Unit.cpp:17154`** and **`Unit::ApplyCastTimePercentMod(float, bool)` — `Unit.cpp:17170`** | The design's line refs (17160/17173) point INSIDE these wrappers (the `ApplyPercentModFloatValue` calls). **Do NOT call `ApplyPercentModFloatValue` directly** — the core's own haste auras call these wrappers (verified handlers: `SpellAuraEffects.cpp:4975` `HandleModCastingSpeed` [SPELL_AURA_HASTE_SPELLS 216, since this fork has NO SPELL_AURA_MOD_CAST_SPEED — 139 is SPELL_AURA_FORCE_REACTION here], `:5028` `HandleModMeleeSpeedPct` [138], `:5039` `HandleAuraModRangedHaste` [140]: `target->ApplyAttackTimePercentMod(BASE_ATTACK/OFF_ATTACK/RANGED_ATTACK, ...)` + `target->ApplyCastTimePercentMod(...)`). Call exactly like the core: `ApplyAttackTimePercentMod(BASE_ATTACK, pct, apply)`, `(OFF_ATTACK, ...)`, `(RANGED_ATTACK, ...)`, `ApplyCastTimePercentMod(pct, apply)`. `WeaponAttackType` enum: `Unit.h:208-214` (`BASE_ATTACK=0, OFF_ATTACK=1, RANGED_ATTACK=2`). |
| Flat AP | `HandleStatModifier(UnitMods, UnitModifierType, float, bool)` — `Unit.h:1016`, impl `Unit.cpp:15321` | Use `UNIT_MOD_ATTACK_POWER` (`Unit.h:164`) and `UNIT_MOD_ATTACK_POWER_RANGED` (`Unit.h:165`), modifier type **`TOTAL_VALUE`** for flat. |
| Flat SP | `Player::ApplySpellPowerBonus(int32, bool)` — `Player.h:1945` (design line correct), impl `src/server/game/Entities/Unit/StatSystem.cpp:167` | Confirmed **flat**: applies to `PLAYER_FIELD_MOD_HEALING_DONE_POS` + `PLAYER_FIELD_MOD_DAMAGE_DONE_POS` per school; handles negative amounts for removal via `_ModifyUInt32`. Same API the enchant path uses (`Player.cpp:6839`). |
| Primary stat | `ApplyStatBuffMod(Stats, float, bool)` — **inline `Unit.h:1024`** (the design cited PlayerStorage.cpp:4445, which is a *call site* of the enchant path, not the definition) | Applies to `UNIT_FIELD_POSSTAT0 + stat` (buff-style). `Stats` enum: `src/server/shared/SharedDefines.h:267-274` (`STAT_STRENGTH=0, STAT_AGILITY=1, STAT_STAMINA=2, STAT_INTELLECT=3, STAT_SPIRIT=4`). Classes enum: `SharedDefines.h:139-152` (`CLASS_WARRIOR=1, CLASS_PALADIN=2, CLASS_HUNTER=3, CLASS_ROGUE=4, CLASS_PRIEST=5, CLASS_DEATH_KNIGHT=6, CLASS_SHAMAN=7, CLASS_MAGE=8, CLASS_WARLOCK=9, CLASS_DRUID=11`). |
| Unit modifier types | `Unit.h:127-131`: `BASE_VALUE=0, BASE_PCT=1, TOTAL_VALUE=2, TOTAL_PCT=3` | Design's "BASE_PCT=1/TOTAL_PCT=3" is correct. For flat AP use `TOTAL_VALUE` (=2). |

**Class → primary stat map** (design §2.5; no core helper exists — build a static switch in the module):
warrior(1)→STR, paladin(2)→STR, hunter(3)→AGI, rogue(4)→AGI, priest(5)→INT, death knight(6)→STR, shaman(7)→INT, mage(8)→INT, warlock(9)→INT, druid(11)→INT. Unknown → INT (defensive fallback, log it).

### Config / persistence
- `AddonChannel` config — `src/server/game/World/WorldConfig.cpp:146` (design line correct): `SetConfigValue<bool>(CONFIG_ADDON_CHANNEL, "AddonChannel", true)` — default **true**.
- `PlayerSaveInterval` — `WorldConfig.cpp:160`: `SetConfigValue<uint32>(CONFIG_INTERVAL_SAVE, "PlayerSaveInterval", 900000)` (design line correct).
- `PlayerSave.Stats.SaveOnlyOnLogout` — `WorldConfig.cpp:162` (default true).
- Module config loading: `src/common/Configuration/Config.cpp:575` `LoadModulesConfigs` reads `env/dist/etc/modules/*.conf.dist` then `*.conf`; the module's `conf/fury.conf.dist` is auto-copied by CMake (`modules/CMakeLists.txt` `CopyModuleConfig`) and its filename auto-added to `CONFIG_FILE_LIST` (`modules/CMakeLists.txt:340-370`). No manual registration needed.
- Module build discovery: `GetModuleSourceList` (`src/cmake/macros/ConfigureModules.cmake:32`) globs `modules/*` and includes any dir with a `src/` subdir. Loader function name derives from the dir: `mod-fury` → **`Addmod_furyScripts()`** (see `modules/CMakeLists.txt:164-172`: `-`→`_`, `Add${name}Scripts()`). Mirror `modules/mod-random-enchants/src/RE_loader.cpp`:
  ```cpp
  void AddFuryScripts();
  void Addmod_furyScripts() { AddFuryScripts(); }
  ```
- DB pools: `LoginDatabase`=acore_auth, `CharacterDatabase`=acore_characters, `WorldDatabase`=acore_world (documentation/data-layer.md). Module SQL dirs: `data/sql/db-auth/` → acore_auth, `data/sql/db-world/` → acore_world. (mod-random-enchants ships `data/sql/db-world/*.sql`; mod-ah-bot/mod-aoe-loot use `data/sql/db-auth/base/` + `updates/` subdirs — either layout works; the design's example is `data/sql/db-auth/001_mod_fury_account_fury.sql`, use that.)

### Addon-channel protocol (fully mapped — design §2.8 + open item #1)
Server side, `src/server/game/Chat/Chat.cpp`:
- `AddonChannelCommandHandler::ParseCommands(std::string_view str)` — **Chat.cpp:1050** (design line correct):
  - `memcmp(str.data(), "AzerothCore\t", 12)` — protocol prefix is the 12 bytes `AzerothCore` + TAB.
  - `char opcode = str[12];` — opcodes: `'p'` ping, `'h'` human-readable command, `'i'` issue command.
  - `str[13..16]` — 4-character command counter (echo).
  - command text starts at `str[17]`; `_ParseCommands(str.substr(17))` dispatches it.
  - `echo = str.substr(13)` (the 4-char counter) is echoed in every reply.
- **Module commands route through it automatically**: `_ParseCommands` → `ChatHandler::_ParseCommands` (`Chat.cpp:228`) → `Acore::ChatCommands::TryExecuteCommand` (`ChatCommand.cpp:274/532`) → top-level command map which includes **all `CommandScript`-registered commands** (`ChatCommand.cpp:84`: `LoadCommandsIntoMap(nullptr, COMMAND_MAP, sScriptMgr->GetChatCommands())`). So the module registers a plain **CommandScript** with a `fury` command (SEC_PLAYER, Console::No) — exactly like `modules/mod-autobalance/src/ABCommandScript.cpp` — and the addon channel routes `.fury` to it with no extra registration. `CommandScript` base: `src/server/game/Scripting/ScriptDefines/CommandScript.h:24-31` (`GetCommands()` returns `ChatCommandTable`).
- Client→server reception: `src/server/game/Handlers/ChatHandler.cpp` (`WorldSession::HandleMessagechatOpcode`) — at **:286-288**: `if (lang == LANG_ADDON) { if (AddonChannelCommandHandler(this).ParseCommands(msg.c_str())) return; }`. LANG_ADDON validity at `:172-184` (requires `CONFIG_ADDON_CHANNEL` true; type must be PARTY/RAID/GUILD/BATTLEGROUND/WHISPER). `LANG_ADDON = 0xFFFFFFFF` (`SharedDefines.h:764`); `CHAT_MSG_ADDON = 0xFFFFFFFF` (`SharedDefines.h:3401`).
- Server→client replies: `AddonChannelCommandHandler::Send` — `Chat.cpp:1091-1096`:
  ```cpp
  WorldPacket data;
  ChatHandler::BuildChatPacket(data, CHAT_MSG_WHISPER, LANG_ADDON, GetSession()->GetPlayer(), GetSession()->GetPlayer(), msg);
  GetSession()->SendPacket(&data);
  ```
  Reply frames: `"AzerothCore\ta"+echo` ack (`:1098`), `"AzerothCore\to"+echo` ok (`:1109`), `"AzerothCore\tf"+echo` fail (`:1119`), `"AzerothCore\tm"+echo+body` message (`:1130` — `SendSysMessage`). `BuildChatPacket` is a public static (`Chat.h:258`-ish / `Chat.cpp:261`).
- **Client receive pattern (WotLK)**: the addon sends `SendAddonMessage(prefix, message, channel, target)`; in 3.3.5 the wire body becomes `prefix.."\t"..message` (that is why the server checks for `AzerothCore\t`). The client **receives** replies as `CHAT_MSG_WHISPER` with the addon-language flag (language == `4294967295`/`0xFFFFFFFF`); `RegisterAddonMessagePrefix`/`CHAT_MSG_ADDON` events are **4.1+/Cataclysm and do NOT exist in 3.3.5**. The addon registers `CHAT_MSG_WHISPER` and detects addon-channel messages by the language argument (canonical 3.3.5 pattern: the 3rd arg of `CHAT_MSG_WHISPER` is the language; addon messages arrive with language `4294967295` — flag in the build report that this arg index must be confirmed live; the fallback is prefix-match on the body starting with `"AzerothCore\t"`).

---

## 2. Deliverable 1 — Server module `modules/mod-fury/`

Mirror `modules/mod-random-enchants/` layout. Files to create:

```
modules/mod-fury/
├── README.md                      # standard module readme (mirror mod-random-enchants README shape)
├── include.sh                     # empty (mirror mod-random-enchants — it's empty there)
├── .gitignore                     # mirror mod-random-enchants .gitignore (module repos are gitignored clones)
├── .editorconfig                  # mirror mod-random-enchants
├── .gitattributes                 # mirror mod-random-enchants
├── .github/
│   ├── workflows/core-build.yml   # mirror mod-random-enchants (uses azerothcore reusable workflow)
│   ├── README.md
│   ├── pull_request_template.md
│   └── ISSUE_TEMPLATE/{bug_report.yml, feature_request.yml}
├── conf/
│   ├── .gitkeep
│   └── fury.conf.dist             # §2.7 keys — see below
├── data/
│   ├── .gitkeep
│   └── sql/db-auth/001_mod_fury_account_fury.sql   # acore_auth DDL — see below
└── src/
    ├── fury.h                     # FuryPlayerScript + helpers (class decl), AddFuryScripts()
    ├── fury.cpp                   # implementation
    └── fury_loader.cpp            # Addmod_furyScripts() -> AddFuryScripts()
```

### 2.1 Config `conf/fury.conf.dist` — EXACT keys (§2.7, all tunable; build first, balance later)

```
[worldserver]
Fury.Enable = 1
Fury.FuryPerLevelBase = 5
Fury.FuryPerLevelBonus = 10
Fury.BossMultiplier = 5
Fury.CurveBase = 100
Fury.CurveIncrement = 100
Fury.MaxLevel = 300
Fury.HastePerLevelPct = 0.1
Fury.APPerMilestone = 50
Fury.SPPerMilestone = 50
Fury.APSPEveryNLevels = 5
Fury.PrimaryPerMilestone = 100
Fury.PrimaryEveryNLevels = 10
```
Format the .dist file in the module's comment style (see `modules/mod-random-enchants/conf/random_enchants.conf.dist`): header block, one commented section per key with `# Default:` line, `[worldserver]` section header first.

### 2.2 SQL `data/sql/db-auth/001_mod_fury_account_fury.sql`

Exact DDL from design §2.3 (do not rename columns; backtick identifiers — MySQL 8 gotcha):

```sql
CREATE TABLE IF NOT EXISTS `account_fury` (
  `account_id` INT UNSIGNED NOT NULL,
  `fury` BIGINT UNSIGNED NOT NULL DEFAULT 0,
  `level` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (`account_id`)
) ENGINE=InnoDB;
```

Add the module's standard header comment (mirror `001_mod_re_rates.sql` style: design source ref, idempotency note). **No world SQL** (the design needs none).

### 2.3 Module design (fury.cpp)

Header includes: `ScriptMgr.h`, `Player.h`, `Creature.h`, `Group.h`, `DatabaseEnv.h`, `Formulas.h`, `Chat.h`, `Configuration/Config.h`, `<unordered_map>`, `<mutex>`, `<cmath>`.

**In-memory cache** (shared across the account's online characters):
```cpp
struct FuryAccount { uint64 fury = 0; uint16 level = 0; };
std::unordered_map<uint32, FuryAccount> g_furyCache;   // key = account id
std::mutex g_furyMutex;                                 // guard the cache
```
Note: AzerothCore world threads are largely single-threaded per map but kills/saves can come from multiple map threads — use a mutex (cheap, correct).

**Config reads** — mirror `sConfigMgr->GetOption<T>("Key", default)`:
```cpp
bool enabled = sConfigMgr->GetOption<bool>("Fury.Enable", true);
uint32 base = sConfigMgr->GetOption<uint32>("Fury.FuryPerLevelBase", 5);
uint32 bonus = sConfigMgr->GetOption<uint32>("Fury.FuryPerLevelBonus", 10);
uint32 bossMult = sConfigMgr->GetOption<uint32>("Fury.BossMultiplier", 5);
uint32 curveBase = sConfigMgr->GetOption<uint32>("Fury.CurveBase", 100);
uint32 curveInc = sConfigMgr->GetOption<uint32>("Fury.CurveIncrement", 100);
uint32 maxLevel = sConfigMgr->GetOption<uint32>("Fury.MaxLevel", 300);
float hastePerLevel = sConfigMgr->GetOption<float>("Fury.HastePerLevelPct", 0.1f);
uint32 apPerMs = sConfigMgr->GetOption<uint32>("Fury.APPerMilestone", 50);
uint32 spPerMs = sConfigMgr->GetOption<uint32>("Fury.SPPerMilestone", 50);
uint32 apspEvery = sConfigMgr->GetOption<uint32>("Fury.APSPEveryNLevels", 5);
uint32 primPerMs = sConfigMgr->GetOption<uint32>("Fury.PrimaryPerMilestone", 100);
uint32 primEvery = sConfigMgr->GetOption<uint32>("Fury.PrimaryEveryNLevels", 10);
```

**Level curve (design §2.2):**
```cpp
uint64 ThresholdForLevel(uint32 level) { return uint64(curveBase) * level; }               // threshold(n)=100n
uint64 TotalFuryForLevel(uint32 level) { /* sum_{i=1..level} curveBase*i ... */ }
```
`threshold(n) = CurveBase × n` (design: 100×n; 0→1=100, …, 299→300=30,000; total to 300 = 4,515,000). Keep `CurveBase`/`CurveIncrement` as config keys even though v1 formula is flat +100 (the design specifies these keys; increment is 100 — the "taper" is percentage-only; implement `threshold(n) = CurveBase × n`; note `CurveIncrement` is read but the curve formula is `CurveBase*n` per design — flag in build report if you interpret otherwise).

**Kill handler** (`OnPlayerCreatureKill(Player* killer, Creature* killed)`):
1. `if (!enabled || !killer || !killed) return;`
2. **Gate — XP-eligible:** `if (killed->GetLevel() <= Acore::XP::GetGrayLevel(killer->GetLevel())) return;` (non-grey only; NOT whether XP was awarded — max-level players still earn).
3. `bool boss = killed->HasFlagExtra(CREATURE_FLAG_EXTRA_DUNGEON_BOSS);` (or `rank == CREATURE_ELITE_WORLDBOSS` / `CREATURE_ELITE_ELITE` as a secondary signal — design says "and/or"; use the flag as primary).
4. `uint64 gain = (uint64(killed->GetLevel()) * base + bonus) * (boss ? bossMult : 1);` — i.e. `(victimLevel×5+10) × bossMultiplier`.
5. `uint32 accountId = killer->GetSession()->GetAccountId();` — lazily `INSERT ... ON DUPLICATE KEY UPDATE` semantics: on first touch, load from `LoginDatabase.Query("SELECT fury, level FROM account_fury WHERE account_id = {}", accountId)`; if absent, create cache entry (fury=0, level=0) — the row itself is inserted on first **save** (see §2.4), or immediately on first kill if you prefer (design: "Lazily inserted on the first kill" — do the INSERT inside the level-up/save path; simplest correct approach: cache-miss loads from DB, and the first `SaveToDB`-time persist uses `INSERT ... ON DUPLICATE KEY UPDATE` so no row exists until the first write).
6. Add `gain` to cache fury; then level-up loop:
   ```cpp
   while (acc.level < maxLevel && acc.fury >= ThresholdForLevel(acc.level + 1))
   {
       acc.fury -= ThresholdForLevel(acc.level + 1);
       acc.level += 1;
       // §2.6 level-up flow (below)
   }
   ```
   (Design §2.6 step 1 says `level = level+1` in cache + **immediate DB write** — see below.)
7. **Group sharing:** if `killer->GetGroup()`, iterate members exactly like `KillRewarder` (`GetFirstMember()` loop + `IsAtGroupRewardDistance`) and add the **same gain** to each member's account cache (a member may be a different account — each member's account gets its own Fury). If no group, only the killer's account. Each member's account processes its own level-ups. (Careful: a group can contain characters of the same account — adding twice to the same account cache entry would double-count. Guard: track which accountIds already received this kill in a small local set, or per-kill iterate `std::set<uint32>` of processed account ids.)
8. Per kill: **memory only — never a DB write per kill.**

**Level-up flow (§2.6)** — run inside the level-up loop for each leveled account:
1. `acc.level += 1`; **immediate DB write**: `LoginDatabase.Execute("INSERT INTO account_fury (account_id, fury, level) VALUES ({}, {}, {}) ON DUPLICATE KEY UPDATE fury = VALUES(fury), level = VALUES(level)", accountId, acc.fury, acc.level)` (fmt-style API — verify `Execute` takes format+args in this fork, mirror `BanMgr.cpp:183`).
2. Compute old/new reward totals (from level and new level), apply the **delta** to **every online character of that account**. Finding online characters of an account: iterate `sWorld->GetPlayerSessions()` (or `SessionMap`) and match `session->GetAccountId() == accountId` — verify the exact accessor in this fork (`World.h` / `World.cpp` — `sWorld->GetPlayerSessions()` returns `SessionMap` of `WorldSession*`; include `World.h`). For each matching online player, apply deltas via:
   - Haste: `hasteDelta = hastePerLevel * (newLevel - oldLevel)`; `player->ApplyAttackTimePercentMod(BASE_ATTACK, hasteDelta, true)`, `(OFF_ATTACK, ...)`, `(RANGED_ATTACK, ...)`, `player->ApplyCastTimePercentMod(hasteDelta, true)`.
   - AP: `apDelta = apPerMs * (newLevel/apsapEvery - oldLevel/apsapEvery)` (integer floor division); `player->HandleStatModifier(UNIT_MOD_ATTACK_POWER, TOTAL_VALUE, float(apDelta), true)` + `(UNIT_MOD_ATTACK_POWER_RANGED, ...)`.
   - SP: `spDelta = spPerMs * (newLevel/apsapEvery - oldLevel/apsapEvery)`; `player->ApplySpellPowerBonus(int32(spDelta), true)`.
   - Primary: `primDelta = primPerMs * (newLevel/primEvery - oldLevel/primEvery)`; `player->ApplyStatBuffMod(primaryStatForClass(player->getClass()), float(primDelta), true)`.
3. **Push a level-up notification** to the client over the addon channel so the popup/window update even when the window is closed: for each online player of the account, build `"AzerothCore\tm" + "LVLU" (fixed 4-char counter) + body` and send via `ChatHandler::BuildChatPacket(data, CHAT_MSG_WHISPER, LANG_ADDON, player->GetGUID(), player->GetGUID(), msg)` + `player->GetSession()->SendPacket(&data)` (mirror `AddonChannelCommandHandler::Send`, Chat.cpp:1091-1096). Body format (design §2.8): `level,currentFury,nextThreshold,totalFury` — e.g. `"levelup:5:250:600:4515000"` (pick a stable, documented framing; the addon parses it). **Define the exact body grammar in the build report** and mirror it in the addon.

**Login** (`OnPlayerLogin`): load/refresh cache for the player's account (query if not cached), then apply **full** rewards computed from the account level (haste, AP/SP, primary — same APIs with `apply=true`). No removal on logout (mods die with the Player object).

**Save** (`OnPlayerSave`): persist the player's account cache entry to `account_fury` (INSERT … ON DUPLICATE KEY UPDATE). Last-writer-wins is correct (all online characters of the account share the same cache entry).

**Addon command** — `fury_commandscript : public CommandScript` (mirror `ABCommandScript.cpp`):
- `GetCommands()` returns `{ { "fury", HandleFuryCommand, SEC_PLAYER, Console::No } }`.
- `HandleFuryCommand(ChatHandler* handler, const char* /*args*/)`:
  - Get player from `handler->GetPlayer()`; read account cache (load from DB if missing); compute `nextThreshold = ThresholdForLevel(level+1)` (or 0 at max), `totalFury = TotalFuryForLevel(level)` (design §2.8 response: `level, currentFury, nextThreshold, totalFury`).
  - Reply over the addon channel: `handler->PSendSysMessage("fury:{}:{}:{}:{}", level, fury, nextThreshold, totalFury)` — when invoked via the addon channel, `handler` **is** the `AddonChannelCommandHandler`, so `PSendSysMessage` flows through its `SendSysMessage` → `"AzerothCore\tm"+echo+body` → LANG_ADDON whisper (verified: `Chat.h:299-312` shows `AddonChannelCommandHandler` overrides `SendSysMessage`). Note the same `.fury` command also works in chat for debugging.
  - Registration: `new FuryCommandScript();` inside `AddFuryScripts()` (CommandScript self-registers via constructor).

**`AddFuryScripts()`** (called from `fury_loader.cpp`): `new FuryPlayer(); new FuryCommandScript();` + a startup `LOG_INFO("module", "Fury: enabled, max level {}, ...")` mirroring `AddRandomEnchantsScripts` (`random_enchants.cpp:362-376`).

**C++17 / conventions**: 4-space indent, `{}` formatting for log/query strings, braces on their own lines, `uint32/uint64` typedefs (no `std::uint32_t` in headers where core uses uint32), no `using namespace`. Keep `fury.h` minimal (class decls + `AddFuryScripts()`), implementation in `fury.cpp`.

---

## 3. Deliverable 2 — Addon `client-resources/NexusFrames/`

**SOURCE ONLY.** Two files: `NexusFrames.toc` + `NexusFrames.lua`. No MPQ packing (engineer packs into `patch-4.MPQ` at `Interface\AddOns\NexusFrames\`). Do NOT touch `Item.dbc`, `SpellItemEnchantment.dbc`, or the generator scripts.

### 3.1 `NexusFrames.toc`
```
## Interface: 30300
## Title: NexusFrames
## Notes: Fury account progression UI
## Author: (server name)
## Version: 1.0
## SavedVariables: NexusFramesDB
NexusFrames.lua
```
**Open item #3 — Interface value:** the repo has **no existing addon/TOC** to confirm against. Evidence: the fork is WoW 3.3.5a / client build 12340 (`documentation/project-overview.md:6,81`). The standard interface number for 3.3.5a is **30300** — use it and flag in the build report that it was taken from standard 3.3.5 knowledge (no in-repo TOC existed to cross-check).

### 3.2 `NexusFrames.lua` — structure (design §3)

**Micro-menu button (§3.2):**
- Create `CreateFrame("Button", "NexusFramesButton", MicroButtonAndBagsBar)`.
- **Open item #2:** no in-repo evidence for the exact micro-bar frame/texture ids. Canonical 3.3.5 facts (flag in build report): parent frame `MicroButtonAndBagsBar` (exists in 3.3.5; holds the micro buttons and bag buttons); the existing micro buttons are named `CharacterMicroButton`, `SpellbookMicroButton`, `TalentMicroButton`, `QuestLogMicroButton`, `GuildMicroButton`, `LFDMicroButton`, `MainMenuMicroButton`, `HelpMicroButton`, arranged left→right; the rightmost is `HelpMicroButton`. Anchor the new button to the **right of `HelpMicroButton`** (`NexusFramesButton:SetPoint("LEFT", HelpMicroButton, "RIGHT", 1, 0)`), or to `MicroButtonAndBagsBar` top-right if that overlaps the bag bar — decide at build, flag the choice. Texture: reuse an existing `Interface\Buttons\UI-MicroButton-*` texture (e.g. `UI-MicroButton-Achievements`/`UI-MicroButton-QuestLog` normal+`Pushed`+`Highlight` states) since no new texture can ship without an MPQ art patch; `SetNormalTexture/SetPushedTexture/SetHighlightTexture`. Tooltip "NexusFrames" via `GameTooltip` on enter (mirror standard micro-button tooltip pattern; register `OnEnter`/`OnLeave` or use `this:SetScript`).
- Click toggles the window (show/hide; query server state on open).

**Window (§3.3):**
- Sized once at init: `local w = GetScreenWidth() * 0.55; local h = GetScreenHeight() * 0.6;` clamp (e.g. min 800×500, max 1600×1000 — pick sensible clamps, note in report); `SetResizable(false)`. Anchor center of screen (`UIParent`, `CENTER`). Children anchored to frame edges (top bar / tab strip / content) so it scales with resolution.
- Tab strip: custom tab buttons (`CreateFrame("Button", nil, frame, "UIFrameTemplate")`), first and only tab **Fury** (highlight selected; others grayed/absent).

**Fury tab (§3.4):**
- Top `StatusBar` (create `CreateFrame("StatusBar", nil, frame)`, `SetStatusBarTexture("Interface\\TargetingFrame\\UI-StatusBar")`, `SetMinMaxValues(threshold[level], threshold[level+1])`, `SetValue(currentFury)`, label text `Level N — X / Y Fury`). At level 300 (max): `SetMinMaxValues(0,1)`, `SetValue(1)`, label `Level 300 — MAX` (design: "full/MAX handling at level 300").
- **Disclaimer line below the bar — EXACT wording (do not paraphrase):**
  ```
  * Each entry shows the total bonus at that level — not an addition on top of the previous level.
  ```
- Below that: a **horizontal** `ScrollFrame` with one entry per level 1..300, multi-line rewards, **centered on the current level**: `scrollOffset = currentEntry × entryWidth − viewportWidth/2`, clamped. Entries are buttons (or `FontString` sets) sized `entryWidth` (e.g. 120px) × `entryHeight` (e.g. 90px); content per level:
  - `Level N`
  - Haste line: `+0.1% Haste` × N → `+{0.1*N}% Haste` (format: `+{N*0.1:g}% Haste`)
  - AP/SP line: `+{50*floor(N/5)} AP / +{50*floor(N/5)} SP` (show only if floor(N/5) > 0)
  - Primary line: `+{100*floor(N/10)} {PrimaryStatName}` (show only if floor(N/10) > 0) — name per the player's own class (warrior/paladin/dk→Strength, hunter/rogue→Agility, priest/shaman/mage/warlock/druid→Intellect); since the addon knows the local player's class (`UnitClass("player")`), render the correct name.
  - Item reward line (extensible): if the level has an item reward in a local table (v1: empty), render a standard item link `|cff...|Hitem:ID:0:0:0:0:0:0:0|h[name]|h|r` — structure the reward table as `{ [level] = { rewards } }` where a reward can be `{item = id}` or `{item = id, name = "..."}`; render via `GameTooltip:SetHyperlink` on hover and hook `SetItemRef` for click (standard 3.3.5 item-link click handling: `SetItemRef(link, text, button, chatFrame)`). **Level-300 item is NOT in scope — structure only.**
- Reward table generated **locally** from the deterministic rules (server only sends live state: level, currentFury, next, total).

**Level-up popup (§3.5):** transient `UIParent`-anchored frame at **top-center** (DBM-style), high strata (`SetFrameStrata("DIALOG")`), text `Fury level N — +X` (list the gained deltas, e.g. `+0.1% Haste` / `+50 AP +50 SP` etc.), fade out via `UIFrameFadeOut` or an `OnUpdate` alpha ramp (a few seconds), shown regardless of window state. Triggered by the server's level-up push (`LVLU` frame).

**Transport (§3.6):**
- Send: `SendAddonMessage("AzerothCore", opcode .. counter .. command, "WHISPER", UnitName("player"))` — wire body becomes `AzerothCore\t` + opcode + 4-char counter + command. Use opcode `'i'` and a 4-char monotonic counter (`string.format("%04d", counter)`), command `.fury` for the status query. Query on window open; optional slow poll (30–60 s) while open (OnUpdate timer).
- Receive: register `CHAT_MSG_WHISPER`; detect addon messages via the language flag (`language == 4294967295`, i.e. LANG_ADDON; **verify arg index at build — canonical 3.3.5 puts language as 3rd arg**; fallback: body starts with `"AzerothCore\t"`); parse `AzerothCore\t` + opcode + 4-char counter + body; handle `'m'` (message): body `fury:...` → update bar/entries; body `levelup:...` → update + popup. Ignore `a/o/f` ack/fail frames (or use them for debugging).
- Keep the parsed grammar identical on both sides (document it in the build report).

---

## 4. Build-time verification items — resolved findings (design §5)

| # | Item | Finding (verified this run) |
|---|---|---|
| 1 | Addon-channel framing + command routing | **RESOLVED.** Prefix = 12 bytes `"AzerothCore\t"`, opcode at [12] (`p`/`h`/`i`), 4-char counter [13..16], command at [17]. Module commands route through `AddonChannelCommandHandler::ParseCommands` → `_ParseCommands` → `TryExecuteCommand` → CommandScript map automatically (Chat.cpp:1050, Chat.cpp:228, ChatCommand.cpp:274/84). Replies: `BuildChatPacket(CHAT_MSG_WHISPER, LANG_ADDON, ...)` (Chat.cpp:1091-1096). |
| 2 | Micro-bar anchor + textures | **NOT verifiable in-repo** (no addon/FrameXML sources). Use canonical 3.3.5: parent `MicroButtonAndBagsBar`, anchor right of `HelpMicroButton`, textures `Interface\Buttons\UI-MicroButton-*`. Flag in report. |
| 3 | `## Interface` value | **30300** for 3.3.5a (client 12340 per docs). No in-repo TOC to cross-check; standard value. Flag in report. |
| 4 | `OnPlayerSave` fires on logout | **CONFIRMED.** `Player::SaveToDB` (PlayerStorage.cpp:7089, guard `if (!create)`) fires `OnPlayerSave`; `SaveToDB(false, true)` is called on logout (WorldSession.cpp:756) and on the periodic cadence (PlayerUpdates.cpp:321-331; `PlayerSaveInterval`=900000, WorldConfig.cpp:160; `PlayerSave.Stats.SaveOnlyOnLogout`=true at :162). |
| 5 | Ranged AP mod + grey formula | **RESOLVED.** `UNIT_MOD_ATTACK_POWER_RANGED` = Unit.h:165 (exists). Grey formula: `Acore::XP::GetGrayLevel` (Formulas.h:46); eligibility gates: `BaseGain` zeroes XP when `mob_level <= gray_level` (Formulas.cpp:58-62); group 'max not-gray member' gate (KillRewarder.cpp:105-106); per-member zero/half gate (KillRewarder.cpp:154-158). Module gate: `victim->GetLevel() > Acore::XP::GetGrayLevel(killer->GetLevel())`. |
| 6 | `ApplySpellPowerBonus` flat | **CONFIRMED FLAT.** StatSystem.cpp:167 — adds flat amount to `PLAYER_FIELD_MOD_HEALING_DONE_POS` + per-school `PLAYER_FIELD_MOD_DAMAGE_DONE_POS`; same API the item enchant path uses (Player.cpp:6839). |

**Additional corrections found (beyond design §5):**
- **Kill hook inverted** — use `OnPlayerCreatureKill` (PlayerScript.h:249), NOT `OnPlayerKilledByCreature` (PlayerScript.h:255 = player killed BY creature). (§0 above.)
- **Haste application**: use `ApplyAttackTimePercentMod` (Unit.cpp:17154)/`ApplyCastTimePercentMod` (Unit.cpp:17170) wrappers, not raw `ApplyPercentModFloatValue` — that's what the core's haste auras call (SpellAuraEffects.cpp:4975/5028/5039). Note `UNIT_MOD_CAST_SPEED` is an update-field offset (UpdateFields.h:137), not a UnitMods enum member — the wrapper handles it.
- **`ApplyStatBuffMod` is defined inline at Unit.h:1024** (PlayerStorage.cpp:4445 is a call site, not the definition).
- **`UnitModifierType` enum values** (Unit.h:127-131): `BASE_VALUE=0, BASE_PCT=1, TOTAL_VALUE=2, TOTAL_PCT=3` — use `TOTAL_VALUE` for flat AP.

---

## 5. Constraints (hard)

- **NO git operations at all** (`--no-commit` mode).
- **NO build**: no cmake/make/ninja, no C++ compile or syntax check via any toolchain, no starting worldserver/authserver, no SQL applied to any live DB, no MPQ packing, no DBC regeneration, no client-side verification. Sanity-check C++ by reading against the APIs above.
- **No changes to `src/server/game/`** (everything rides existing hooks/APIs).
- Do not touch `client-resources/Item.dbc`, `client-resources/SpellItemEnchantment.dbc`, or the generator scripts.
- Modules are gitignored clones — no commits (standing rule).
- MySQL 8: backtick identifiers in any ad-hoc SQL; no `rank` column name.
- SP% is impossible in this fork (no `SPELL_AURA_MOD_SPELL_POWER_PCT`) — AP and SP are both **flat** (locked decision).

## 6. Done means

- `modules/mod-fury/` exists: `src/{fury.h, fury.cpp, fury_loader.cpp}`, `conf/fury.conf.dist` (all 13 §2.7 keys), `data/sql/db-auth/001_mod_fury_account_fury.sql` (exact §2.3 DDL), README + repo bits mirroring `mod-random-enchants`. No world SQL.
- `client-resources/NexusFrames/{NexusFrames.toc, NexusFrames.lua}` implementing design §3 fully, including the **exact disclaimer line**.
- Coherent C++17 (AzerothCore module conventions) + valid 3.3.5 Lua; no core changes; no git; nothing compiled/built/packed/applied.
- Build report lists every verification finding (esp. §4 table), the wire grammar, the micro-bar/anchor/TOC assumptions flagged, and the hook correction.

## 7. Out of scope (do not do)

Balance tuning; the level-300 item reward (structure only); honor-based Fury; core `src/server/game/` changes; the client DBC patches + generators; MPQ packing; applying SQL; running/compiling the server; ANY git operation.
