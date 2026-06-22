import json
from typing import Type, Any, Dict, Union
from google import genai
from google.genai import types
from pydantic import BaseModel
from config.settings import settings

class GeminiService:
    def __init__(self):
        """
        Central management layer for the Google Gemini API.
        Initializes split clients to separate Free vs Paid tier projects seamlessly.
        """
        # Project A: Free Tier Client (Chat, Narrative Parsers, DDB Ingestion)
        self.free_client = genai.Client(api_key=settings.gemini_api_key)
        
        # Project B: Paid Tier Client (Rule Adjudicator / Context Cache lookups)
        # Fallback to free key if you haven't split them out in settings yet
        paid_key = getattr(settings, "paid_gemini_api_key", settings.gemini_api_key)
        self.paid_client = genai.Client(api_key=paid_key)

    def get_client(self, use_paid: bool = False) -> genai.Client:
        """Helper to safely route requests to the correct Google Cloud wallet project."""
        return self.paid_client if use_paid else self.free_client

    async def generate_structured_output(
        self,
        model: str,
        contents: Union[str, list],
        response_schema: Type[BaseModel],
        use_paid: bool = False,
        config_overrides: Dict[str, Any] = None
    ) -> BaseModel:
        """
        Consumes unstructured layouts or tokens, enforces strict structural contracts,
        bypasses client-side validation blockers, and returns a fully initialized Pydantic DTO.
        """
        client = self.get_client(use_paid=use_paid)
        
        # 1. Bypass client-side validation errors by generating the JSON schema explicitly
        # and passing it directly to the API backend through response_json_schema.
        # This completely resolves the "additionalProperties is only supported in Enterprise" crash.
        base_config = {
            "response_mime_type": "application/json",
            "response_json_schema": response_schema.model_json_schema(),
            "temperature": 0.1,  # Enforce structural determinism
        }
        
        if config_overrides:
            base_config.update(config_overrides)
            
        # Convert dictionary settings cleanly into the SDK's required config structure
        api_config = types.GenerateContentConfig(**base_config)

        # 2. Execute call via the raw under-the-hood engine loops
        # If your environment requires async/await loop calls, verify if client uses:
        # response = await client.aio.models.generate_content(...)
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=api_config
        )

        # 🔍 EXTRACT AND LOG TOKEN TELEMETRY HERE
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata
            print(f"📊 [API Telemetry] Model: {model}")
            print(f"   ↳ Input  Tokens (Prompt): {usage.prompt_token_count}")
            print(f"   ↳ Output Tokens (Generated): {usage.candidates_token_count} ") #/ {base_config['max_output_tokens']}
            print(f"   ↳ Total  Tokens Context:  {usage.total_token_count}")

        if not response.text:
            raise ValueError("The Gemini API engine returned an empty data response.")

        # 3. Handle Native Deserialization on the way out.
        # Unpack the raw JSON string directly into the requested Pydantic DTO type contract.
        parsed_json = json.loads(response.text)
        return response_schema(**parsed_json)

# Instantiate as a global singleton service instance
gemini_service = GeminiService()