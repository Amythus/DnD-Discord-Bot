import random
import discord
from discord.ext import commands
from database.models import GameSession, CharacterSheet

class TeamwideRollView(discord.ui.View):
    def __init__(self, channel_id: str, character_roster: list, mode: str, check_type: str, target_dc: int):
        super().__init__(timeout=180)
        self.channel_id = channel_id
        self.mode = mode
        self.check_type = check_type
        self.target_dc = target_dc
        
        self.rolls_tracker = {
            str(char.player_id): {
                "db_id": char.id,
                "name": char.character_name,
                "first_roll": None,
                "final_total": None,
                "math_breakdown": "",
                "has_2014_insp": char.vitals.has_inspiration,
                "has_2024_heroic": char.vitals.has_heroic_inspiration,
                "modifier": char.base_skills.get(check_type, 0)
            }
            for char in character_roster
        }

    def _generate_status_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"🎲 TEAMWIDE CHECK: DC {self.target_dc} {self.check_type}", color=discord.Color.blue())
        text = ""
        for p_id, d in self.rolls_tracker.items():
            if d["final_total"] is not None:
                text += f"✅ **{d['name']}**: `{d['final_total']}` ({d['math_breakdown']})\n"
            elif d["first_roll"] is not None and d["has_2024_heroic"]:
                text += f"⚡ **{d['name']}**: Rolled `{d['first_roll']}`... *Deciding Heroic Reroll...*\n"
            else:
                tags = []
                if d["has_2014_insp"]: tags.append("2014 Insp")
                if d["has_2024_heroic"]: tags.append("2024 Heroic")
                tag_str = f" *({', '.join(tags)} Available)*" if tags else ""
                text += f"⏳ **{d['name']}**: *Awaiting Initial Roll...*{tag_str}\n"
        embed.add_field(name="Party Roster", value=text, inline=False)
        return embed

    async def _check_and_finalize(self, interaction: discord.Interaction):
        """Verifies if every player has completely resolved their reroll choices."""
        # A player is done if they have a final_total OR if they chose not to use heroic loop
        all_done = all(d["final_total"] is not None for d in self.rolls_tracker.values())
        
        if all_done:
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(embed=self._generate_status_embed(), view=self)
            # Route to your Gemini Narrator logic pipeline here...
            await interaction.followup.send("🏁 All rolls locked! Sending results to the Dungeon Master...")
            self.stop()
        else:
            await interaction.message.edit(embed=self._generate_status_embed(), view=self)

    @discord.ui.button(label="🎲 INITIAL ROLL", style=discord.ButtonStyle.primary, custom_id="init_roll_btn")
    async def initial_roll_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if user_id not in self.rolls_tracker or self.rolls_tracker[user_id]["first_roll"] is not None:
            return
            
        await interaction.response.defer()
        data = self.rolls_tracker[user_id]
        
        # Standard Roll Execution
        d20 = random.randint(1, 20)
        data["first_roll"] = d20
        total = d20 + data["modifier"]
        
        # IF player lacks Heroic Inspiration, or if they passed anyway, lock it immediately!
        if not data["has_2024_heroic"] or total >= self.target_dc:
            data["final_total"] = total
            success_tag = "Success" if total >= self.target_dc else "Failure"
            data["math_breakdown"] = f"{success_tag} | Rolled {d20} + {data['modifier']}"
        
        # If they failed but HAVE Heroic Inspiration, the row stays open for a reroll command choice
        await self._check_and_finalize(interaction)

    @discord.ui.button(label="✨ USE 2014 INSPIRATION (ADV)", style=discord.ButtonStyle.success, custom_id="insp_2014_btn")
    async def legacy_insp_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        data = self.rolls_tracker.get(user_id)
        if not data or data["first_roll"] is not None or not data["has_2014_insp"]:
            return
            
        await interaction.response.defer()
        
        # 2014 Advantage calculation (rolled upfront)
        r1, r2 = random.randint(1, 20), random.randint(1, 20)
        final_d20 = max(r1, r2)
        total = final_d20 + data["modifier"]
        
        # Consume item from MongoDB
        char = await CharacterSheet.find_one(CharacterSheet.id == data["db_id"])
        char.vitals.has_inspiration = False
        await char.save()
        
        data["first_roll"] = final_d20
        data["final_total"] = total
        success_tag = "Success" if total >= self.target_dc else "Failure"
        data["math_breakdown"] = f"{success_tag} | Adv Max({r1}, {r2}) + {data['modifier']}"
        data["has_2014_insp"] = False
        
        await self._check_and_finalize(interaction)

    @discord.ui.button(label="⚡ ACTIVATE HEROIC REROLL", style=discord.ButtonStyle.danger, custom_id="heroic_2024_btn")
    async def heroic_reroll_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        data = self.rolls_tracker.get(user_id)
        
        # Can only click if they have already taken their initial roll, haven't finalized, and have the resource
        if not data or data["first_roll"] is None or data["final_total"] is not None or not data["has_2024_heroic"]:
            await interaction.response.send_message("You cannot trigger a Heroic Reroll right now.", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        # New roll completely overrides the original roll total
        new_d20 = random.randint(1, 20)
        total = new_d20 + data["modifier"]
        
        # Mutate database state
        char = await CharacterSheet.find_one(CharacterSheet.id == data["db_id"])
        char.vitals.has_heroic_inspiration = False
        await char.save()
        
        data["final_total"] = total
        success_tag = "Success" if total >= self.target_dc else "Failure"
        data["math_breakdown"] = f"{success_tag} | **Heroic Reroll:** {new_d20} + {data['modifier']} (Dropped {data['first_roll']})"
        data["has_2024_heroic"] = False
        
        await self._check_and_finalize(interaction)
