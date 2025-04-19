# orchestrator/phases/phase_2.py (System Architecture)
import logging
import json # Import json for parsing
from typing import Optional, Dict, List, Any

# Corrected Relative Imports
from . import Phase
from ..core.data_types import ProjectContext, LLMOutput
from ..core import utils # Keep utils for now

logger = logging.getLogger(__name__)

class Phase2(Phase):
    """
    Handles the system design and architecture phase using AI parsing.
    """
    def __init__(self, prompt_manager, llm_factory):
        super().__init__('Phase2_Architecture', prompt_manager, llm_factory)
        logger.debug("Phase 2 (Architecture - AI Parsing) Initialized")

    def run(self, context: ProjectContext) -> ProjectContext:
        logger.info(f"--- Running Phase: {self.phase_name_key} ---")
        context.update_status("Running", current_phase=self.phase_name_key)

        # 1. Validate context inputs
        if not context.refined_requirements or not isinstance(context.refined_requirements, dict):
             return self._handle_error_and_halt(context, "Refined requirements missing or invalid for Phase 2.")
        if context.refined_requirements.get('parsing_status', '').startswith('Failed'):
             logger.warning("Phase 1 requirements parsing failed/skipped. Architecture quality may be impacted.")
        elif context.refined_requirements.get('parsing_status') == 'NeedsUserInput':
             return self._handle_error_and_halt(context, "Cannot proceed to Phase 2, Phase 1 requires user input.")


        try:
            # --- Core Phase 2 Logic ---
            # 2. Initial LLM Call (Architecture Generation)
            logger.info("Calling LLM for system architecture design...")
            architecture_llm_output: Optional[LLMOutput] = self._call_llm(
                context=context,
                prompt_key=self.phase_name_key
            )

            if not architecture_llm_output or architecture_llm_output.error:
                 logger.error(f"Halting phase due to initial architecture LLM call failure.")
                 return context

            raw_architecture_text = architecture_llm_output.text
            logger.info("Initial architecture call successful. Now calling LLM for parsing...")
            logger.debug(f"Raw architecture text (start): {raw_architecture_text[:100]}...")


            # 3. Second LLM Call (Parsing Sub-injection)
            parsing_llm_output: Optional[LLMOutput] = self._call_llm(
                context=context,
                prompt_key="ParseArchitectureJSON", # Use the new parsing prompt key
                is_sub_injection=True,
                template_data={"raw_llm_output": raw_architecture_text} # Pass raw text
            )

            if not parsing_llm_output or parsing_llm_output.error:
                logger.error("LLM call for parsing architecture failed. Storing raw architecture text.")
                context.architecture_document = {'raw_output': raw_architecture_text, 'parsing_status': 'Failed - Parsing LLM call error'}
                context.technology_stack = ['Parsing LLM failed']
                return self._update_context_and_proceed(context) # Proceed with raw data? Or halt? Let's proceed.


            # 4. Parse the JSON output from the *second* LLM call
            logger.info("Parsing LLM call successful. Attempting to parse JSON response...")
            parsing_response_text = parsing_llm_output.text
            parsed_successfully = False
            try:
                if parsing_response_text.strip().startswith("```json"):
                    parsing_response_text = parsing_response_text.strip()[7:-3].strip()

                parsed_data = json.loads(parsing_response_text)

                if isinstance(parsed_data, dict):
                    if parsed_data.get("error"):
                         logger.error(f"Parsing LLM reported error: {parsed_data['error']}")
                         context.architecture_document = {'raw_output': raw_architecture_text, 'parsing_status': f'Failed - Parser Error: {parsed_data["error"]}'}
                         context.technology_stack = ['Parsing LLM reported error']
                    else:
                         # Extract expected keys
                         arch_doc = parsed_data.get("architecture_document")
                         tech_stack = parsed_data.get("technology_stack")

                         if isinstance(arch_doc, dict) and isinstance(tech_stack, list):
                              logger.info("Successfully parsed architecture JSON from parsing LLM.")
                              context.architecture_document = arch_doc
                              context.technology_stack = tech_stack
                              context.architecture_document['parsing_status'] = 'Success' # Mark success
                              parsed_successfully = True
                         else:
                              logger.error("Parsing LLM JSON response missing required keys ('architecture_document' object, 'technology_stack' list) or keys have wrong type.")
                              context.architecture_document = {'raw_output': raw_architecture_text, 'parsing_status': 'Failed - Invalid JSON structure from parser', 'parser_response': parsed_data}
                              context.technology_stack = ['Invalid structure from parser']
                else:
                    logger.error("Parsing LLM response was not a valid JSON object.")
                    context.architecture_document = {'raw_output': raw_architecture_text, 'parsing_status': 'Failed - Invalid JSON from parser', 'parser_response': parsing_response_text}
                    context.technology_stack = ['Invalid JSON from parser']

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON from parsing LLM response: {e}")
                logger.debug(f"Raw text from parsing LLM: {parsing_response_text}")
                context.architecture_document = {'raw_output': raw_architecture_text, 'parsing_status': 'Failed - JSONDecodeError', 'parser_response': parsing_response_text}
                context.technology_stack = ['JSONDecodeError from parser']
            except Exception as e:
                 logger.error(f"Unexpected error processing parsing LLM response: {e}", exc_info=True)
                 context.architecture_document = {'raw_output': raw_architecture_text, 'parsing_status': f'Failed - Unexpected processing error: {e}', 'parser_response': parsing_response_text}
                 context.technology_stack = ['Processing error from parser']

            # Log summary
            arch_summary = str(context.architecture_document)[:200]; logger.debug(f"Stored arch (summary): {arch_summary}..."); logger.debug(f"Stored tech stack: {context.technology_stack}")

            # --- End Phase 2 Logic ---

            # 5. Update context status and return
            logger.info(f"Architecture generation & AI parsing attempt complete.")
            return self._update_context_and_proceed(context)

        except Exception as e:
             logger.critical(f"An unexpected critical error occurred in {self.phase_name_key} run method: {e}", exc_info=True)
             return self._handle_error_and_halt(context, f"Unexpected critical error", str(e))

