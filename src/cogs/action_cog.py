import asyncio
import json
import random
from collections import defaultdict
from discord.ext import commands
import discord

from config.settings import settings
from database.models import GameSession, CharacterSheet, RoomContext
from services.gemini_client import gemini_service
from google.genai import types
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Setup Jinja2 prompt template environment
jinja_env = Environment(
    loader=FileSystemLoader("src/templates"),
    autoescape=select_autoescape()
)

# ==============================================================================
# DISCORD UI INTERACTIVE COMPONENT (The Roll Button View)
# ==============================================================================
class DiceRollView(discord.ui.View):
    """
    Spins up an interactive button tied securely to a specific player session.
    Fires the deterministic math engine natively on click and hands off to the Narrator.
    """
    def __init__(self, channel_id: str, player_id: str, roll_type: str, target_dc: int, action_text: str):
        # Timeout after 2 minutes of player hesitation
        super().__init__(timeout=120)
        self.channel_id = channel_id
        self.player_id = player_id
        self.roll_type = roll_type
        self.target_dc = target_dc
        self.action_text = action_text

    @discord.ui.button(label="🎲 CLICK TO ROLL", style=discord.ButtonStyle.primary, custom_id="dnd_roll_btn")
    async def roll_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Enforce user security check: Only the player attempting the action can roll
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("This isn't your fate to decide, adventurer!", ephemeral=True)
            return

        # Disable the button immediately to stop rapid double-clicking exploits
        button.disabled = True
        await interaction.message.edit(view=self)
        
        # Acknowledge interaction instantly to prevent Discord gateway timeouts
        await interaction.response.defer()

        # 2. Execute Deterministic Server-Side Math
        d20 = random.randint(1, 20)
        character = await CharacterSheet.find_one(
            CharacterSheet.channel_id == self.channel_id,
            CharacterSheet.player_id == self.player_id
        )
        
        # Pull modifier safely from our Pydantic dictionary layer
        modifier = character.base_skills.get(self.roll_type, 0)
        total = d20 + modifier
        success = total >= self.target_dc
        success_str = "SUCCESS" if success else "FAILURE"
        
        roll_summary = f"{success_str}! Rolled {d20} + {modifier} = {total} (vs DC {self.target_dc})"

        # 3. Apply Local Database State Mutations (Example: Damage tracking if failed)
        old_vitals = character.vitals.copy()
        if not success:
            # Trap or environment penalty logic example
            if character.vitals.session_current_hp is None:
                character.vitals.session_current_hp = character.vitals.base_max_hp
            character.vitals.session_current_hp = max(0, character.vitals.session_current_hp - 4)
            await character.save()

        # Update the UI layout to display the mathematical outcome
        await interaction.followup.send(f"**Dice Result:** {character.character_name} rolled **{total}** ({roll_summary}). Calling the DM...")

        # 4. Invoke the Cached Gemini Narrator via Jinja2 Prompts
        session = await GameSession.find_one(GameSession.channel_id == self.channel_id, fetch_links=True)
        
        template = jinja_env.get_template("narrator_prompt.j2")
        rendered_prompt = template.render(
            character=character,
            session=session,
            player_action=self.action_text,
            roll_summary=roll_summary,
            old_vitals=old_vitals
        )

        # Slide the Context Cache TTL forward to protect ongoing session RAM budgets
        gemini_service.bump_context_cache_ttl(session.active_module.gemini_file_uri)
        
        # Route to Gemini API Client via file reference handle
        client = gemini_service.get_client()
        module_file_handle = client.files.get(name=session.active_module.gemini_file_uri.split('/')[-1])

        response = client.models.generate_content(
            model=gemini_service.model_name,
            contents=[module_file_handle, rendered_prompt]
        )

        # 5. Presentation Layer delivery
        await interaction.followup.send(response.text)
        self.stop() # Kill the UI View tracker loop cleanly

    async def on_timeout(self):
        # Handle player hesitation by closing the view interaction channel
        print(f"⌛ Roll timeout occurred in channel {self.channel_id}")


# ==============================================================================
# CORE DISCORD ACTION COG
# ==============================================================================
class ActionCog(commands.Cog):
    """Manages natural language gameplay inputs and runs the Rule Check sequence."""
    def __init__(self, bot):
        self.bot = bot
        # Thread-safe async session locks dictionary mapping channel IDs to an active lock
        self.session_locks = defaultdict(asyncio.Lock)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 1. Pipeline Traffic Guards
        if message.author.bot:
            return
        # Ignore messages starting with commands or mentioning the Lorekeeper bot profile
        if message.content.startswith("!") or message.content.startswith("/") or self.bot.user.mentioned_in(message):
            return
        # Ignore text wrapped explicitly inside Out-Of-Character brackets
        if message.content.strip().startswith("((") and message.content.strip().endswith("))"):
            return

        channel_id = str(message.channel.id)
        player_id = str(message.author.id)

        # 2. Fire the Concurrency Lock System to freeze multi-user race conditions
        async with self.session_locks[channel_id]:
            
            # Fetch active game state from MongoDB
            session = await GameSession.find_one(GameSession.channel_id == channel_id, fetch_links=True)
            if not session:
                return # Silence if no active session is provisioned in this channel

            character = await CharacterSheet.find_one(
                CharacterSheet.channel_id == channel_id,
                CharacterSheet.player_id == player_id
            )
            if not character:
                await message.reply("You haven't checked into this campaign yet! Use `/join_session` first.")
                return

            room = await RoomContext.find_one(
                RoomContext.module_slug == session.active_module.module_slug,
                RoomContext.room_id == session.current_room_id
            )

            # 3. Construct and Execute the Rule Check Call
            rule_template = jinja_env.get_template("rule_check.j2")
            rendered_rule_prompt = rule_template.render(
                character=character,
                room=room,
                player_action=message.content
            )

            async with message.channel.typing():
                client = gemini_service.get_client()
                
                # Define expected schema constraints using inline type configurations
                class RuleResponse(pydantic_model := json.loads):
                    pass # Handled on the fly via Gemini Schema injection maps

                # To match Pydantic schema outputs accurately inside Gemini 3.1 Flash-Lite:
                response_schema = {
                    "type": "OBJECT",
                    "properties": {
                        "action_valid": {"type": "BOOLEAN"},
                        "rejection_reason": {"type": "STRING"},
                        "roll_required": {"type": "STRING"},
                        "target_dc": {"type": "INTEGER"}
                    },
                    "required": ["action_valid", "rejection_reason", "roll_required", "target_dc"]
                }

                # Evaluate mechanics via static rules cache
                rule_response = client.models.generate_content(
                    model=gemini_service.model_name,
                    contents=[rendered_rule_prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=response_schema
                    )
                )

                decision = json.loads(rule_response.text)

            # 4. Process Adjudication Results
            if not decision["action_valid"]:
                # Mechanical Rejection (e.g., Target out of range / slot empty)
                await message.reply(f"❌ **Action Denied:** {decision['rejection_reason']}")
                return

            # Action Approved: Instantiate the interactive component loop
            view = DiceRollView(
                channel_id=channel_id,
                player_id=player_id,
                roll_type=decision["roll_required"],
                target_dc=decision["target_dc"],
                action_text=message.content
            )
            
            await message.reply(
                f"🎲 **Action Validated:** {character.character_name} attempts to execute their action.\n"
                f"Requires a **DC {decision['target_dc']} {decision['roll_required']}** check.",
                view=view
            )

async def setup(bot):
    await bot.add_cog(ActionCog(bot))
