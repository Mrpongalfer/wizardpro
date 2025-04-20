# orchestrator/phases/phase_1.py (Requirements Elicitation)
import logging
import json
from typing import Optional

# Corrected Relative Imports
from . import Phase
from ..core.data_types import ProjectContext, LLMOutput

logger = logging.getLogger(__name__)


class Phase1(Phase):
    """
    Handles the initial requirements elicitation phase, including processing user responses.
    """

    def __init__(self, prompt_manager, llm_factory):
        super().__init__("Phase1_Requirements", prompt_manager, llm_factory)
        logger.debug("Phase 1 (Requirements - AI Parsing & Interaction) Initialized")

    def run(self, context: ProjectContext) -> ProjectContext:
        logger.info(f"--- Running Phase: {self.phase_name_key} ---")
        context.update_status("Running", current_phase=self.phase_name_key)

        # --- Main try block for the entire phase ---
        try:
            # --- Decide whether to run initial prompt or process user response ---
            elicitation_llm_output: Optional[LLMOutput] = None
            if context.latest_user_response:
                logger.info("User response found in context. Processing response...")
                # Prepare data for the response processing prompt
                template_data = {
                    "initial_request": context.initial_request,
                    # Pass previous requirements state for context
                    "previous_requirements": context.refined_requirements,
                    "user_response": context.latest_user_response,
                }
                # Call LLM with the response processing sub-injection prompt
                elicitation_llm_output = self._call_llm(
                    context=context,
                    prompt_key="ProcessUserResponse",  # Needs to exist in sub_injection_prompts.yaml
                    is_sub_injection=True,
                    template_data=template_data,
                )
                # Clear the response now that we've used it
                logger.debug("Clearing latest_user_response from context.")
                context.latest_user_response = None
                # Note: Orchestrator saves context after phase returns

            else:
                # Initial run for this phase
                if not context.initial_request:
                    # Use helper method from base class to handle error state and return
                    return self._handle_error_and_halt(
                        context, "Initial user request is missing."
                    )
                logger.info(
                    "No user response found. Calling LLM for initial requirements gathering..."
                )
                elicitation_llm_output = self._call_llm(
                    context=context,
                    prompt_key=self.phase_name_key,  # Use the main Phase 1 prompt key
                )

            # --- Process the output (from either initial call or response processing) ---
            if not elicitation_llm_output or elicitation_llm_output.error:
                logger.error(
                    "Halting phase due to LLM call failure (elicitation/response processing)."
                )
                # If error happened after processing user input, ensure status is Error
                context.update_status("Error", current_phase=self.phase_name_key)
                return context  # Return context in Error state

            raw_elicitation_text = elicitation_llm_output.text
            logger.info(
                "Elicitation/Response Processing call successful. Now calling LLM for parsing..."
            )
            logger.debug(f"Raw text to parse (start): {raw_elicitation_text[:100]}...")

            # --- Call AI Parser Sub-Injection ---
            parsing_llm_output: Optional[LLMOutput] = self._call_llm(
                context=context,
                prompt_key="ParseRequirementsJSON",
                is_sub_injection=True,
                template_data={"raw_llm_output": raw_elicitation_text},
            )

            if not parsing_llm_output or parsing_llm_output.error:
                logger.error(
                    "LLM call for parsing requirements failed. Storing raw elicitation text."
                )
                context.refined_requirements = {
                    "raw_output": raw_elicitation_text,
                    "parsing_status": "Failed - Parsing LLM call error",
                    "parsing_error": (
                        parsing_llm_output.error
                        if parsing_llm_output
                        else "Unknown parsing call error"
                    ),
                }
                return self._update_context_and_proceed(
                    context
                )  # Proceed, but parsing failed

            # --- Parse the JSON output from the AI Parser ---
            logger.info(
                "Parsing LLM call successful. Attempting to parse JSON response..."
            )
            parsing_response_text = parsing_llm_output.text
            needs_input_flag = False
            try:
                if parsing_response_text.strip().startswith("```json"):
                    parsing_response_text = parsing_response_text.strip()[7:-3].strip()
                parsed_requirements = json.loads(parsing_response_text)

                if isinstance(parsed_requirements, dict):
                    logger.info(
                        "Successfully parsed JSON requirements from parsing LLM."
                    )
                    context.refined_requirements = (
                        parsed_requirements  # Store structured data
                    )
                    context.refined_requirements["parsing_status"] = (
                        parsed_requirements.get("status", "Parsed")
                    )

                    if (
                        context.refined_requirements["parsing_status"]
                        == "NeedsUserInput"
                    ):
                        logger.info("Parsing LLM indicated user input is required.")
                        needs_input_flag = True  # Set flag
                    elif context.refined_requirements.get("error"):
                        logger.error(
                            f"Parsing LLM reported error: {context.refined_requirements['error']}"
                        )
                        context.refined_requirements["parsing_status"] = (
                            "Failed - Parser reported error"
                        )
                else:
                    logger.error("Parsing LLM response was not a valid JSON object.")
                    context.refined_requirements = {
                        "raw_output": raw_elicitation_text,
                        "parsing_status": "Failed - Invalid JSON from parser",
                        "parser_response": parsing_response_text,
                    }

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON from parsing LLM response: {e}")
                logger.debug(f"Raw text from parsing LLM: {parsing_response_text}")
                context.refined_requirements = {
                    "raw_output": raw_elicitation_text,
                    "parsing_status": "Failed - JSONDecodeError",
                    "parser_response": parsing_response_text,
                }
            except Exception as e:
                logger.error(
                    f"Unexpected error processing parsing LLM response: {e}",
                    exc_info=True,
                )
                context.refined_requirements = {
                    "raw_output": raw_elicitation_text,
                    "parsing_status": f"Failed - Unexpected processing error: {e}",
                    "parser_response": parsing_response_text,
                }

            # --- Finalize Phase Status ---
            req_summary = str(context.refined_requirements)[:200]
            logger.debug(f"Stored requirements (summary): {req_summary}...")
            logger.info("Requirements gathering & AI parsing attempt complete.")

            if needs_input_flag:
                context.update_status(
                    "NeedsUserInput", current_phase=self.phase_name_key
                )
                return context  # Return context with NeedsUserInput status
            else:
                # If no input needed and no critical error occurred during parsing, mark phase complete
                return self._update_context_and_proceed(context)

        # --- CORRECTED INDENTATION FOR THIS EXCEPT BLOCK ---
        except Exception as e:
            logger.critical(
                f"An unexpected critical error occurred in {self.phase_name_key} run method: {e}",
                exc_info=True,
            )
            context.latest_user_response = (
                None  # Clear response if we errored during processing
            )
            return self._handle_error_and_halt(
                context, f"Unexpected critical error in {self.phase_name_key}", str(e)
            )
        # --- End of run method ---
