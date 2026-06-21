import uuid
from typing import List, Dict, Any
from pydantic import BaseModel
from services.gemini_client import gemini_service
from database.models import ChannelConfig, SessionDelta, CharacterRegistry, NodeMatrix

class ActionIntent(BaseModel):
    session_id: uuid.UUID
    channel_id: int
    user_id: int
    raw_text: str

class PipelineOrchestrator:
    def __init__(self):
        self.concurrency_locks: Dict[int, bool] = {}  # channel_id to lock status

    async def process_intent(self, intent: ActionIntent) -> str:
        """
        The master controller entrypoint invoked by ChatParserCog / Slash commands.
        Ensures strict synchronization, state aggregation, validation, and routing.
        """
        # 1. Enforce Channel Concurrency & Lock Management
        if self.concurrency_locks.get(intent.channel_id, False):
            return "An action is currently processing in this channel. Please wait."
        
        self.concurrency_locks[intent.channel_id] = True
        
        try:
            # 2. Step 1: Context Aggregation Layer (The Buffer Stack Assembly)
            # Retrieve the session overlay cache
            session_delta = await SessionDelta.find_one({"session_id": intent.session_id})
            player_state = session_delta.player_states.get(str(intent.user_id))
            
            # Fetch read-only immutable map data based on character location
            current_node = NodeMatrix.get_node(player_state.current_node_id)
            
            # Fetch permanent character profile truth thresholds
            character_base = await CharacterRegistry.find_one({"discord_user_id": intent.user_id})
            
            # 3. Capture Snapshot A (Absolute base-line state before execution)
            snapshot_a = session_delta.model_dump()
            
            # 4. Multi-LLM Processing Pipeline: Step 2 — Rule Adjudication Loop
            # Packages unified text context using cached rule books (PHB/DMG) via Gemini Pro
            adjudication_payload = self._assemble_llm_payload(
                intent=intent, 
                delta=session_delta, 
                node=current_node, 
                character=character_base
            )
            
            # Invoke high-tier model using structured JSON schema with extra="forbid"
            adjudication_result = await gemini_service.adjudicate_rules(
                payload=adjudication_payload, 
                use_paid=True
            )
            
            if not adjudication_result.is_legal:
                # Short circuit early if action breaks physical parameters/game rules
                return adjudication_result.reason_denied

            # 5. Step 3: Local Code Verification Handshake (Deterministic State Engine)
            # Python translates the LLM structural directives into exact atomic database modifications
            # Prevents AI from executing values math directly
            updated_delta = await self._enforce_deterministic_mutations(
                session_delta=session_delta,
                directives=adjudication_result.mutation_directives
            )
            
            # 6. Capture Snapshot B (Absolute state after mutations)
            snapshot_b = updated_delta.model_dump()
            
            # Native dictionary difference map minimizes data sent to narration model
            semantic_diff_map = self._calculate_code_diff(snapshot_a, snapshot_b)
            
            # 7. Step 4: Narrative Reconstruction & Assembly
            # Passes changes to lower-cost creative tier (Flash-Lite) for flavor generation
            cinematic_response = await gemini_service.generate_narrative(
                context_a=snapshot_a,
                diff=semantic_diff_map,
                action_logs=adjudication_result.action_results_list,
                use_paid=False
            )
            
            return cinematic_response

        finally:
            # Always release concurrency lock even if exceptions occur
            self.concurrency_locks[intent.channel_id] = False

    def _assemble_llm_payload(self, **kwargs) -> Dict[str, Any]:
        # Combines layers into single lightweight evaluation string
        pass

    async def _enforce_deterministic_mutations(self, session_delta: SessionDelta, directives: List[Dict]) -> SessionDelta:
        """
        Translates raw AI desires into precise Beanie/MongoDB $inc, $set, $push operators
        """
        for mutation in directives:
            # Example: converting "Deal 8 damage to Goblin A" into atomic updates
            # await session_delta.update({"$inc": {f"creature_states.{mutation.target}.damage_taken": mutation.value}})
            pass
        return await session_delta.get_fresh_copy()

    def _calculate_code_diff(self, snap_a: Dict, snap_b: Dict) -> Dict:
        # Fast dictionary lookup extraction logic running entirely in local native code
        return {k: snap_b[k] for k in snap_b if snap_b[k] != snap_a.get(k)}