import discord
import random
from beanie import PydanticObjectId
from typing import List
from database.models.character import CharacterSheet
from database.models.session import GameSession, SessionStatus, PartyState, CombatState, NarrativeMemory, ActiveCharacterState

class InitialDiceRollView(discord.ui.View):
    """
    Exposes a unified 2024 Theatre of the Mind rolling button canvas.
    Handles advantage and disadvantage math natively in Python before resolution [lost_mine_of_phandelver].
    """
    def __init__(self, session_id: PydanticObjectId, character_id: str, stat_name: str, target_dc: int, modifier: int, roll_modifier_mode: str = "NORMAL"):
        super().__init__(timeout=120)
        self.session_id = session_id
        self.character_id = character_id
        self.stat_name = stat_name
        self.target_dc = target_dc
        self.modifier = modifier
        self.roll_modifier_mode = roll_modifier_mode  # Expected values: "NORMAL", "ADVANTAGE", "DISADVANTAGE"

    @discord.ui.button(label="Roll Dice", style=discord.ButtonStyle.primary, emoji="🎲")
    async def roll_dice(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Disable button immediately to prevent double-click network latency exploits
        button.disabled = True
        await interaction.response.edit_message(view=self)

        # 1. Automated Python Dice Roll Generation
        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)

        if self.roll_modifier_mode == "ADVANTAGE":
            final_d20 = max(roll1, roll2)
            math_desc = f"Rolled with Advantage: [d20: {roll1}, {roll2}] -> took **{final_d20}**"
        elif self.roll_modifier_mode == "DISADVANTAGE":
            final_d20 = min(roll1, roll2)
            math_desc = f"Rolled with Disadvantage: [d20: {roll1}, {roll2}] -> took **{final_d20}**"
        else:
            final_d20 = roll1
            math_desc = f"Rolled d20: **{final_d20}**"

        # 2. Hand data off to your two-stage evaluator function inside utils.py
        # This utility checks for failures to dynamically trigger Heroic Inspiration views [lost_mine_of_phandelver]
        from cogs.utils import handle_initial_roll_result
        await handle_initial_roll_result(
            ctx=interaction.channel,
            session_id=self.session_id,
            character_id=self.character_id,
            stat_name=self.stat_name,
            target_dc=self.target_dc,
            modifier=self.modifier,
            rolled_d20=final_d20,
            math_desc=math_desc,
            client=interaction.client
        )


class HeroicInspirationDecisionView(discord.ui.View):
    """
    A reactive prompt canvas popped up ONLY if an initial roll fails
    and the player possesses a True 'has_heroic_inspiration' flag inside MongoDB [lost_mine_of_phandelver].
    """
    def __init__(self, session_id: PydanticObjectId, character_id: str, stat_name: str, target_dc: int, modifier: int, original_d20: int):
        super().__init__(timeout=60)
        self.session_id = session_id
        self.character_id = character_id
        self.stat_name = stat_name
        self.target_dc = target_dc
        self.modifier = modifier
        self.original_d20 = original_d20

    async def finalize_and_dispatch(self, interaction: discord.Interaction, final_d20: int, math_desc: str):
        """Locks down the canvas and hands the definitive result to the Narrator LLM [lost_mine_of_phandelver]."""
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        total = final_d20 + self.modifier
        success = total >= self.target_dc
        outcome = "SUCCESS" if success else "FAILURE"

        # Check for 2024 Rulebook Natural 20 guidelines (Grants a new Heroic Inspiration charge) [lost_mine_of_phandelver]
        awarded_inspiration_note = ""
        if final_d20 == 20:
            session = await GameSession.get(self.session_id)
            actor = session.party_state.active_characters[self.character_id]
            actor.has_heroic_inspiration = True
            await session.save()
            awarded_inspiration_note = "\n✨ *Natural 20! Heroic Inspiration has been awarded to your character profile!*"

        payload = {
            "character_id": self.character_id,
            "check_type": self.stat_name.upper(),
            "dc_target": self.target_dc,
            "final_score": total,
            "math_breakdown": f"{math_desc} + Modifier: {self.modifier}",
            "outcome": outcome
        }

        if awarded_inspiration_note:
            await interaction.channel.send(content=awarded_inspiration_note)

        # Notify the NarrativeEngineCog to describe the final outcome to the channel [lost_mine_of_phandelver]
        interaction.client.dispatch("rules_roll_complete", self.session_id, payload)

    @discord.ui.button(label="Accept Original Roll", style=discord.ButtonStyle.secondary)
    async def accept_original(self, interaction: discord.Interaction, button: discord.ui.Button):
        desc = f"Accepted original roll: **{self.original_d20}**"
        await self.finalize_and_dispatch(interaction, self.original_d20, desc)

    @discord.ui.button(label="🔥 Spend Heroic Inspiration (Reroll!)", style=discord.ButtonStyle.danger)
    async def reroll_dice(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Mutate state in database instantly to consume the resource safely [lost_mine_of_phandelver]
        session = await GameSession.get(self.session_id)
        actor = session.party_state.active_characters[self.character_id]
        actor.has_heroic_inspiration = False
        await session.save()

        # 2. Roll a completely new d20 and force the user to take it [lost_mine_of_phandelver]
        new_d20 = random.randint(1, 20)
        desc = f"Spent Heroic Inspiration! Discarded {self.original_d20}. **New Roll: {new_d20}**"
        
        await self.finalize_and_dispatch(interaction, new_d20, desc)

class GroupDiceRollView(discord.ui.View):
    """
    Exposes a multi-user collective rolling interface board for team checks.
    Natively handles Group Majority rules or Hazard Saving Throws in Python [lost_mine_of_phandelver].
    """
    def __init__(self, session_id: PydanticObjectId, checking_team_ids: list, stat_name: str, target_dc: int, check_mode: str):
        # 3 minute timeout to give all active party members time to click
        super().__init__(timeout=180)
        self.session_id = session_id
        self.checking_team_ids = checking_team_ids  # List of active character_id strings
        self.stat_name = stat_name                  # e.g., "stealth" or "dexterity"
        self.target_dc = target_dc
        self.check_mode = check_mode                # "GROUP_CHECK" or "INDIVIDUAL_HAZARD"
        
        # Track completed team entries securely in local memory
        self.recorded_rolls = {}  # {character_id: {"rolled_d20": int, "total": int, "success": bool, "name": str}}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Enforces multi-user security constraints so only target party members can roll."""
        session = await GameSession.get(self.session_id)
        
        # Cross-reference the clicking Discord user ID with the session character map
        user_char_id = next((c_id for c_id, c in session.party_state.active_characters.items() if c.user_id == str(interaction.user.id)), None)
        
        if not user_char_id or user_char_id not in self.checking_team_ids:
            await interaction.response.send_message("❌ You are not part of this team check sequence!", ephemeral=True)
            return False
            
        if user_char_id in self.recorded_rolls:
            await interaction.response.send_message("❌ You have already submitted your dice entry for this event!", ephemeral=True)
            return False
            
        # Cache the character ID string inside interaction extras for the button callback
        interaction.extras["character_id"] = user_char_id
        return True

    @discord.ui.button(label="Roll Team Dice", style=discord.ButtonStyle.success, emoji="👥")
    async def roll_team_dice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        char_id = interaction.extras["character_id"]
        session = await GameSession.get(self.session_id)
        actor = session.party_state.active_characters[char_id]
        
        # Automated Modifier Lookup out of the active session state
        # Lowercase fallback guard ensures robust matching (e.g., "Stealth" -> "stealth")
        modifier = actor.skill_modifiers.get(self.stat_name.lower(), 0)
        
        # Pure Python True Random d20 Generation
        d20_roll = random.randint(1, 20)
        total = d20_roll + modifier
        success = total >= self.target_dc
        
        # Record this individual player's entry into our checklist
        self.recorded_rolls[char_id] = {
            "rolled_d20": d20_roll,
            "total": total,
            "success": success,
            "name": actor.name,
            "breakdown": f"Rolled {d20_roll} + {modifier} = {total}"
        }
        
        await interaction.followup.send(f"🎲 Your roll of **{total}** has been logged safely!", ephemeral=True)
        
        # When the last required player submits their roll, lock the view and process outcomes
        if len(self.recorded_rolls) == len(self.checking_team_ids):
            await self.finalize_team_check(interaction.channel)

    async def finalize_team_check(self, channel: discord.TextChannel):
        """Processes team-wide mathematical victory boundaries and dispatches data upstream."""
        for child in self.children:
            child.disabled = True
            
        # --- MODE 1: GROUP MOVEMENT / COCHLEAR SNEAKING (Majority Rules) ---
        if self.check_mode == "GROUP_CHECK":
            success_count = sum(1 for r in self.recorded_rolls.values() if r["success"])
            required_successes = (len(self.checking_team_ids) + 1) // 2  # 2024 Rule: Half or more must succeed [lost_mine_of_phandelver]
            
            group_success = success_count >= required_successes
            global_outcome = "SUCCESS" if group_success else "FAILURE"
            
            math_breakdown = f"Group Check Matrix: {success_count}/{len(self.checking_team_ids)} passed (Needed {required_successes}).\n"
            math_breakdown += "\n".join([f"• **{r['name']}**: {r['breakdown']}" for r in self.recorded_rolls.values()])
            
            payload = {
                "character_id": "THE_ENTIRE_PARTY",
                "check_type": f"GROUP_{self.stat_name.upper()}",
                "dc_target": self.target_dc,
                "final_score": success_count,
                "math_breakdown": math_breakdown,
                "outcome": global_outcome,
                "raw_statement": f"The party executes a collective {self.stat_name} check."
            }

            # If a Group Stealth Check fails clumsily, flag an acoustic anomaly to wake monsters [lost_mine_of_phandelver]
            if not group_success and self.stat_name.lower() == "stealth":
                payload["trigger_environmental_noise"] = "sudden_movement_or_loud_noise"

        # --- MODE 2: ENVIRONMENTAL AREA TRAPS & HAZARDS (Individual Saves) ---
        else:
            session = await GameSession.get(self.session_id)
            
            # Traps resolve damage independently on a per-player basis [lost_mine_of_phandelver]
            for char_id, r in self.recorded_rolls.items():
                if not r["success"]:
                    actor = session.party_state.active_characters[char_id]
                    # Process 2d6 spike/explosion trap damage natively in Python code [lost_mine_of_phandelver]
                    damage = random.randint(1, 6) + random.randint(1, 6)
                    actor.current_hp = max(0, actor.current_hp - damage)
                    r["breakdown"] += f" | 💥 FAILED SAVE! Took {damage} damage. HP: {actor.current_hp}"
                else:
                    r["breakdown"] += " | 🛡️ SAVED! Avoided trap damage."
            
            await session.save()
            
            math_breakdown = "Individual Hazard Tracking Ledger:\n"
            math_breakdown += "\n".join([f"• **{r['name']}**: {r['breakdown']}" for r in self.recorded_rolls.values()])
            
            payload = {
                "character_id": "THE_ENTIRE_PARTY",
                "check_type": f"TEAM_HAZARD_{self.stat_name.upper()}",
                "dc_target": self.target_dc,
                "final_score": 0,
                "math_breakdown": math_breakdown,
                "outcome": "MIXED_RESULTS",
                "raw_statement": "An environmental hazard forces reaction saving throws across the group."
            }

        # Stop button listeners and push the finalized packet to NarrativeEngineCog
        self.stop()
        channel.client.dispatch("rules_roll_complete", self.session_id, payload)
