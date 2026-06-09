import os
import re
import discord
from discord.ext import commands
from discord import app_commands
from google import genai
from google.genai import types

from config.settings import settings
from database.models import GameSession, CampaignModule, RoomContext
from services.ddb_parser import ddb_parser
from services.gemini_client import gemini_service

# Define the expected Pydantic schema structure for Gemini module parsing inline
import pydantic
from typing import List, Dict

class ParsedRoomSchema(pydantic.BaseModel):
    room_id: str
    room_title: str
    environmental_hazards: List[str]
    mechanics_override_json: Dict[str, str]
    flavor_text: str

class ParsedModuleSchema(pydantic.BaseModel):
    module_name: str
    rooms: List[ParsedRoomSchema]


class SetupCog(commands.Cog):
    """
    Manages campaign initialization and character check-ins. 
    Orchestrates the ingestion pipeline for Google Drive modules and D&D Beyond character sheets.
    """
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Ensures that slash commands are synchronized with the Discord API gateway upon boot."""
        # Synchronize slash commands globally across all connected Discord servers
        await self.bot.tree.sync()
        print("🤖 Slash Command tree synchronized successfully across global endpoints.")

    @staticmethod
    def _extract_gdrive_id(url: str) -> str:
        """Helper utility using regex to isolate the unique file ID out of a Google Drive link."""
        match = re.search(r'(?:id=|/d/|/file/d/)([\w_-]{25,})', url)
        if not match:
            raise ValueError("Malformed Google Drive link layout.")
        return match.group(1)

    # ==============================================================================
    # SLASH COMMAND: LOAD CAMPAIGN MODULE FROM GOOGLE DRIVE
    # ==============================================================================
    @app_commands.command(name="load_module", description="Ingests a campaign module PDF directly from a public Google Drive link.")
    @app_commands.describe(slug="Shorthand look-up label (e.g., lost_mine)", gdrive_url="Public sharing link of the document")
    async def load_module(self, interaction: discord.Interaction, slug: str, gdrive_url: str):
        # Only allow Administrators or managers to trigger world ingestion events
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ **Access Denied:** Only administrators can forge new worlds.", ephemeral=True)
            return

        # Defer interaction instantly to prevent 3-second Discord gateway timeouts during heavy parsing
        await interaction.response.defer(thinking=True)
        slug_clean = slug.strip().lower()

        try:
            # 1. Isolate the remote file ID and construct the Google direct export stream
            file_id = self._extract_gdrive_id(gdrive_url)
            export_stream_url = f"https://google.com{file_id}&exportFormat=pdf"

            # 2. Call Gemini 3.1 Flash-Lite to extract room parameters using Pydantic Structured Outputs
            client = gemini_service.get_client()
            extraction_prompt = (
                "Analyze this adventure module via its remote cloud stream. Break the adventure grid down room-by-room. "
                "Extract all specific mechanical environmental hazards, rule overrides, and narrative descriptions boxes."
            )

            # Check if this module already exists locally to prevent duplicate cloud data uploads
            existing_module = await CampaignModule.find_one(CampaignModule.module_slug == slug_clean)
            
            # Use the stream URL directly as the content payload to evaluate room trees
            response = client.models.generate_content(
                model=gemini_service.model_name,
                contents=[export_stream_url, extraction_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ParsedModuleSchema,
                ),
            )

            structured_data = ParsedModuleSchema.model_validate_json(response.text)

            # 3. Commit Master Module Metadata mapping into MongoDB
            campaign = CampaignModule(
                module_slug=slug_clean,
                module_name=structured_data.module_name,
                gemini_file_uri=export_stream_url # Direct remote streaming URL pointer saved for long-context caching
            )
            await campaign.save()

            # 4. Flush and replace individual room context boundaries natively inside MongoDB collections
            await RoomContext.find(RoomContext.module_slug == slug_clean).delete()
            for parsed_room in structured_data.rooms:
                room_doc = RoomContext(
                    module_slug=slug_clean,
                    room_id=parsed_room.room_id,
                    room_title=parsed_room.room_title,
                    environmental_hazards=parsed_room.environmental_hazards,
                    mechanics_override_json=parsed_room.mechanics_override_json,
                    flavor_text=parsed_room.flavor_text
                )
                await room_doc.insert()

            # 5. Initialize or overwrite the active Game Session link for this specific Discord channel
            session = await GameSession.find_one(GameSession.channel_id == str(interaction.channel_id))
            if not session:
                session = GameSession(
                    channel_id=str(interaction.channel_id),
                    current_room_id=structured_data.rooms[0].room_id if structured_data.rooms else "start",
                    active_module=campaign
                )
            else:
                session.active_module = campaign
                if structured_data.rooms:
                    session.current_room_id = structured_data.rooms[0].room_id
            
            await session.save()
            await interaction.followup.send(
                f"🎉 **Module Loaded Successfully!** Registered campaign: **{structured_data.module_name}**.\n"
                f"Stored `{len(structured_data.rooms)}` distinct room tactical grids securely. Campaign is active in this channel!"
            )

        except ValueError:
            await interaction.followup.send("❌ **Error:** Invalid Google Drive URL structure. Ensure it contains a standard file ID block.")
        except Exception as e:
            print(f"❌ Ingestion pipeline crash: {e}")
            await interaction.followup.send("❌ **Parsing Error:** Gemini failed to evaluate the document stream. Verify the Google Drive link is set to public ('Anyone with link can view').")

    # ==============================================================================
    # SLASH COMMAND: REGISTER CHARACTER SHEET TO SESSION
    # ==============================================================================
    @app_commands.command(name="join_session", description="Parses and checks your character sheet into this channel's active campaign room.")
    @app_commands.describe(ddb_url="Your public D&D Beyond character profile sharing link")
    async def join_session(self, interaction: discord.Interaction, ddb_url: str):
        channel_id = str(interaction.channel_id)
        player_id = str(interaction.user.id)

        # 1. Operational Guard: Verify that a campaign has actually been booted up in this channel first
        session = await GameSession.find_one(GameSession.channel_id == channel_id)
        if not session:
            await interaction.response.send_message("❌ **Error:** No active campaign session exists in this room. Ask an admin to execute `/load_module` first.", ephemeral=True)
            return

        # Defer interaction to give the D&D Beyond scraper and Gemini parser time to work
        await interaction.response.defer(thinking=True)

        # 2. Run the smart parsing service layer to sync the data sheets to MongoDB
        synced_sheet = await ddb_parser.parse_and_sync_character(
            channel_id=channel_id,
            player_id=player_id,
            ddb_url=ddb_url
        )

        # 3. Dispatch presentation response states based on sync outcomes
        if synced_sheet:
            await interaction.followup.send(
                f"⚔️ **Character Sheet Sync Complete!** Welcome to the adventure, **{synced_sheet.character_name}** (`{synced_sheet.class_and_level}`).\n"
                f"Your baseline statistics and proficiencies are registered. Type an in-character action at any time to begin playing!"
            )
        else:
            await interaction.followup.send("❌ **Sync Failure:** Unable to parse sheet data. Ensure your D&D Beyond character profile configuration privacy is set to **Public**.")

async def setup(bot):
    await bot.add_cog(SetupCog(bot))
