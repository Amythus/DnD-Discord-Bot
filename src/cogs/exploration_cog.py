import discord
from discord.ext import commands
from beanie import PydanticObjectId
from database.models.session import GameSession
from database.models.node import Node

class ExplorationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="move", aliases=["go", "head"])
    async def text_move_command(self, ctx, direction: str):
        """Processes cardinal movement inputs (north, south, east, west) from player chat text."""
        target_dir = direction.strip().lower()
        if target_dir not in ["north", "south", "east", "west"]:
            return await ctx.send("❌ **Invalid Direction!** Please provide a cardinal compass heading: `north`, `south`, `east`, or `west`.")

        # 1. Look up the caller's active running game session
        session = await GameSession.find_one({"party_state.active_characters.user_id": str(ctx.author.id)})
        if not session:
            return await ctx.send("❌ You are not currently linked to an active campaign session.")
            
        if session.combat_state.in_combat:
            return await ctx.send("❌ You cannot change map locations casually while locked in active initiative combat structure.")

        # 2. Enforce Lead Token rules: Only the designated party leader can direct movement
        if str(session.party_state.party_leader_id) != str(ctx.author.id) and session.party_state.active_characters.get(str(session.party_state.party_leader_id)).user_id != str(ctx.author.id):
            return await ctx.send("❌ Only the appointed Vanguard Party Leader can navigate the group to new areas.")

        # 3. Pull the active world-graph Node from MongoDB
        current_node = await Node.find_one(Node.node_id == session.party_state.current_room_id)
        
        # 4. Search the Exit List for a matching discovered cardinal direction
        matched_exit = next((
            ex for ex in current_node.navigation.exits 
            if ex.direction.lower() == target_dir and ex.is_discovered
        ), None)

        if not matched_exit:
            return await ctx.send(f"❌ There is no visible, accessible exit leading **{target_dir.upper()}** from here.")

        if matched_exit.is_locked:
            return await ctx.send(f"🚧 The path to the {target_dir.upper()} is blocked! The **{matched_exit.type.replace('_',' ').title()}** is currently locked securely.")

        # 5. Execute the move action natively in Python
        await self.execute_party_transition(session, matched_exit.target_node_id, target_dir, ctx.channel)

    async def execute_party_transition(self, session: GameSession, target_node_id: str, direction_moved: str, channel: discord.TextChannel):
        """Mutates document states and dispatches the transition payload down to the Narrative Engine."""
        # Save new location ID directly to MongoDB via Beanie
        session.party_state.current_room_id = target_node_id
        await session.save()

        # Fetch the newly targeted destination graph node
        new_node = await Node.find_one(Node.node_id == target_node_id)

        # Compile sensory notes out of the new node's properties
        sensory_notes = []
        if new_node.sensory_profile.ambient_sound: sensory_notes.append(f"Sounds: {new_node.sensory_profile.ambient_sound}")
        if new_node.sensory_profile.olfactory_clue: sensory_notes.append(f"Smell: {new_node.sensory_profile.olfactory_clue}")
        if new_node.sensory_profile.thermal_clue: sensory_notes.append(f"Temperature: {new_node.sensory_profile.thermal_clue}")
        compiled_sensory_string = " | ".join(sensory_notes) if sensory_notes else "None detected."

        # Compile structural data validation payload packet straight to Narrative layer
        payload = {
            "character_id": str(session.party_state.party_leader_id),
            "check_type": "THEATRE_OF_THE_MIND_MOVE",
            "dc_target": 0,
            "final_score": 0,
            "math_breakdown": f"Moved {direction_moved.upper()} into {new_node.title}. Sensory data: {compiled_sensory_string}",
            "outcome": "SUCCESS",
            "raw_statement": f"We move to the {direction_moved.upper()}."
        }

        # Fire event hook to let NarrativeEngineCog compile prose and print the description
        self.bot.dispatch("rules_roll_complete", session.id, payload)

async def setup(bot):
    await bot.add_cog(ExplorationCog(bot))
