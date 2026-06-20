import discord
from discord.ext import commands
from discord import app_commands
from services.ddb_parser import DDBParserService

class ImportCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="import", description="Import or sync your character from D&D Beyond")
    @app_commands.describe(character_link="The URL or ID of your D&D Beyond character")
    async def import_character(self, interaction: discord.Interaction, character_link: str):
        # 1. Asynchronous Deferral (Prevents Discord loop timeout while waiting on APIs)
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 2. Pass to the parsing engine, injecting the Discord Owner ID to prevent state drift
            character = await DDBParserService.import_character(
                dndb_url=character_link, 
                discord_user_id=interaction.user.id
            )
            
            # 3. Successful Upsert Formatting
            embed = discord.Embed(
                title="Character Synced Successfully!",
                description=f"**{character.name}** (Level {character.level} {character.race})\nhas been securely added to the Global Tracker.",
                color=discord.Color.green()
            )
            
            # Use followup.send because we deferred the original response
            await interaction.followup.send(embed=embed)
            
        except ValueError as e:
            # Captures validation issues like bad links
            await interaction.followup.send(f"**Import Error**: {str(e)}", ephemeral=True)
            
        except Exception as e:
            # Captures unexpected LLM or HTTpx timeout issues
            await interaction.followup.send(f"An unexpected engine error occurred: {str(e)}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ImportCog(bot))