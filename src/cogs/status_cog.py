import discord
from discord.ext import commands
from datetime import datetime
from database.models import GameSession, CharacterSheet, RoomContext

class StatusCog(commands.Cog):
    """
    Manages local game state tracking. Delivers real-time character sheets, 
    vitals, spell slots, and inventory states using high-speed $0-cost MongoDB lookups.
    """
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="status", aliases=["st", "sheet"])
    async def get_status(self, ctx: commands.Context):
        """
        Fetches and beautifully formats the current user's stateless-delta character sheet
        within the active channel session into a Discord Rich Embed.
        """
        channel_id = str(ctx.channel.id)
        player_id = str(ctx.author.id)

        # 1. Fetch Active Session State to identify the room location
        session = await GameSession.find_one(GameSession.channel_id == channel_id)
        if not session:
            await ctx.reply("❌ **Error:** No active campaign session running in this channel.")
            return

        # 2. Fetch Player Character Sheet constrained to this unique session
        character = await CharacterSheet.find_one(
            CharacterSheet.channel_id == channel_id,
            CharacterSheet.player_id == player_id
        )
        if not character:
            await ctx.reply("❌ **Error:** You haven't checked a character sheet into this session yet. Use `/join_session`.")
            return

        # Fetch current room metadata to display the room title
        room = await RoomContext.find_one(
            RoomContext.module_slug == session.active_module.id if hasattr(session.active_module, 'id') else session.active_module,
            RoomContext.room_id == session.current_room_id
        )
        room_title = room.room_title if room else f"Unknown Zone ({session.current_room_id})"

        # 3. Resolve Stateless-Delta HP values
        # If session_current_hp is None, it means they are at full health (matching base_max_hp)
        current_hp = character.vitals.session_current_hp
        if current_hp is None:
            current_hp = character.vitals.base_max_hp

        # Determine alignment color indicator (Green/Orange/Red) based on health ratio
        hp_ratio = current_hp / character.vitals.base_max_hp
        embed_color = discord.Color.green() if hp_ratio > 0.5 else (discord.Color.orange() if hp_ratio > 0.2 else discord.Color.red())

        # 4. Construct the Core Rich Embed
        embed = discord.Embed(
            title=f"🛡️ Character Profile: {character.character_name}",
            description=f"**Class/Level:** {character.class_and_level} | **Current Location:** {room_title}",
            color=embed_color,
            timestamp=datetime.utcnow()
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

        # 5. Core Vitals & Attributes Field
        vitals_text = (
            f"❤️ **HP:** `{current_hp}` / `{character.vitals.base_max_hp}`"
            f"{f' *(+{character.vitals.temp_hp} Temp)*' if character.vitals.temp_hp > 0 else ''}\n"
            f"🛡️ **AC:** `{character.vitals.base_ac}` | 🥾 **Speed:** `{character.vitals.speed} ft` | 🎲 **Init:** `+{character.vitals.initiative_bonus}`"
        )
        
        # Add conditions tracker metadata if they are actively suffering from anything
        if character.vitals.active_conditions:
            vitals_text += f"\n⚠️ **Conditions:** *{', '.join(character.vitals.active_conditions)}*"
        else:
            vitals_text += "\n⚠️ **Conditions:** *None*"

        embed.add_field(name="📊 Vitals & Combat Stats", value=vitals_text, inline=False)

        # 6. Core 6 Attribute Scores Field
        stats_text = (
            f"💪 **STR:** `{character.stats.get('strength', 10)}` | "
            f"🏃 **DEX:** `{character.stats.get('dexterity', 10)}` | "
            f"🪵 **CON:** `{character.stats.get('constitution', 10)}`\n"
            f"🧠 **INT:** `{character.stats.get('intelligence', 10)}` | "
            f"🦉 **WIS:** `{character.stats.get('wisdom', 10)}` | "
            f"✨ **CHA:** `{character.stats.get('charisma', 10)}`"
        )
        embed.add_field(name="🧬 Ability Scores", value=stats_text, inline=False)

        # 7. Spellcasting Tracker Field (Optional evaluation based on character class)
        if character.spellcasting and character.spellcasting.max_slots:
            spell_lines = []
            for tier, max_val in character.spellcasting.max_slots.items():
                used = character.spellcasting.used_slots.get(tier, 0)
                available = max_val - used
                # Render spell slots visually using filled and empty circle indicators
                circles = "🔴 " * used + "🔵 " * available
                spell_lines.append(f"**{tier} Level:** {circles} `({available}/{max_val})`")
            
            embed.add_field(name="🔮 Spell Slots Remaining", value="\n".join(spell_lines), inline=False)

        # 8. Dynamic Inventory Tracking Field
        if character.inventory:
            loot_items = []
            base_items = []
            for item in character.inventory:
                item_str = f"• {item.name} x{item.quantity}"
                if item.is_loot_found_mid_session:
                    loot_items.append(f"{item_str} ✨ *(Loot)*")
                else:
                    base_items.append(item_str)
            
            # Combine inventories, listing fresh dungeon loot found first
            inventory_list = loot_items + base_items
            # Cap long text arrays to prevent breaking Discord field char limits
            if len(inventory_list) > 8:
                inventory_text = "\n".join(inventory_list[:7]) + f"\n*...and {len(inventory_list) - 7} more items.*"
            else:
                inventory_text = "\n".join(inventory_list) if inventory_list else "*Empty pockets.*"
        else:
            inventory_text = "*Empty pockets.*"
            
        embed.add_field(name="🎒 Backpack & Equipment", value=inventory_text, inline=True)

        # 9. Proficiencies High-Level Tags Field
        prof_tags = []
        if hasattr(character, 'proficiencies') and character.proficiencies:
            if character.proficiencies.tools:
                prof_tags.append(f"🛠️ **Tools:** {', '.join(character.proficiencies.tools[:3])}")
            if character.proficiencies.weapons:
                prof_tags.append(f"⚔️ **Weapons:** {', '.join(character.proficiencies.weapons[:3])}")
            if character.proficiencies.armor:
                prof_tags.append(f"🛡️ **Armor:** {', '.join(character.proficiencies.armor[:3])}")
        
        prof_text = "\n".join(prof_tags) if prof_tags else "*No special gear training.*"
        embed.add_field(name="📜 Trained Proficiencies", value=prof_text, inline=True)

        embed.set_footer(text=f"Session Tracker ID: {channel_id} | Core rules validated local.")
        
        # Dispatch final visual card presentation layout back to the player
        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(StatusCog(bot))
