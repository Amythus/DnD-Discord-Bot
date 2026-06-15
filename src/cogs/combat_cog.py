import discord
import random
from discord.ext import commands
from beanie import PydanticObjectId
from google import genai
from google.genai import types
from models.session import GameSession, CombatState, InitiativeTurn, SpeakerType, ChatMessage, NpcDelta
from models.node import Node
from models.monster import Monster
from utils.template_service import prompt_service
from views.combat_view import PlayerCombatAttackView

class CombatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ai_client = genai.Client()

    async def execute_automated_initiative_setup(self, channel: discord.TextChannel, session: GameSession):
        """
        Gathers all active characters and room monster blueprints from MongoDB, 
        rolls true random d20 initiative scores for everyone, sorts them, 
        and launches the first turn loop.
        """
        # 1. Fetch the active world-graph Node data from MongoDB via Beanie
        node = await Node.find_one(Node.node_id == session.party_state.current_room_id)
        initiative_list = []

        # 2. Roll automated, true random initiative for all active player characters
        for char_id, actor in session.party_state.active_characters.items():
            roll = random.randint(1, 20) + actor.initiative_modifier
            initiative_list.append(InitiativeTurn(entity_id=str(char_id), entity_type="PLAYER", roll_total=roll))

        # 3. Read creature templates from our universal node configuration
        for m_template in node.encounters:
            # Query the immutable stat records from the centralized Monster Manual registry
            monster_blueprint = await Monster.find_one(Monster.monster_id == m_template["creature_id"])
            if not monster_blueprint:
                continue
            
            # Spawn the precise quantity of individual minion tracking entities
            for qty in range(1, m_template["quantity"] + 1):
                instance_slug = f"{m_template['creature_id']}_{qty}" # e.g., "goblin_sentry_1"
                
                # Clone parameters into an isolated, mutable session delta state mapping
                session.npc_deltas[instance_slug] = NpcDelta(
                    current_hp=monster_blueprint.defenses.hit_points.average,
                    max_hp=monster_blueprint.defenses.hit_points.average,
                    attitude="HOSTILE",
                    status_conditions=[]
                )
                
                # Roll NPC initiative using passive perception as a baseline modifier proxy
                roll = random.randint(1, 20) + monster_blueprint.mobility_and_senses.passive_perception
                initiative_list.append(InitiativeTurn(entity_id=instance_slug, entity_type="NPC", roll_total=roll))

        # 4. Sort the initiative queue descending by roll_total, resolving ties using entity_id strings
        initiative_list.sort(key=lambda x: (x.roll_total, x.entity_id), reverse=True)

        # 5. Populate and commit the structural CombatState to MongoDB via Beanie
        session.combat_state = CombatState(
            in_combat=True,
            current_round=1,
            active_turn_index=0,
            initiative_order=initiative_list,
            active_readied_actions=[]
        )
        await session.save()

        # 6. Format and send the public initiative tracker scoreboard card to Discord
        order_board = "\n".join([f"**{idx+1}.** {turn.entity_id.replace('_',' ').title()} *(Roll: {turn.roll_total})*" for idx, turn in enumerate(initiative_list)])
        
        embed = discord.Embed(
            title="⚔️ Initiative Combat Commenced!", 
            description=f"The environment tightens as weapons are drawn!\n\n{order_board}", 
            color=discord.Color.red()
        )
        await channel.send(embed=embed)
        
        # 7. Step directly into the active processing cycle loop
        await self.process_active_combat_turn(channel, session)


    async def process_active_combat_turn(self, channel: discord.TextChannel, session: GameSession):
        """
        Evaluates who is next in line to act. Executes automated enemy AI scripts, 
        or resets player resources and prompts them with interactive button options.
        """
        # Extract the current active entity out of the sorted initiative list array
        active_turn = session.combat_state.initiative_order[session.combat_state.active_turn_index]

        # --- BRANCH A: AUTOMATED NPC ENEMY AI MONSTER BRAIN TURN ---
        if active_turn.entity_type == "NPC":
            npc_delta = session.npc_deltas.get(active_turn.entity_id)
            # Guardrail: If this minion was already defeated, skip its turn immediately
            if npc_delta.attitude == "DEAD":
                return await self.advance_combat_queue(channel, session)

            await channel.send(f"🤖 *{active_turn.entity_id.replace('_',' ').title()} compiles hostile tactical actions...*")
            # Hand over control to the automated script tool calculator
            await self.execute_automated_npc_turn(channel, session, active_turn.entity_id)

        # --- BRANCH B: ACTIVE PLAYER CHARACTER INTERACTIVE TURN ---
        else:
            actor = session.party_state.active_characters[active_turn.entity_id]
            
            # --- START-OF-TURN 2024 CORE RESOURCE RESET ---
            actor.turn_resources.action_used = False
            actor.turn_resources.bonus_action_used = False
            actor.turn_resources.free_object_interaction_used = False
            actor.turn_resources.has_stood_up_this_turn = False
            actor.turn_resources.movement_remaining_ft = actor.turn_resources.base_speed_ft
            
            # Scrub lingering round-based defensive buff states
            actor.turn_resources.is_dodging = False
            actor.turn_resources.is_disengaged = False
            
            # Scrub any un-triggered readied actions owned by this character from previous rounds
            session.combat_state.active_readied_actions = [
                ra for ra in session.combat_state.active_readied_actions 
                if ra.character_id != active_turn.entity_id
            ]
            await session.save()
            
            # Identify the first remaining living monster target inside Theatre of the Mind bounds
            first_live_npc = next((k for k, v in session.npc_deltas.items() if v.attitude != "DEAD"), None)
            
            # VICTORY CONDITION: If all npc_deltas are dead, terminate combat immediately
            if not first_live_npc:
                session.combat_state.in_combat = False
                await session.save()
                return await channel.send("🎉 **Victory! All hostiles inside the area have been completely neutralized!**")

            # Instantiate our interactive, compartmentalized weapon strike button template view canvas
            view = PlayerCombatAttackView(
                session_id=session.id,
                player_user_id=actor.user_id,
                actor_id=active_turn.entity_id,
                monster_instance_id=first_live_npc,
                attack_name="Longsword strike",
                hit_modifier=4, 
                target_ac=15 
            )

            await channel.send(
                content=f"🟢 <@{actor.user_id}>, it is your turn! **{actor.name}** targets **{first_live_npc.replace('_',' ').title()}**.\n"
                        f"Click the button below to resolve your attack options:",
                view=view
            )


    async def execute_automated_npc_turn(self, channel: discord.TextChannel, session: GameSession, npc_instance_id: str):
        """
        Runs the automated monster loop. Evaluates player readied actions first, 
        calls Gemini 3.1 Flash Lite for a tactical decision, runs random d20 math 
        locally, and updates player health pools deterministically.
        """
        npc_delta = session.npc_deltas.get(npc_instance_id)
        # Parse the base lookup key out of the unique instance string (e.g., "goblin_sentry_1" -> "goblin_sentry")
        base_creature_slug = "_".join(npc_instance_id.split("_")[:-1])
        
        monster_blueprint = await Monster.find_one(Monster.monster_id == base_creature_slug)
        node = await Node.find_one(Node.node_id == session.party_state.current_room_id)

        # --- THE PLAYER REACTION INTERCEPT SEARCH LAYER ---
        # Scan if any active player has an un-fired readied action waiting for this monster to strike
        intercepted_action = next((
            ra for ra in session.combat_state.active_readied_actions 
            if ra.entity_type == "PLAYER" and ra.target_entity_id == npc_instance_id and ra.trigger_keyword_condition == "attacks"
        ), None)

        if intercepted_action:
            # Burn reaction charge immediately out of memory to block exploitation loops
            session.combat_state.active_readied_actions.remove(intercepted_action)
            await session.save()

            player_actor = session.party_state.active_characters[intercepted_action.character_id]
            await channel.send(f"⚡ **REACTION INTERCEPT!** As the *{npc_instance_id.replace('_',' ').title()}* breaks cover, **{player_actor.name}** executes their readied action!")
            
            # Resolve the out-of-turn reaction attack natively in Python variables
            p_d20 = random.randint(1, 20)
            p_total = p_d20 + 4
            p_hit = p_total >= 15 
            
            if p_hit:
                dmg = random.randint(1, 8) + 2
                npc_delta.current_hp = max(0, npc_delta.current_hp - dmg)
                if npc_delta.current_hp = player.armor_class

        # Calculate and deduct weapon damage from player HP balances if the roll breaks their armor class
        damage = 0
        if hit_success:
            damage = random.randint(1, 6) + 1
            player.current_hp = max(0, player.current_hp - damage)

        await session.save()

        # Build clean structural validation data package ledger metrics
        math_payload = {
            "attacker_name": npc_instance_id.replace("_", " ").title(),
            "attack_name": decision.get("action_name", "Claw swipe"),
            "hit_roll_breakdown": f"{hit_breakdown_label} + 3 = **{total_hit}** vs Player AC {player.armor_class}",
            "hit_success": hit_success,
            "damage_dealt": damage,
            "target_name": player.name,
            "target_dead": player.current_hp <= 0
        }

        # Dispatch the validation blocks to the Storyteller listener, and advance initiative counters
        self.bot.dispatch("combat_turn_resolve", session.id, math_payload, channel)
        await self.advance_combat_queue(channel, session)


    async def advance_combat_queue(self, channel: discord.TextChannel, session: GameSession):
        """
        Increments the initiative pointer pointer. Handles round transition resets, 
        and invokes the universal trigger engine to check for round-based events [lost_mine_of_phandelver].
        """
        session.combat_state.active_turn_index += 1
        
        # ROTATION RESET: Check if the counter index has completed a full round rotation cycle
        if session.combat_state.active_turn_index >= len(session.combat_state.initiative_order):
            session.combat_state.active_turn_index = 0
            session.combat_state.current_round += 1
            await channel.send(f"🛡️ **Combat Round {session.combat_state.current_round} begins!**")

            # --- UNIVERSAL NODE BEHAVIOR TRIGGER ENGINE HOOK ---
            # Update the room's metadata state tracker natively inside MongoDB via Beanie
            node = await Node.find_one(Node.node_id == session.party_state.current_room_id)
            if "combat_round_counter" in node.node_metadata.room_states:
                node.node_metadata.room_states["combat_round_counter"] = session.combat_state.current_round
                await node.save()

                # Call the script evaluator to check if environmental triggers (like reinforcements) are met!
                from utils.trigger_engine import trigger_engine
                node, fired_trigger = await trigger_engine.evaluate_node_triggers(node, "round_end", "")

                if fired_trigger:
                    payload = {
                        "character_id": "ENVIRONMENT", "check_type": "WORLD_TRIGGER_EVENT",
                        "dc_target": 0, "final_score": 0, "math_breakdown": f"Trigger: {fired_trigger.action_required}",
                        "outcome": "SUCCESS", "raw_statement": fired_trigger.instruction_to_narrator 
                    }
                    # Halt the pipeline here! Let the storyteller print the hazard description block first!
                    self.bot.dispatch("rules_roll_complete", session.id, payload)
                    return 

        # Save all positional advancements and recurse down to process the next entity turn
        await session.save()
        await self.process_active_combat_turn(channel, session)

    


async def setup(bot):
    await bot.add_cog(CombatCog(bot))