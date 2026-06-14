import discord
from discord.ext import commands
from jinja2 import Environment, FileSystemLoader
from google import genai
from google.genai import types

from database.models.session import GameSession, SpeakerType, ChatMessage
from database.models.room import Room

class NarrativeEngineCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 1. Load the Jinja2 file environment
        self.jinja_env = Environment(loader=FileSystemLoader("templates"))
        # 2. Instantiate the Google GenAI Client
        self.ai_client = genai.Client()

    @commands.Cog.listener()
    async def on_rules_roll_complete(self, session_id, payload: dict):
        """
        Triggered automatically whenever a player's dice roll sequence resolves.
        Stitches database context and requests descriptive prose from Gemini.
        """
        # 1. Fetch active session state from MongoDB via Beanie
        session = await GameSession.get(session_id)
        if not session:
            return

        # 2. Fetch immutable structural details of the current room
        room = await Room.find_one(Room.room_id == session.party_state.current_room_id)
        
        # 3. Locate the specific character name
        actor_id = payload["character_id"]
        actor = session.party_state.active_characters[str(actor_id)]
        
        # Locate target channel from the active bot cache
        # (In production, store a target 'channel_id' inside your GameSession schema)
        channel = self.bot.get_channel(int(actor.user_id)) 
        if not channel:
            # Fallback to searching active channel structures if user matching fails
            for guild in self.bot.guilds:
                for ch in guild.text_channels:
                    if ch.permissions_for(guild.me).send_messages:
                        channel = ch
                        break

        # --- STEP 1: Render Immersive Narrative Prompt Stack ---
        template = self.jinja_env.get_template("narrator_player_action.jinja")
        narrator_prompt = template.render(
            room=room, 
            session=session, 
            payload=payload, 
            actor_name=actor.name
        )

        # Send a typing indicator to simulate the DM describing the scene
        async with channel.typing():
            # --- STEP 2: Invoke Gemini 3.1 Flash Lite Prose Generator ---
            # (Note: Explicit context caching would hook onto this specific prompt prefix)
            response = self.ai_client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=narrator_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.8,  # Higher temperature allows for colorful, creative prose descriptions
                )
            )
            
            story_text = response.text

        # --- STEP 3: Append Transactional Records to History Logs ---
        if payload["check_type"] != "FLAVOR_ACTION":
            session.narrative_memory.recent_chat_history.append(
                ChatMessage(speaker=SpeakerType.RULES_ENGINE, text=f"{actor.name}: {payload['math_breakdown']} -> {payload['outcome']}")
            )
        session.narrative_memory.recent_chat_history.append(
            ChatMessage(speaker=SpeakerType.NARRATOR, text=story_text)
        )
        
        # Commit running log updates securely to MongoDB
        await session.save()

        # --- STEP 4: Post the Final Immersive Embed block ---
        embed = discord.Embed(
            title=f"📖 {actor.name}'s Action Resolves",
            description=story_text,
            color=discord.Color.gold() if payload["outcome"] == "SUCCESS" else discord.Color.dark_grey()
        )
        if payload["check_type"] != "FLAVOR_ACTION":
            embed.set_footer(text=f"Math Ledger: {payload['math_breakdown']} (vs DC {payload['dc_target']})")
            
        await channel.send(embed=embed)


    @commands.Cog.listener()
    async def on_intent_dialogue_execute(self, channel, session: GameSession, npc_profile: dict, player_speech_text: str, user_id: int):
        """
        Processes conversational roleplay intents. Scans player speech text against 
        node behavior triggers before using Gemini 3.5 to render the NPC's in-character response.
        """
        # 1. Fetch active node blueprint to analyze current behavior triggers
        node = await Node.find_one(Node.node_id == session.party_state.current_room_id)
        character_id = next((c_id for c_id, c in session.party_state.active_characters.items() if c.user_id == str(user_id)), None)
        actor = session.party_state.active_characters[character_id]

        fired_social_trigger = None

        # 2. Iterate through behavioral structures to check for matching conversation cues
        if npc_profile:
            # Cast raw model object data parameters safely
            for trigger in node.node_metadata.behavior_triggers:
                if trigger.trigger_type != "player_action":
                    continue
                
                # Check if the player speech contains a specific conditional phrase
                # Example: If trigger condition is "ordered_boiling_oil", check if "boiling oil" is in their input text
                clean_condition = trigger.condition.replace("_", " ").lower()
                if clean_condition in player_speech_text.lower():
                    # Match caught! Invoke trigger processing mechanics
                    fired_social_trigger = trigger
                    
                    # Update room metadata flags natively in MongoDB to track this choice
                    node.node_metadata.room_states[trigger.condition] = True
                    # Remove trigger so it doesn't fire repeatedly
                    node.node_metadata.behavior_triggers.remove(trigger)
                    await node.save()
                    break

        # --- STEP 3: Render Social Dialogue Prompt Context ---
        template = self.jinja_env.get_template("narrator_social_dialogue.jinja")
        prompt = template.render(
            node=node,
            npc=npc_profile,
            fired_trigger=fired_social_trigger,
            player_speech_text=player_speech_text
        )

        async with channel.typing():
            # Call Gemini 3.5 Flash. We use 3.5 here for its superior linguistic comprehension 
            # and emotional pacing during roleplay scenes
            response = self.ai_client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.85, # Rich emotional and behavioral variety
                )
            )
            npc_response_text = response.text

        # 4. Save the conversation exchange directly to the rolling chat logs for history tracking
        from models.session import ChatMessage, SpeakerType
        session.narrative_memory.recent_chat_history.append(
            ChatMessage(speaker=SpeakerType.PLAYER, sender_name=actor.name, text=player_speech_text)
        )
        session.narrative_memory.recent_chat_history.append(
            ChatMessage(speaker=SpeakerType.NARRATOR, sender_name=npc_profile.get("npc_id"), text=npc_response_text)
        )
        
        # Run your background auto-summary pruning worker before committing the save
        session = await self.enforce_context_history_pruning(session)
        await session.save()

        # 5. Output a clean, beautiful Dialogue Embed block to the Discord channel
        title_label = npc_profile.get('alias') if npc_profile.get('alias') else npc_profile.get('npc_id').replace('_',' ').title()
        
        embed = discord.Embed(
            title=f"🗣️ Dialogue: {title_label}",
            description=npc_response_text,
            color=discord.Color.teal() if not fired_social_trigger else discord.Color.gold()
        )
        await channel.send(embed=embed)


    @commands.Cog.listener()
    async def on_intent_status_check_execute(self, channel, session: GameSession, node: Node, query_text: str, user_id: int):
        """
        Invokes the DM-Assistant Advisor LLM to answer tactical staging queries
        and evaluate rules legality before players commit to an action.
        """
        # 1. Identify the specific active character model belonging to the user making the query
        character_id = next((c_id for c_id, c in session.party_state.active_characters.items() if c.user_id == str(user_id)), None)
        if not character_id:
            return # Silent fail if user has no registered active character in this lobby
            
        actor = session.party_state.active_characters[character_id]

        # --- STEP 2: Compile Full Game State and Render Jinja2 Advice Prompt ---
        prompt = prompt_service.render_prompt(
            "dm_assistant_advisor.jinja",
            node=node,
            session=session,
            actor=actor,
            query_text=query_text
        )

        async with channel.typing():
            # Call Gemini 3.1 Flash Lite. Since this is an out-of-character advisor help tool,
            # we keep the cost low while keeping precision high
            response = self.ai_client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,  # Lower temperature prevents rule hallucinations
                    thinking_level="low"
                )
            )
            advice_text = response.text

        # --- STEP 3: Print a Clean, Specialized Tactical Information Embed ---
        embed = discord.Embed(
            title=f"🛡️ Tactical Advice: {actor.name}",
            description=advice_text,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Staging Area | State unchanged. Type your action to commit.")
        
        await channel.send(embed=embed)

    async def enforce_context_history_pruning(self, session: GameSession) -> GameSession:
        """
        Monitors running chat arrays. When the message collection logs grow too dense, 
        it compresses old transactions down into the continuous campaign summary text.
        """
        # Boundary baseline check: Only prune if the chat history exceeds 30 dialogue turn blocks
        if len(session.narrative_memory.recent_chat_history) < 30:
            return session

        print(f"📦 Compressing chat logs for session ID {session.id} to protect context bounds...")

        # Isolate the oldest half of the chat log to summarize, keeping the recent half for active context continuity
        split_index = len(session.narrative_memory.recent_chat_history) // 2
        old_history_to_compress = session.narrative_memory.recent_chat_history[:split_index]
        fresh_history_to_retain = session.narrative_memory.recent_chat_history[split_index:]

        # --- STEP 1: Compile Context Using TemplateService ---
        # We pass the raw array directly to Jinja2, allowing the template loop to format speaker blocks
        prompt = prompt_service.render_prompt(
            "history_pruner.jinja",
            campaign_summary_so_far=session.narrative_memory.campaign_summary_so_far,
            old_history_to_compress=old_history_to_compress
        )

        # --- STEP 2: Invoke Gemini 3.1 Flash Lite for Summary Synthesis ---
        response = self.ai_client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2, # Low temperature forces factual chronological tracking
                thinking_level="low"
            )
        )

        # --- STEP 3: Update and Overwrite Master Document Fields ---
        session.narrative_memory.campaign_summary_so_far = response.text.strip()
        session.narrative_memory.recent_chat_history = fresh_history_to_retain
        
        # Recalculate raw token count metadata estimates dynamically
        session.narrative_memory.summary_token_count = len(response.text.split())
        
        print(f"✅ Chat logs successfully pruned. New Summary length: {session.narrative_memory.summary_token_count} words.")
        return session

async def setup(bot):
    await bot.add_cog(NarrativeEngineCog(bot))
