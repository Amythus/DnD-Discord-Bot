import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from google import genai
from google.genai import types

# Import core schema documents and utilities
from services.template_service import prompt_service
from database.models.session import GameSession, PartyState, CombatState, NarrativeMemory, SessionStatus
from database.models.character import CharacterSheet
from database.models.room import Room

class CoreCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ai_client = genai.Client()

    @app_commands.command(name="start_campaign", description="Initializes a new game session using an imported campaign module.")
    @app_commands.describe(campaign_id="The unique reference slug identifier of the module (e.g. lost_mine_of_phandelver)")
    async def start_campaign(self, interaction: discord.Interaction, campaign_id: str):
        """Creates a running group session delta environment inside MongoDB."""
        await interaction.response.defer(ephemeral=False)

        # 1. Fetch the absolute starting room blueprint for this specific module from MongoDB
        # Convention: The first room of an ingested module is slugified as '<campaign_id>_lvl1_room_01'
        starting_room_id = f"{campaign_id}_lvl1_room_01"
        starting_room = await Room.find_one(Room.room_id == starting_room_id)
        
        if not starting_room:
            return await interaction.followup.send(
                f"❌ **Module Not Found!** Unable to locate a parsed module matching id `{campaign_id}` in our collection blueprints. "
                f"Ensure you run `/import_module` first."
            )

        # 2. Gather all public Character Sheets registered to users currently in this Discord text channel
        active_characters_map = {}
        channel_members = interaction.channel.members
        
        for member in channel_members:
            if member.bot:
                continue
            # Search for the latest character profile sheet owned by this discord user id string
            master_sheet = await CharacterSheet.find_one(CharacterSheet.user_id == str(member.id))
            if master_sheet:
                from database.models.session import ActiveCharacterState
                # Convert the heavy sheet down to a streamlined real-time active state dictionary
                active_characters_map[str(master_sheet.id)] = ActiveCharacterState(
                    character_id=master_sheet.id,
                    user_id=str(member.id),
                    name=master_sheet.name,
                    class_and_level=f"{master_sheet.character_class} {master_sheet.level}",
                    current_hp=master_sheet.vitals.current_hp,
                    armor_class=master_sheet.vitals.armor_class,
                    speed_ft=master_sheet.vitals.speed_ft,
                    initiative_modifier=master_sheet.vitals.initiative_modifier,
                    passive_perception=master_sheet.vitals.passive_perception,
                    proficiency_bonus=2, # Default tier 1 modifier boundary
                    saving_throw_modifiers={k: v.modifier for k, v in master_sheet.attributes.__dict__.items()},
                    skill_modifiers={s: 2 for s in master_sheet.proficiencies} # Rough baseline lookup
                )

        if not active_characters_map:
            return await interaction.followup.send("❌ **Party Setup Failed!** No registered character sheets found for members in this channel. Run `/import_character` first.")

        # 3. Designate the command executor as the initial party leader token holder
        leader_character_id = list(active_characters_map.keys())[0]
        leader_name = active_characters_map[leader_character_id].name

        # 4. Instantiate the complete GameSession database delta document structure
        new_session = GameSession(
            campaign_id=campaign_id,
            session_status=SessionStatus.ACTIVE,
            party_state=PartyState(
                current_region_id=campaign_id,
                current_room_id=starting_room_id,
                party_leader_id=leader_character_id,
                active_characters=active_characters_map
            ),
            combat_state=CombatState(in_combat=False),
            narrative_memory=NarrativeMemory(campaign_summary_so_far=f"The party began their journey in {starting_room.title}.")
        )
        
        # Save the live session tracking layout to MongoDB via Beanie
        await new_session.insert()

        # --- STEP 5: Invoke Jinja2 Welcome Template and Call Gemini 3.1 Flash Lite ---
        prompt = prompt_service.render_prompt(
            "campaign_welcome.jinja",
            campaign_title=campaign_id.replace("_", " ").title(),
            room=starting_room,
            session=new_session,
            leader_name=leader_name
        )

        response = self.ai_client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.85, # Immersive storytelling style variance
                thinking_level="low" # Lower reasoning depth is fine for introductory narrative prose
            )
        )

        story_intro = response.text

        # 6. Post the clean welcome embed out to the active channel layout
        embed = discord.Embed(
            title=f"⚔️ Campaign Initialized: {campaign_id.replace('_', ' ').title()}",
            description=story_intro,
            color=discord.Color.dark_red()
        )
        embed.add_field(name="👑 Appointed Party Leader", value=f"**{leader_name}** has been given the Vanguard Lead Token.", inline=False)
        embed.add_field(name="🗺️ Current Location", value=f"📍 **{starting_room.title}**", inline=True)
        embed.add_field(name="👥 Active Party Size", value=f"🛡️ **{len(active_characters_map)} Heroes** active in session.", inline=True)
        embed.set_footer(text=f"Session ID Reference Reference: {new_session.id}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="promote_leader", description="Transfers the out-of-combat navigation Lead Token to another player.")
    @app_commands.describe(member="The Discord user you want to appoint as the new party guide")
    async def promote_leader(self, interaction: discord.Interaction, member: discord.Member):
        """Mutates the party_leader_id state block to support navigation handover actions."""
        session = await GameSession.find_one({"party_state.active_characters.user_id": str(interaction.user.id)})
        if not session:
            return await interaction.response.send_message("❌ You are not currently inside an active campaign session context.", ephemeral=True)

        # Locate the specific character sheet corresponding to the target player
        target_char_id = next((c_id for c_id, c in session.party_state.active_characters.items() if c.user_id == str(member.id)), None)
        if not target_char_id:
            return await interaction.response.send_message("❌ That user does not have an active character bound to this session's party array.", ephemeral=True)

        # Apply database state transformation update
        session.party_state.party_leader_id = target_char_id
        await session.save()

        await interaction.response.send_message(
            f"👑 **Vanguard Lead Token Transferred!**\n**{session.party_state.active_characters[target_char_id].name}** ({member.mention}) is now directing party navigation inputs on the map."
        )

async def setup(bot):
    await bot.add_cog(CoreCog(bot))
