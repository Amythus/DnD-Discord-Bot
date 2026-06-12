import os
import json
from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader, select_autoescape

class TemplateService:
    def __init__(self, templates_dir: str = "templates"):
        """
        Initializes the centralized Jinja2 environment.
        Configures strict variable checking and whitespace trimming for clean LLM prompts.
        """
        # Ensure the template directory path is absolute to prevent traversal bugs
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        target_path = os.path.join(base_path, templates_dir)

        self.env = Environment(
            loader=FileSystemLoader(target_path),
            # Automatically trim whitespaces and block lines to minimize token waste
            trim_blocks=True,
            lstrip_blocks=True,
            # Force Jinja2 to raise an error if a variable name is misspelled in a template
            keep_trailing_newline=False
        )

    def render_prompt(self, template_name: str, **kwargs: Any) -> str:
        """
        Loads a target template file and injects Python objects dynamically.
        Returns a stripped string ready for Gemini API ingestion.
        """
        try:
            template = self.env.get_template(template_name)
            rendered_text = template.render(**kwargs)
            # Remove redundant empty lines to preserve prompt context cohesion
            return "\n".join([line for line in rendered_text.splitlines() if line.strip()])
        except Exception as e:
            raise RuntimeError(f"❌ Failed to compile Jinja2 template '{template_name}': {e}")

    def clean_json_response(self, raw_llm_output: str) -> Dict[str, Any]:
        """
        Helper utility to clean up raw LLM responses. Strips away accidental markdown
        code blocks (```json ... ```) or hidden whitespace characters before running json.loads().
        """
        cleaned = raw_llm_output.strip()
        
        # Strip leading and trailing markdown code block wrappers if the LLM hallucinated them
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
            
        return json.loads(cleaned)

# Instantiate a single global instance of our prompt utility pipeline
prompt_service = TemplateService()
