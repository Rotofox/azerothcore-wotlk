#pragma once

#include "Player.h"
#include "GameObject.h"
#include "Spell.h"

class TrackingModule
{
public:
    static void Initialize();
    static void Shutdown();

private:
    static void CastDoubleGather(Player* player);
    static void CheckAndGrantSpell(Player* player);
    static void OnPlayerLogin(Player* player);
    static bool IsMultiGatherSpellEnabled(Player* player);
    static bool ToggleMultiGatherSpell(Player* player);
};
