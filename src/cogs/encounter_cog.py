import random
import discord
from discord.ext import commands
# from beanie.odm.operators.find.array import In
from database.models import GameSession, CharacterSheet, ReadiedAction
from services.gemini_client import gemini_service
from services.game_engine import game_engine

class EncounterRollView(discord.ui.View):
    def __init__(self, channel_id: str, character_roster: list, mode: str, check_type: str, target_dc: int, readied_triggers: list = None):
        super().__init__(timeout=180)
        self.channel_id = channel_id
        self.mode = mode               # "INITIATIVE", "GROUP_CHECK", "SAVING_THROW", "TRIGGERED_REACTION"
        self.check_type = check_type
        self.target_dc = target_dc
        self.readied_triggers = readied_triggers or []
        self.rolls_tracker = {}
        
        for char in character_roster:
            p_id = str(char.player_id)
            self.rolls_tracker[p_id] = {
                "db_id": char.id,
                "name": char.character_name,
                "roll_total": None,
                "math_breakdown": "",
                "vitals_ref": char.vitals,
                "modifier": char.vitals.initiative_bonus if mode == "INITIATIVE" else char.base_skills.get(check_type, 0),
                "is_reaction": False,
                "action_text": f"Performs {check_type} Check"
            }

        for trigger in self.readied_triggers:
            p_id = str(trigger.player_id)
            if p_id in self.rolls_tracker:
                self.rolls_tracker[p_id]["is_reaction"] = True
                self.rolls_tracker[p_id]["action_text"] = f"⚡ REACTION: {trigger.held_action}"

    def _generate_status_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"⚔️ TACTICAL ENCOUNTER: {self.mode}", color=discord.Color.dark_purple())
        text = ""
        for p_id, d in self.rolls_tracker.items():
            if d["roll_total"] is not None:
                text += f"✅ **{d['name']}**: `{d['roll_total']}` ({d['math_breakdown']})\n"
            elif d["is_reaction"]:
                text += f"⚡ **{d['name']}**: *Readied Trigger Online!* -> `{d['action_text']}`\n"
            else:
                text += f"⏳ **{d['name']}**: *Awaiting Roll...*\n"
        embed.add_field(name="Encounter Sequence Queue", value=text, inline=False)
        return embed

    @discord.ui.button(label="🎲 EXECUTE ROLL", style=discord.ButtonStyle.primary, custom_id="enc_roll_btn")
    async def standard_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if user_id not in self.rolls_tracker or self.rolls_tracker[user_id]["roll_total"] is not None: return
        await interaction.response.defer()
        
        data = self.rolls_tracker[user_id]
        d20 = random.randint(1, 20)
        
        # 💎 EVALUATE BUFF MODIFIERS CONCURRENTLY ON MULTI-USER ROSTER TARGETS
        action_cat = "saving_throws" if self.mode == "SAVING_THROW" else "skills"
        buff_bonus, buff_breakdown = game_engine.evaluate_active_buffs(data["vitals_ref"], action_cat)
        
        total = d20 + data["modifier"] + buff_bonus
        data["roll_total"] = total
        
        success_tag = "Success" if total >= self.target_dc else "Failure"
        data["math_breakdown"] = f"{success_tag} | Rolled {d20} + {data['modifier']} (Base) {buff_breakdown}"

        all_done = all(d["roll_total"] is not None for d in self.rolls_tracker.values())
        if all_done:
            button.disabled = True
            await interaction.message.edit(embed=self._generate_status_embed(), view=self)
            await self._dispatch_to_narrator(interaction)
        else:
            await interaction.message.edit(embed=self._generate_status_embed(), view=self)

    async def _dispatch_to_narrator(self, interaction: discord.Interaction):
        session = await GameSession.find_one(GameSession.channel_id == self.channel_id, fetch_links=True)
        summary = f"Encounter State resolution: {self.mode} ({self.check_type} DC {self.target_dc})\n"
        for d in self.rolls_tracker.values():
            summary += f"- {d['name']} {d['action_text']}: Total Result {d['roll_total']} ({d['math_breakdown']})\n"

        session.readied_actions = []
        await session.save()

        client = gemini_service.get_client()
        module_file_handle = client.files.get(name=session.active_module.gemini_file_uri.split('/')[-1])
        
        prompt = f"An atmospheric encounter event resolved.\n{summary}\nNarrate the consequence scene utilizing Rule of Cool."
        response = client.models.generate_content(model=gemini_service.model_name, contents=[module_file_handle, prompt])
        await interaction.followup.send(response.text)
        self.stop()

class EncounterCog(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.command(name="ready")
    async def ready_action_cmd(self, ctx: commands.Context, trigger: str, action: str):
        channel_id, player_id = str(ctx.channel.id), str(ctx.author.id)
        session = await GameSession.find_one(GameSession.channel_id == channel_id)
        char = await CharacterSheet.find_one(CharacterSheet.channel_id == channel_id, CharacterSheet.player_id == player_id)
        if not session or not char: return

        session.readied_actions.append(ReadiedAction(player_id=player_id, character_name=char.character_name, trigger_condition=trigger.strip(), held_action=action.strip()))
        await session.save()
        await ctx.reply(f"🎯 **Action Anchored:** {char.character_name} readies: *\"{action}\"* on trigger *\"{trigger}\"*.")

    @commands.command(name="event_trigger", aliases=["trigger", "ev"])
    async def trigger_event_cmd(self, ctx: commands.Context, event_desc: str, check_type: str = "Perception", dc: int = 12):
        if not ctx.author.guild_permissions.administrator: return
        channel_id = str(ctx.channel.id)
        session = await GameSession.find_one(GameSession.channel_id == channel_id, fetch_links=True)
        active_triggers = session.readied_actions
        
        if active_triggers:
            roster = await CharacterSheet.find(CharacterSheet.channel_id == channel_id, In(CharacterSheet.player_id, [t.player_id for t in active_triggers])).to_list()
            mode = "TRIGGERED_REACTION"
        else:
            roster = await CharacterSheet.find(CharacterSheet.channel_id == channel_id).to_list()
            mode = "GROUP_CHECK" if "Save" not in check_type else "SAVING_THROW"

        view = EncounterRollView(channel_id, roster, mode, check_type, dc, active_triggers)
        await ctx.send(embed=view._generate_status_embed(), view=view)

async def setup(bot): await bot.add_cog(EncounterCog(bot))
