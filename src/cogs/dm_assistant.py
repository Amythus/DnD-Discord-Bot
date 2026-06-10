import json
import discord
from discord.ext import commands
from discord import app_commands
from database.models import GameSession, CharacterSheet, RoomContext, StagedAction
from cogs.action_cog import SinglePlayerRollView
from services.gemini_client import gemini_service
from google.genai import types
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Initialize Jinja2 prompt template environment
jinja_env = Environment(
    loader=FileSystemLoader("src/templates"),
    autoescape=select_autoescape()
)

# ==============================================================================
# DISCORD UI COMPONENT (The Staged Execution Launcher)
# ==============================================================================
class StagedExecutionView(discord.ui.View):
    """Presents an approved action. Clicking launches it straight into the game engine."""
    def __init__(self, channel_id: str, player_id: str):
        super().__init__(timeout=60)
        self.channel_id = channel_id
        self.player_id = player_id

    # --- ACTION EXECUTION CALLBACK ---
    # Intercepts confirmation clicks and bridges parameters natively into the rolling engine.
    @discord.ui.button(label="🚀 CONFIRM & EXECUTE ACTION", style=discord.ButtonStyle.success, custom_id="exec_staged_btn")
    async def execute_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message("You cannot execute another player's staged intent!", ephemeral=True)
            return

        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.defer()

        session = await GameSession.find_one(GameSession.channel_id == self.channel_id)
        staged = next((a for a in session.staged_actions if a.player_id == self.player_id), None)
        
        if not staged:
            await interaction.followup.send("❌ **Error:** Your staged action has expired or was cleared.")
            return

        view = SinglePlayerRollView(
            channel_id=self.channel_id,
            player_id=self.player_id,
            roll_type=staged.roll_required,
            target_dc=staged.target_dc,
            action_text=staged.original_intent
        )

        session.staged_actions = [a for a in session.staged_actions if a.player_id != self.player_id]
        await session.save()

        await interaction.followup.send(
            f"🎲 **Executing Action for {staged.character_name}:** *\"{staged.original_intent}\"*\n"
            f"Requires a **DC {staged.target_dc} {staged.roll_required}** check.",
            view=view
        )
        self.stop()


# ==============================================================================
# THE UPGRADED DM ASSISTANT COG ENGINE
# ==============================================================================
class DMAssistantCog(commands.Cog):
    """Handles @dm_assistant requests for rules pre-clearance, staging, and session lore queries."""
    def __init__(self, bot):
        self.bot = bot

    # --- MASTER INTENT INTERCEPTOR ---
    # Catches app mentions, parses state parameters from MongoDB, and bifurcated data flow to Gemini.
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        
        if self.bot.user.mentioned_in(message):
            channel_id = str(message.channel.id)
            player_id = str(message.author.id)

            # Extract the raw intent text by clean-stripping the bot's mention tag out
            user_query = message.content.replace(f'<@!{self.bot.user.id}>', '').replace(f'<@{self.bot.user.id}>', '').strip()
            if not user_query:
                await message.reply("Greetings, adventurer! State an intent (e.g., `@DM_Assistant Can I flip over the table?`) or ask an out-of-character lore question relative to your current room surroundings!")
                return

            # Fetch state infrastructure references from MongoDB
            session = await GameSession.find_one(GameSession.channel_id == channel_id, fetch_links=True)
            character = await CharacterSheet.find_one(CharacterSheet.channel_id == channel_id, CharacterSheet.player_id == player_id)
            if not session or not character: return

            room = await RoomContext.find_one(
                RoomContext.module_slug == session.active_module.module_slug, 
                RoomContext.room_id == session.current_room_id
            )

            # Fetch the long-context module file handle from the server cache link pool
            client = gemini_service.get_client()
            module_file_handle = client.files.get(name=session.active_module.gemini_file_uri.split('/')[-1])

            # --- ROUTING LOGIC: STAGING vs CONTEXT LORE INTERROGATION ---
            # Check if the player is simply asking a question instead of attempting a physical maneuver
            is_query = any(keyword in user_query.lower() for keyword in ["what", "who", "where", "how", "why", "examine", "remind", "look", "check"])

            if is_query:
                # --- CALL ROUTE 1: CONTEXTUAL LORE QUERY ---
                # Passes full campaign cache + room metadata framework to answer player questions conversational
                template = jinja_env.get_template("assistant_query.j2")
                    rendered_query = template.render(
                        character=character,
                        session=session,
                        room=room,
                        user_query=user_query
                    )

                    response = client.models.generate_content(
                        model=gemini_service.model_name,
                        contents=[
                            module_file_handle, # ❄️ Long Context Cache Hit (Reads the massive book)
                            rendered_query      # ✉️ Dynamic player query data payload
                        ]
                    )
                    await message.reply(f"🔮 **DM Assistant Lore Record:**\n{response.text}")
                return

            # --- CALL ROUTE 2: STANDARD ACTION STAGING ---
            # Operates on your strict validation schemas to cache intent parameters
            rule_template = jinja_env.get_template("rule_check.j2")
            rendered_rule_prompt = rule_template.render(character=character, room=room, player_action=user_query)

            async with message.channel.typing():
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
                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=response_schema)
                )
                decision = json.loads(rule_response.text)

            if not decision["action_valid"]:
                await message.reply(
                    f"🔮 **DM Assistant Pre-Clearance Audit:**\n"
                    f"❌ **Action Impossible:** {decision['rejection_reason']}\n"
                    f"*Your action state remains un-executed. Adjust your approach or try another intent description.*"
                )
                return

            if decision.get("move_to_room_id"):
                await message.reply(
                    f"🔮 **DM Assistant Pre-Clearance Audit:**\n"
                    f"✅ **Movement Available:** Unhindered passage to that zone is fully clear. No dice rolls needed!\n"
                    f"To finalize this movement, click the button below:",
                    view=StagedExecutionView(channel_id, player_id)
                )
                session.staged_actions = [a for a in session.staged_actions if a.player_id != player_id]
                session.staged_actions.append(StagedAction(player_id=player_id, character_name=character.character_name, original_intent=user_query, roll_required="None", target_dc=0))
                await session.save()
                return

            session.staged_actions = [a for a in session.staged_actions if a.player_id != player_id]
            session.staged_actions.append(StagedAction(
                player_id=player_id,
                character_name=character.character_name,
                original_intent=user_query,
                roll_required=decision["roll_required"],
                target_dc=decision["target_dc"]
            ))
            await session.save()

            view = StagedExecutionView(channel_id, player_id)
            await message.reply(
                f"🔮 **DM Assistant Pre-Clearance Audit:**\n"
                f"✅ Action Possible! Maps to a DC {decision['target_dc']} {decision['roll_required']} check.\n"
                f"If you choose to accept these mechanical stakes, lock it in below:",view=view)
                
async def setup(bot):
    await bot.add_cog(DMAssistantCog(bot))