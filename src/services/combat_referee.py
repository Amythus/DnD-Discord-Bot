import random
from database.models.session import GameSession, ActiveCharacterState

class CombatReferee:
    @staticmethod
    async def process_player_combat_intent(channel, session: GameSession, actor: ActiveCharacterState, intent: dict) -> tuple[bool, str]:
        """
        Validates, consumes, and mutates database structures based on 2024 resource rules.
        Returns a tuple of (is_legal, logging_message).
        """
        tier = intent["resource_tier"]
        action_type = intent["action_type"]
        sub_text = intent["extracted_sub_text"]
        tracker = actor.turn_resources

        # =====================================================================
        # 1. FREE ACTIONS RESOURCE TRACKING
        # =====================================================================
        if tier == "FREE_ACTION":
            if action_type == "OBJECT_INTERACTION":
                if tracker.free_object_interaction_used:
                    # Under 2024 rules, a secondary object interaction upgrades to using your main Action [lost_mine_of_phandelver]
                    intent["resource_tier"] = "ACTION"
                    intent["action_type"] = "USE_OBJECT"
                    return await CombatReferee.process_player_combat_intent(channel, session, actor, intent)
                tracker.free_object_interaction_used = True
                return True, f"Free object interaction consumed: {sub_text}"
            return True, "Short communication recorded freely."

        # =====================================================================
        # 2. MOVEMENT RESOURCE TRACKING
        # =====================================================================
        elif tier == "MOVEMENT":
            if action_type == "STAND_UP":
                if tracker.active_movement_mode != "PRONE" and tracker.has_stood_up_this_turn:
                    return False, "❌ You are already standing up!"
                cost = tracker.base_speed_ft // 2 # Standing up costs exactly half your movement speed [lost_mine_of_phandelver]
                if tracker.movement_remaining_ft < cost:
                    return False, f"❌ Not enough movement remaining to stand up! Needs {cost}ft."
                tracker.movement_remaining_ft -= cost
                tracker.active_movement_mode = "WALK"
                tracker.has_stood_up_this_turn = True
                return True, "Character stood up from prone position safely."

            elif action_type in ["ALT_CLIMB", "ALT_SWIM", "ALT_CRAWL"]:
                # Alt movement modes function as difficult terrain, costing 2ft per 1ft moved [lost_mine_of_phandelver]
                tracker.active_movement_mode = action_type.replace("ALT_", "")
                return True, f"Movement mode swapped to {tracker.active_movement_mode}."

            return True, "Standard positioning adjustment logged."

        # =====================================================================
        # 3. BONUS ACTIONS RESOURCE TRACKING
        # =====================================================================
        elif tier == "BONUS_ACTION":
            if tracker.bonus_action_used:
                return False, "❌ You have already expended your Bonus Action choice for this combat turn!"
            tracker.bonus_action_used = True
            return True, f"Bonus Action consumed for: {action_type}"

        # =====================================================================
        # 4. MAIN ACTIONS RESOURCE TRACKING (The Core 11 Options)
        # =====================================================================
        elif tier == "ACTION":
            if tracker.action_used:
                return False, "❌ You have already expended your main Action choice for this combat turn!"
            
            # Apply strict systemic property changes based on the selected action blueprint type
            if action_type == "DODGE":
                # Dodging forces all incoming attacks to roll with disadvantage [lost_mine_of_phandelver]
                tracker.is_dodging = True
                
            elif action_type == "DISENGAGE":
                # Disengaging completely disables enemy opportunity attack triggers for the rest of your turn [lost_mine_of_phandelver]
                tracker.is_disengaged = True
                
            elif action_type == "DASH":
                # Dashing instantly doubles your remaining movement speed allocation balance [lost_mine_of_phandelver]
                tracker.movement_remaining_ft += tracker.base_speed_ft
                
            elif action_type == "HIDE":
                tracker.is_hiding = True

            tracker.action_used = True
            return True, f"Main Action consumed for: {action_type}"

        # =====================================================================
        # 5. REACTION RESOURCE TRACKING
        # =====================================================================
        elif tier == "REACTION":
            if tracker.reaction_used:
                return False, "❌ You have already expended your Reaction choice for this round rotation loop!"
            tracker.reaction_used = True
            return True, f"Reaction intercept consumed for: {action_type}"

        return False, "❌ Unrecognized resource tracking tier classification."

combat_referee = CombatReferee()
