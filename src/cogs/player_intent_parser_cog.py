import os
import json
import discord
from discord.ext import commands
from google import genai
from google.genai import types

from database.models.session import GameSession
from database.models.node import Node
from utils.template_service import prompt_service

class PlayerIntentParserCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Instantiate the Google GenAI Connection Client targeting Gemini 3.1 Flash Lite
        self.ai_client = genai.Client()

    async def evaluate_environmental_noise(self, channel: discord.TextChannel, session: GameSession, node: Node, text: str) -> bool:
        """
        Scans a text substring for heavy sonic/acoustic disruptions.
        Triggers the state machine's loud noise trigger if an anomaly is caught.
        """
        noise_keywords = ["shout", "scream", "yell", "shouted", "screamed", "shouts", "yells", "loud", "slam", "slams"]
        
        if any(kw in text.lower() for kw in noise_keywords):
            from utils.trigger_engine import trigger_engine
            # Run the Python state evaluator checking for our exact metadata flag key
            node, fired_trigger = await trigger_engine.evaluate_node_triggers(
                node, 
                trigger_type="player_action", 
                condition_key="sudden_movement_or_loud_noise"
            )

            if fired_trigger:
                # Compile structural notification package and dispatch to the Narrator Engine
                payload = {
                    "character_id": "ENVIRONMENT",
                    "check_type": "WORLD_TRIGGER_EVENT",
                    "dc_target": 0, "final_score": 0,
                    "math_breakdown": f"Acoustic Trigger Fired: {fired_trigger.action_required}",
                    "outcome": "SUCCESS",
                    "raw_statement": fired_trigger.instruction_to_narrator 
                }
                self.bot.dispatch("rules_roll_complete", session.id, payload)
                return True # Signal that an environmental alert was triggered
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Primary intercept hook. Listens to chat messages, splits multi-intents,
        scans for acoustics, and routes sub-actions to correct cogs sequentially.
        """
        # Enforce baseline boundary checks: Ignore bot chat and standard explicit command prefix tokens
        if message.author.bot or message.content.startswith("!") or message.content.startswith("/"):
            return

        # 1. Fetch active session mapping this user profile ID
        session = await GameSession.find_one({"party_state.active_characters.user_id": str(message.author.id)})
        if not session:
            return

        # 2. Enforce strict turn lock during combat initiatives
        if session.combat_state.in_combat:
            active_turn = session.combat_state.initiative_order[session.combat_state.active_turn_index]
            # Fetch character data bound to active position index
            active_actor = session.party_state.active_characters.get(active_turn.entity_id)
            if active_actor and active_actor.user_id != str(message.author.id):
                # Suppress typing inputs out of turn bounds to keep initiative stable
                return await message.channel.send(f"❌ Hold on, it is currently **{active_actor.name}**'s turn to act!")

        # 3. Query the active world-graph Node model from MongoDB via Beanie
        node = await Node.find_one(Node.node_id == session.party_state.current_room_id)
        if not node:
            return

        # --- STEP 4: Render Prompt and Call Gemini 3.1 Flash Lite Intent Brain ---
        prompt = prompt_service.render_prompt(
            "player_intent_parser.jinja",
            node=node,
            player_input=message.content
        )

        try:
            response = self.ai_client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Strict maximum classification consistency
                    response_mime_type="application/json"
                )
            )

            # 5. Clean output code fences and parse into atomic loop actions
            parsed_payload = prompt_service.clean_json_response(response.text)
            actions = parsed_payload.get("actions", [])

            # --- STEP 6: Chronological Routing Sequence ---
            for idx, action in enumerate(actions):
                category = action["category"]
                sub_text = action["extracted_sub_text"]
                target_id = action.get("target_id")

                # Track if this action sets off an environmental alert first
                await self.evaluate_environmental_noise(message.channel, session, node, sub_text)

                # BRANCH A: DIALOGUE WITH LOCAL NPC
                if category == "DIALOGUE":
                    # Locate matching target identity profile dictionary registered to the node
                    npc_profile = next((npc.__dict__ for npc in node.npc_profiles if npc.npc_id == target_id), None)
                    if not npc_profile:
                        npc_profile = {"npc_id": target_id or "unknown_npc", "base_demeanor": "Mysterious stranger."}
                        
                    self.bot.dispatch(
                        "intent_dialogue_execute", 
                        message.channel, 
                        session, 
                        npc_profile, 
                        sub_text, 
                        message.author.id
                    )

                # BRANCH B: TACTICAL STATUS CHECK / STAGING QUESTIONS
                elif category == "STATUS_CHECK":
                    # Pass straight to the DM-Assistant Referee helper pipeline
                    self.bot.dispatch(
                        "intent_status_check_execute", 
                        message.channel, 
                        session, 
                        node, 
                        sub_text, 
                        message.author.id
                    )

                # BRANCH C: DEFINITIVE PHYSICAL PLAYER MANEUVERS & ACTIONS
                elif category == "PLAYER_ACTION":
                    # Hand over to the RulesEngine or Combat cogs to challenge success parameters via dice
                    self.bot.dispatch(
                        "intent_action_execute", 
                        message.channel, 
                        session, 
                        sub_text, 
                        message.author.id
                    )

        except Exception as e:
            print(f"❌ Intent Parser Pipeline Exception Caught: {e}")
            # Fallback guard: If parsing fails, route raw text to the action cog to keep the loop moving
            self.bot.dispatch("intent_action_execute", message.channel, session, message.content, message.author.id)

async def setup(bot):
    await bot.add_cog(PlayerIntentParserCog(bot))
