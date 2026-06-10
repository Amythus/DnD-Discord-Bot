import asyncio
import json
import random
from collections import defaultdict
from discord.ext import commands
from discord import app_commands
import discord

from config.settings import settings
from database.models import GameSession, CharacterSheet, RoomContext
from services.gemini_client import gemini_service
from services.game_engine import game_engine
from google.genai import types
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Setup Jinja2 template workspace parsing framework
jinja_env = Environment(
    loader=FileSystemLoader("src/templates"),
    autoescape=select_autoescape()
)

# ==============================================================================
# SINGLE PLAYER INTERACTIVE VIEW ENGINE (Multi-Stage 2024 State Machine)
# ==============================================================================
class SinglePlayerRollView(discord.ui.View):
    """
    Manages a proactive, single-player action check. 
    Implements a multi-stage 2024 state machine for Heroic Inspiration fallbacks.
    """
    def __init__(self, channel_id: str, player_id: str, roll_type: str, target_dc: int, action_text: str):
        super().__init__(timeout=120)
        self.channel_id = channel_id
        self.player_id = player_id
        self.roll_type = roll_type
        self.target_dc = target_dc
        self.action_text = action_text
        self.first_roll = None
        self.final_total = None

    # --- NARRATOR PIPELINE HANDOFF ---
    # Compiles prompt templates and streams the tactical results to the Gemini Narrator.
    async def _execute_narrator_handoff(self, interaction: discord.Interaction, roll_summary: str, old_vitals):
        session = await GameSession.find_one(GameSession.channel_id == self.channel_id, fetch_links=True)
        character = await CharacterSheet.find_one(CharacterSheet.channel_id == self.channel_id, CharacterSheet.player_id == self.player_id)
        
        template = jinja_env.get_template("narrator_prompt.j2")
        rendered_prompt = template.render(
            character=character,
            session=session,
            player_action=self.action_text,
            roll_summary=roll_summary,
            old_vitals=old_vitals
        )

        gemini_service.bump_context_cache_ttl(session.active_module.gemini_file_uri)
        client = gemini_service.get_client()
        module_file_handle = client.files.get(name=session.active_module.gemini_file_uri.split('/')[-1])

        response = client.models.generate_content(
            model=gemini_service.model_name,
            contents=[module_file_handle, rendered_prompt]
        )
        
        await interaction.followup.send(response.text)
        self.stop()

    # --- STAGE 1: INITIAL DICE RESOLUTION ---
    # Executes the primary d20 roll, evaluates active buffs, and locks or branches the loop.
    @discord.ui.button(label="🎲 CLICK TO ROLL", style=discord.ButtonStyle.primary, custom_id="single_roll_btn")
    async def initial_roll_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("This isn't your fate to decide, traveler!", ephemeral=True)
            return

        await interaction.response.defer()
        
        character = await CharacterSheet.find_one(CharacterSheet.channel_id == self.channel_id, CharacterSheet.player_id == self.player_id)
        modifier = character.base_skills.get(self.roll_type, 0)
        
        d20 = random.randint(1, 20)
        self.first_roll = d20
        old_vitals = character.vitals.copy()

        # RECONCILE DYNAMIC ACTIVE BUFFS
        action_cat = "attack_rolls" if "Attack" in self.roll_type else "skills"
        buff_bonus, buff_breakdown = game_engine.evaluate_active_buffs(character.vitals, action_cat)
        
        total = d20 + modifier + buff_bonus

        # PATH A: SUCCESS OR NO HEROIC INSPIRATION -> Lock turn instantly
        if total >= self.target_dc or not character.vitals.has_heroic_inspiration:
            self.final_total = total
            button.disabled = True
            await interaction.message.edit(view=self)
            
            success_tag = "SUCCESS" if total >= self.target_dc else "FAILURE"
            summary = f"{success_tag}! Rolled {d20} + {modifier} (Base) {buff_breakdown} = {total} (vs DC {self.target_dc})"
            
            if total < self.target_dc:
                current_hp = character.vitals.session_current_hp if character.vitals.session_current_hp is not None else character.vitals.base_max_hp
                character.vitals.session_current_hp = max(0, current_hp - 4)
                await character.save()
                
            await interaction.followup.send(f"**Dice Result:** {character.character_name} rolled **{total}** ({summary}). Adjudicating scene...")
            await self._execute_narrator_handoff(interaction, summary, old_vitals)
        
        # PATH B: FAILURE BUT HAS HEROIC INSPIRATION -> Spawn 2024 option button
        else:
            button.disabled = True
            reroll_btn = discord.ui.Button(label="⚡ ACTIVATE HEROIC REROLL", style=discord.ButtonStyle.danger, custom_id="single_heroic_btn")
            
            # --- STAGE 2: 2024 OVERWRITE CALLBACK ---
            # Handles the post-roll 2024 overwrite loop, draining the inspiration flag from MongoDB.
            async def reroll_callback(inter: discord.Interaction):
                if str(inter.user.id) != self.player_id: return
                await inter.response.defer()
                
                new_d20 = random.randint(1, 20)
                b_bonus, b_breakdown = game_engine.evaluate_active_buffs(character.vitals, action_cat)
                new_total = new_d20 + modifier + b_bonus
                self.final_total = new_total
                
                reroll_btn.disabled = True
                await inter.message.edit(view=self)
                
                character.vitals.has_heroic_inspiration = False
                if new_total < self.target_dc:
                    current_hp = character.vitals.session_current_hp if character.vitals.session_current_hp is not None else character.vitals.base_max_hp
                    character.vitals.session_current_hp = max(0, current_hp - 4)
                await character.save()
                
                success_tag = "SUCCESS" if new_total >= self.target_dc else "FAILURE"
                summary = f"{success_tag}! **Heroic Reroll:** {new_d20} + {modifier} (Base) {b_breakdown} = {new_total} (vs DC {self.target_dc}, Overwrote {self.first_roll})"
                
                await inter.followup.send(f"💥 **Heroic Reroll Triggered!** New Total: **{new_total}** ({summary})")
                await self._execute_narrator_handoff(inter, summary, old_vitals)

            reroll_btn.callback = reroll_callback
            self.add_item(reroll_btn)
            
            await interaction.message.edit(
                content=f"⚠️ **Check Failed!** You rolled a total of `{total}` (vs DC {self.target_dc}). Spend your Heroic Inspiration to completely overwrite this roll?", 
                view=self
            )


# ==============================================================================
# REFACTORED CORE COG: SLASH COMMAND ENGINE
# ==============================================================================
class ActionCog(commands.Cog):
    """Manages player-driven tactical turns via secure Discord Slash Commands."""
    def __init__(self, bot):
        self.bot = bot
        self.session_locks = defaultdict(asyncio.Lock)

    # --- CORE CORE TACTICAL ACTION GATEWAY ---
    # Captures proactive text intents, runs strict rules evaluation via Gemini, and launches UI viewports.
    @app_commands.command(name="action", description="Execute an in-character tactical action within your current room.")
    @app_commands.describe(player_message="Describe exactly what your character attempts to do")
    async def execute_action(self, interaction: discord.Interaction, player_message: str):
        channel_id = str(interaction.channel_id)
        player_id = str(interaction.user.id)

        async with self.session_locks[channel_id]:
            session = await GameSession.find_one(GameSession.channel_id == channel_id, fetch_links=True)
            if not session:
                await interaction.response.send_message("❌ **Error:** No active session configured for this channel.", ephemeral=True)
                return

            character = await CharacterSheet.find_one(CharacterSheet.channel_id == channel_id, CharacterSheet.player_id == player_id)
            if not character:
                await interaction.response.send_message("❌ **Error:** You haven't checked a character sheet into this campaign yet! Use `/join_session`.", ephemeral=True)
                return

            await interaction.response.defer(thinking=True)

            room = await RoomContext.find_one(RoomContext.module_slug == session.active_module.module_slug, RoomContext.room_id == session.current_room_id)

            rule_template = jinja_env.get_template("rule_check.j2")
            rendered_rule_prompt = rule_template.render(
                character=character,
                room=room,
                player_action=player_message
            )

            client = gemini_service.get_client()
            response_schema = {
                "type": "OBJECT",
                "properties": {
                    "action_valid": {"type": "BOOLEAN"},
                    "rejection_reason": {"type": "STRING"},
                    "roll_required": {"type": "STRING"},
                    "target_dc": {"type": "INTEGER"},
                    "move_to_room_id": {"type": "STRING"}
                },
                "required": ["action_valid", "rejection_reason", "roll_required", "target_dc", "move_to_room_id"]
            }

            rule_response = client.models.generate_content(
                model=gemini_service.model_name,
                contents=[rendered_rule_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema
                )
            )

            decision = json.loads(rule_response.text)

            if not decision["action_valid"]:
                await interaction.followup.send(f"❌ Action Denied: {decision['rejection_reason']}")
                return
        
            # Spatial Navigation Bypass: Direct node movement
            if decision.get("move_to_room_id"):
                session.current_room_id = decision["move_to_room_id"]
                await session.save()
            
                summary = f"Character moves unhindered to destination location node: {decision['move_to_room_id']}"
                view = SinglePlayerRollView(channel_id, player_id, "None", 0, player_message)

                await interaction.followup.send(f"🏃 {character.character_name} moves to the next area...")
                await view._execute_narrator_handoff(interaction, summary, character.vitals.copy())
                return

            view = SinglePlayerRollView(
                channel_id=channel_id,
                player_id=player_id,
                roll_type=decision["roll_required"],
                target_dc=decision["target_dc"],
                action_text=player_message
            )

            await interaction.followup.send(
                f"🎲 Action Validated: {character.character_name} attempts their maneuver.\n"
                f"Requires a DC {decision['target_dc']} {decision['roll_required']} check.",view=view
            )
                    
                        

async def setup(bot):
    await bot.add_cog(ActionCog(bot))