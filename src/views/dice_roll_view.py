import discord
import random
from beanie import PydanticObjectId
from typing import List
from database.models.character import CharacterSheet
from database.models.session import GameSession, SessionStatus, PartyState, CombatState, NarrativeMemory, ActiveCharacterState

class GroupDiceRollView(discord.ui.View):
    def __init__(self, session_id: PydanticObjectId, checking_team_ids: list, stat_name: str, target_dc: int, check_mode: str):
        # Timeout after 3 minutes to give a large party time to click their buttons
        super().__init__(timeout=180)
        self.session_id = session_id
        self.checking_team_ids = checking_team_ids # List of character_id strings in the party
        self.stat_name = stat_name
        self.target_dc = target_dc
        self.check_mode = check_mode # "GROUP_CHECK" or "INDIVIDUAL_HAZARD"
        
        # Track completed player rolls in server memory
        self.recorded_rolls = {} # {character_id: {"rolled_d20": int, "total": int, "success": bool, "name": str}}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Verifies if the clicking user owns an active character that hasn't rolled yet."""
        session = await GameSession.get(self.session_id)
        
        # Find which character ID belongs to this Discord user ID
        user_char_id = next((c_id for c_id, c in session.party_state.active_characters.items() if c.user_id == str(interaction.user.id)), None)
        
        if not user_char_id or user_char_id not in self.checking_team_ids:
            await interaction.response.send_message("❌ You are not part of this team check!", ephemeral=True)
            return False
            
        if user_char_id in self.recorded_rolls:
            await interaction.response.send_message("❌ You have already submitted your dice roll for this check!", ephemeral=True)
            return False
            
        # Temporarily store the verified character ID on the interaction object for the button callback
        interaction.extras["character_id"] = user_char_id
        return True

    @discord.ui.button(label="🎲 Roll Team Dice", style=discord.ButtonStyle.primary, emoji="👥")
    async def roll_team_dice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        char_id = interaction.extras["character_id"]
        session = await GameSession.get(self.session_id)
        actor = session.party_state.active_characters[char_id]
        
        # 1. Automated Python Modifier Resolution
        # Dynamically fetch the correct modifier out of the skill or attribute dictionaries we built earlier
        modifier = actor.skill_modifiers.get(self.stat_name.lower(), 0)
        
        d20_roll = random.randint(1, 20)
        total = d20_roll + modifier
        success = total >= self.target_dc
        
        # 2. Record the score in our tracking matrix
        self.recorded_rolls[char_id] = {
            "rolled_d20": d20_roll,
            "total": total,
            "success": success,
            "name": actor.name,
            "breakdown": f"Rolled {d20_roll} + {modifier} = {total}"
        }
        
        # 3. Update the public display status message
        await interaction.followup.send(f"✅ Your roll of **{total}** has been recorded securely!", ephemeral=True)
        
        # Check if the entire party has submitted their rolls
        if len(self.recorded_rolls) == len(self.checking_team_ids):
            await self.finalize_team_check(interaction.channel)

    async def finalize_team_check(self, channel: discord.TextChannel):
        """Processes team-wide mathematical victory constraints and dispatches to the Narrator."""
        for child in self.children:
            child.disabled = True
            
        # --- PHASE 1: MATHEMATICAL GROUP CHECK RESOLUTION (Majority Rules) ---
        if self.check_mode == "GROUP_CHECK":
            success_count = sum(1 for r in self.recorded_rolls.values() if r["success"])
            required_successes = (len(self.checking_team_ids) + 1) // 2 # At least half the team [lost_mine_of_phandelver]
            
            group_success = success_count >= required_successes
            global_outcome = "SUCCESS" if group_success else "FAILURE"
            
            math_breakdown = f"Group Check Result: {success_count}/{len(self.checking_team_ids)} players succeeded (Needed {required_successes}).\n"
            math_breakdown += "\n".join([f"• **{r['name']}**: {r['breakdown']}" for r in self.recorded_rolls.values()])
            
            # Simple payload format for the Narrator to describe group success or failure
            payload = {
                "character_id": "THE_ENTIRE_PARTY",
                "check_type": f"GROUP_{self.stat_name.upper()}",
                "dc_target": self.target_dc,
                "final_score": success_count,
                "math_breakdown": math_breakdown,
                "outcome": global_outcome,
                "raw_statement": f"The party attempts a coordinated group {self.stat_name} check."
            }

        # --- PHASE 2: INDIVIDUAL HAZARD CHECK RESOLUTION ---
        else:
            # For traps or explosions, track exactly who succeeded and who failed independently [lost_mine_of_phandelver]
            math_breakdown = "Individual Hazard Tracking:\n"
            math_breakdown += "\n".join([f"• **{r['name']}**: {r['breakdown']} -> " + ("*SAVED*" if r['success'] else "*FAILED*") for r in self.recorded_rolls.values()])
            
            payload = {
                "character_id": "THE_ENTIRE_PARTY",
                "check_type": f"TEAM_HAZARD_{self.stat_name.upper()}",
                "dc_target": self.target_dc,
                "final_score": 0,
                "math_breakdown": math_breakdown,
                "outcome": "MIXED_RESULTS",
                "raw_statement": "A sudden hazard forces individual saving throws across the whole group."
            }
            
            # If it's a hazard failure, programmatically deduct health natively in Python right here [lost_mine_of_phandelver]
            # (e.g., if you fail the save, deduct 2d6 trap damage from your active character state document)
            session = await GameSession.get(self.session_id)
            for char_id, r in self.recorded_rolls.items():
                if not r["success"]:
                    actor = session.party_state.active_characters[char_id]
                    damage = random.randint(1, 6) + random.randint(1, 6) # 2d6 damage [lost_mine_of_phandelver]
                    actor.current_hp = max(0, actor.current_hp - damage)
                    r["breakdown"] += f" | Took {damage} damage! Current HP: {actor.current_hp}"
            
            payload["math_breakdown"] = "Individual Hazard Tracking:\n" + "\n".join([f"• **{r['name']}**: {r['breakdown']}" for r in self.recorded_rolls.values()])
            await session.save()

        # Stop view interaction listeners and hand the final payload to the Narrator LLM
        self.stop()
        channel.client.dispatch("rules_roll_complete", self.session_id, payload)


class InitialDiceRollView(discord.ui.View):
    def __init__(self, session_id: PydanticObjectId, character_id: str, stat_name: str, target_dc: int, modifier: int, can_use_inspiration: bool):
        super().__init__(timeout=120)
        self.session_id = session_id
        self.character_id = character_id
        self.stat_name = stat_name
        self.target_dc = target_dc
        self.modifier = modifier
        
        # If the player doesn't have regular inspiration, gray out the advantage button instantly
        if not can_use_inspiration:
            self.inspiration_advantage_roll.disabled = True
            self.inspiration_advantage_roll.style = discord.ButtonStyle.secondary

    async def process_initial_roll(self, interaction: discord.Interaction, mode: str):
        """Processes the primary d20 roll mechanics securely in Python."""
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)

        if mode == "INSPIRATION_ADVANTAGE":
            # 1. Consume the resource in MongoDB via Beanie
            session = await GameSession.find_one({"_id": self.session_id})
            actor = session.party_state.active_characters[self.character_id]
            actor.has_regular_inspiration = False
            await session.save()

            final_d20 = max(roll1, roll2)
            math_desc = f"Rolled with Inspiration (Advantage): [d20: {roll1}, {roll2}] -> took **{final_d20}**"
        else:
            final_d20 = roll1
            math_desc = f"Rolled normal d20: **{final_d20}**"

        # Pass the verified numeric result to your two-stage evaluator function
        # This function determines whether to display the reactive Heroic Inspiration view or finalize
        from .utils import handle_initial_roll_result
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

    # --- Button Layout Configuration ---
    
    @discord.ui.button(label="Normal Roll", style=discord.ButtonStyle.primary, emoji="🎲", row=0)
    async def normal_roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_initial_roll(interaction, "NORMAL")

    @discord.ui.button(label="Spend Inspiration (Advantage)", style=discord.ButtonStyle.success, emoji="✨", row=0)
    async def inspiration_advantage_roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_initial_roll(interaction, "INSPIRATION_ADVANTAGE")