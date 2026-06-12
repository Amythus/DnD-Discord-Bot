import discord
import random
from beanie import PydanticObjectId
from typing import List
from database.models.character import CharacterSheet
from database.models.session import GameSession, SessionStatus, PartyState, CombatState, NarrativeMemory, ActiveCharacterState

class ExplorationNavigationView(discord.ui.View):
    def __init__(self, session_id: PydanticObjectId, leader_user_id: str, available_exits: dict):
        super().__init__(timeout=180)
        self.session_id = session_id
        self.leader_user_id = leader_user_id
        self.available_exits = available_exits

        # Dynamically disable button pointers if no valid room connection exists
        if available_exits.get("north", "none") == "none": self.go_north.disabled = True
        if available_exits.get("south", "none") == "none": self.go_south.disabled = True
        if available_exits.get("east", "none") == "none": self.go_east.disabled = True
        if available_exits.get("west", "none") == "none": self.go_west.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Enforces Lead Token rules: Only the party leader can advance the map."""
        if str(interaction.user.id) != self.leader_user_id:
            await interaction.response.send_message("❌ Only the appointed Party Leader can navigate the map layout.", ephemeral=True)
            return False
        return True

    async def execute_move(self, interaction: discord.Interaction, direction: str):
        """Processes room transition state updates natively in Python code."""
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        target_room_id = self.available_exits[direction]
        
        # Dispatch move event over to the ExplorationCog namespace loop
        interaction.client.dispatch("party_move_execute", self.session_id, target_room_id, interaction.channel)

    @discord.ui.button(label="North", style=discord.ButtonStyle.primary, emoji="⬆️", row=0)
    async def go_north(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.execute_move(interaction, "north")

    @discord.ui.button(label="West", style=discord.ButtonStyle.primary, emoji="⬅️", row=1)
    async def go_west(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.execute_move(interaction, "west")

    @discord.ui.button(label="South", style=discord.ButtonStyle.primary, emoji="⬇️", row=1)
    async def go_south(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.execute_move(interaction, "south")

    @discord.ui.button(label="East", style=discord.ButtonStyle.primary, emoji="➡️", row=1)
    async def go_east(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.execute_move(interaction, "east")

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

class ModuleSelectMenu(discord.ui.Select):
    def __init__(self, campaign_slugs: List[str], dm_id: int):
        self.dm_id = dm_id
        options = [
            discord.SelectOption(
                label=slug.replace("_", " ").title(),
                description=f"Initialize lobby with layout blueprint: {slug}",
                value=slug,
                emoji="📖"
            ) for slug in campaign_slugs
        ]
        super().__init__(
            placeholder="Select a campaign module to initialize the lobby...",
            min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        selected_campaign_id = self.values

        # 1. Instantiate the live GameSession document inside MongoDB right here
        new_session = GameSession(
            campaign_id=selected_campaign_id,
            session_status=SessionStatus.LOBBY, # Set to LOBBY so players can join
            party_state=PartyState(
                current_region_id=selected_campaign_id,
                current_room_id=f"{selected_campaign_id}_lvl1_room_01", # Target starting room pointer
                party_leader_id=None, # Assigned dynamically when players register
                active_characters={}
            ),
            combat_state=CombatState(in_combat=False),
            narrative_memory=NarrativeMemory(campaign_summary_so_far="Lobby initialized. Waiting for players.")
        )
        await new_session.insert()

        self.view.stop()
        await interaction.edit_original_response(content=f"✅ **Lobby Created!** Campaign set to `{selected_campaign_id}`.", view=None)

        # 2. Broadcast public invitation embed out to the channel chat space
        embed = discord.Embed(
            title=f"🏰 Campaign Lobby Opened: {selected_campaign_id.replace('_', ' ').title()}",
            description="The Dungeon Master has established an active game server workspace!\n\n"
                        "👉 **Step 1: Players Join**\nEveryone playing tonight must type the command:\n`/join_session`\n\n"
                        "🏁 **Step 2: DM Begins Game**\nOnce all heroes have selected their sheets, the DM can kick off the story by typing:\n`/begin_campaign`",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Database Session ID: {new_session.id}")
        await interaction.channel.send(embed=embed)

class ModuleStartView(discord.ui.View):
    def __init__(self, campaign_slugs: List[str], dm_id: int):
        super().__init__(timeout=60)
        self.add_item(ModuleSelectMenu(campaign_slugs, dm_id))
        
class CharacterJoinView(discord.ui.View):
    def __init__(self, characters: List[CharacterSheet], session_id: PydanticObjectId, voter_id: int):
        super().__init__(timeout=60)
        self.voter_id = voter_id
        # Append the dropdown select component list to the active view pane
        self.add_item(CharacterSelectMenu(characters, session_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Enforces execution checks so only the calling command user can select their sheet choice."""
        if interaction.user.id != self.voter_id:
            await interaction.response.send_message("❌ Run `/join_session` on your own profile to pick your adventurer choice!", ephemeral=True)
            return False
        return True
