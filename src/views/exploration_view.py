import discord
from beanie import PydanticObjectId
from database.models.session import GameSession
from database.models.node import Node

class ExplorationNavigationView(discord.ui.View):
    def __init__(self, session_id: PydanticObjectId, leader_user_id: str, current_node: Node):
        super().__init__(timeout=180)
        self.session_id = session_id
        self.leader_user_id = leader_user_id
        
        # 1. Build a fast lookup map out of our new structured Exit List
        # Only populate options if the secret path has been explicitly discovered by the party
        self.exit_lookup = {
            exit_node.direction.lower(): exit_node.target_node_id 
            for exit_node in current_node.navigation.exits 
            if exit_node.is_discovered
        }

        # 2. Automatically gray out compass button widgets if no discovered exit path is present
        if "north" not in self.exit_lookup: self.go_north.disabled = True
        if "south" not in self.exit_lookup: self.go_south.disabled = True
        if "east" not in self.exit_lookup: self.go_east.disabled = True
        if "west" not in self.exit_lookup: self.go_west.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.leader_user_id:
            await interaction.response.send_message("❌ Only the Vanguard Leader can navigate the world graph.", ephemeral=True)
            return False
        return True

    async def execute_move(self, interaction: discord.Interaction, direction: str):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        # Route target destination ID string directly down to the execution cog listener loop
        target_node_id = self.exit_lookup[direction]
        interaction.client.dispatch("party_move_execute", self.session_id, target_node_id, interaction.channel)

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
