/*
 * This file is part of the AzerothCore Project. See AUTHORS file for Copyright information
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
 * more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program. If not, see <http://www.gnu.org/licenses/>.
 */

#include "CombatPackets.h"
#include "CreatureAI.h"
#include "Log.h"
#include "ObjectAccessor.h"
#include "Opcodes.h"
#include "Player.h"
#include "SpellInfo.h"
#include "SpellMgr.h"
#include "Vehicle.h"
#include "WorldPacket.h"
#include "WorldSession.h"

// QoL (documentation/wow-handoff.md §9.2): the 3.3.5 client will not start a
// ranged auto-repeat cast (Auto Shot 75, wand Shoot 5019, ...) while the player
// is moving - it holds the cast back until movement stops. CMSG_ATTACKSWING is
// the one attack signal the client *does* send while running (melee auto-attack
// is usable on the move), so when a ranged-weapon player asks to attack a target
// inside their ranged auto-attack's reach, start that auto-repeat server-side.
// Unit::_UpdateAutoRepeatSpell then drives the shots, and the Spell.cpp movement
// exemptions for spell 75 keep it alive while the player keeps moving (kiting).
static void StartRangedAutoAttack(Player* player, Unit* victim)
{
    if (!player || !victim || !player->IsAlive() || !victim->IsAlive())
        return;

    // Already auto-shooting - never restart (a restart would fire a free shot).
    if (player->GetCurrentSpell(CURRENT_AUTOREPEAT_SPELL))
        return;

    // Needs a ranged weapon in the ranged slot.
    if (!player->GetWeaponForAttack(RANGED_ATTACK))
        return;

    // Find the player's own ranged auto-repeat spell (Auto Shot / Shoot / ...).
    SpellInfo const* autoRepeat = nullptr;
    for (auto const& [spellId, playerSpell] : player->GetSpellMap())
    {
        if (!playerSpell || playerSpell->State == PLAYERSPELL_REMOVED)
            continue;

        SpellInfo const* spellInfo = sSpellMgr->GetSpellInfo(spellId);
        if (spellInfo && spellInfo->IsAutoRepeatRangedSpell())
        {
            autoRepeat = spellInfo;
            break;
        }
    }

    if (!autoRepeat)
        return; // this class has no ranged auto-attack

    // Only for targets inside the ranged auto-attack's reach; a target that is
    // out of ranged range keeps its normal (melee) attack behaviour.
    if (!player->IsWithinDistInMap(victim, autoRepeat->GetMaxRange(false, player)))
        return;

    player->CastSpell(victim, autoRepeat, TRIGGERED_NONE);
}

void WorldSession::HandleAttackSwingOpcode(WorldPacket& recvData)
{
    ObjectGuid guid;
    recvData >> guid;

    LOG_DEBUG("network", "WORLD: Recvd CMSG_ATTACKSWING: {}", guid.ToString());

    Unit* pEnemy = ObjectAccessor::GetUnit(*_player, guid);

    if (!pEnemy)
    {
        // stop attack state at client
        _player->SendMeleeAttackStop(nullptr);
        return;
    }

    if (!_player->IsValidAttackTarget(pEnemy))
    {
        // stop attack state at client
        _player->SendMeleeAttackStop(pEnemy);
        return;
    }

    //! Client explicitly checks the following before sending CMSG_ATTACKSWING packet,
    //! so we'll place the same check here. Note that it might be possible to reuse this snippet
    //! in other places as well.
    if (Vehicle* vehicle = _player->GetVehicle())
    {
        VehicleSeatEntry const* seat = vehicle->GetSeatForPassenger(_player);
        ASSERT(seat);
        if (!(seat->m_flags & VEHICLE_SEAT_FLAG_CAN_ATTACK))
        {
            _player->SendMeleeAttackStop(pEnemy);
            return;
        }
    }

    _player->Attack(pEnemy, true);

    // QoL: also start the ranged auto-attack, so "attack this target" works for
    // ranged-weapon classes even while moving (the client withholds the Auto Shot
    // cast while running). No-op for melee-only classes / out-of-range targets.
    StartRangedAutoAttack(_player, pEnemy);
}

void WorldSession::HandleAttackStopOpcode(WorldPacket& /*recvData*/)
{
    GetPlayer()->AttackStop();
}

void WorldSession::HandleSetSheathedOpcode(WorldPackets::Combat::SetSheathed& packet)
{
    if (packet.CurrentSheathState >= MAX_SHEATH_STATE)
    {
        LOG_ERROR("network.opcode", "Unknown sheath state {} ??", packet.CurrentSheathState);
        return;
    }

    _player->SetSheath(SheathState(packet.CurrentSheathState));
}
