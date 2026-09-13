--
-- QoL: +50% pet and guardian base stats (all 35 pet_levelstats entries, all levels, 2800 rows).
--
-- pet_levelstats is the single source of every pet's and temporary guardian's base pool:
-- Guardian::InitStatsForLevel() reads it per creature entry (all hunter pets share entry 1,
-- summon pets use their own creature entry). Pets/guardians without a row fall back to
-- creature_classlevelstats and are therefore NOT affected by this file.
--
-- The other half of the change - how much stamina / armor / damage a pet inherits from its
-- master - lives in the per-class spell scaling scripts and ships in the same change set.
--
-- WARNING: this is a RELATIVE update: it multiplies whatever values are present when it runs.
-- Apply it once (the DB updater records the revision) - re-running it compounds the buff.
--
-- The str/agi/sta/inte/spi columns are intentionally NOT scaled: Guardian::UpdateMaxHealth()
-- and UpdateMaxPower() use (GetStat - GetCreateStat), so base stats are subtracted out and
-- scaling them would change nothing but the pet sheet.

UPDATE `pet_levelstats` SET
    `hp` = ROUND(`hp` * 1.5),
    `mana` = ROUND(`mana` * 1.5),
    `armor` = ROUND(`armor` * 1.5),
    `min_dmg` = ROUND(`min_dmg` * 1.5),
    `max_dmg` = ROUND(`max_dmg` * 1.5);
