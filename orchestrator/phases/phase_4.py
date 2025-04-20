# orchestrator/phases/phase_4.py (Testing & Debugging)
import logging
import json  # Import json for parsing
from typing import Optional, Dict, List, Any  # Added List

# Corrected Relative Imports
from . import Phase
from ..core.data_types import ProjectContext, LLMOutput
from ..core import utils  # Keep utils for now

logger = logging.getLogger(__name__)


class Phase4(Phase):
    """
    Handles the testing and debugging phase using AI parsing for results.
    (Note: Iterative debugging loop is still placeholder).
    """

    MAX_DEBUG_ATTEMPTS = 3

    def __init__(self, prompt_manager, llm_factory):
        super().__init__("Phase4_Testing", prompt_manager, llm_factory)
        logger.debug("Phase 4 (Testing - AI Parsing) Initialized")

    def run(self, context: ProjectContext) -> ProjectContext:
        logger.info(f"--- Running Phase: {self.phase_name_key} ---")
        context.update_status("Running", current_phase=self.phase_name_key)

        # 1. Validate context inputs
        if not context.generated_code:
            return self._handle_error_and_halt(
                context, "Generated code missing for testing."
            )
        if context.status == "Error":  # Check status from previous phase
            logger.error(
                "Cannot run Phase 4 because project context is in Error state."
            )
            return context

        try:
            # --- 2. Initial LLM Call (Testing/Analysis) ---
            logger.info("Calling LLM for initial testing/debugging analysis...")
            testing_llm_output: Optional[LLMOutput] = self._call_llm(
                context=context, prompt_key=self.phase_name_key  # Main Phase 4 prompt
            )

            if not testing_llm_output or testing_llm_output.error:
                logger.error(f"Halting phase due to initial testing LLM call failure.")
                return context

            raw_testing_text = testing_llm_output.text
            logger.info(
                "Initial testing call successful. Now calling LLM for parsing test results..."
            )
            logger.debug(f"Raw testing text (start): {raw_testing_text[:100]}...")

            # --- 3. AI Parser Sub-Injection Call ---
            parsing_llm_output: Optional[LLMOutput] = self._call_llm(
                context=context,
                prompt_key="ParseTestResultsJSON",  # Use the test result parsing prompt
                is_sub_injection=True,
                template_data={"raw_llm_output": raw_testing_text},
            )

            # Initialize/clear relevant context fields before attempting parse
            context.test_results = []
            context.debugging_info = []
            # Keep existing context.unit_tests? Or expect parser to populate? Let's keep for now.
            # Don't clear context.generated_code unless parser provides full replacement

            if not parsing_llm_output or parsing_llm_output.error:
                logger.error(
                    "LLM call for parsing test results failed. Storing raw testing text."
                )
                context.debugging_info.append(
                    f"Raw Phase 4 Output (Parsing Failed): {raw_testing_text}"
                )
                context.test_results.append(
                    {
                        "name": "parsing_failed",
                        "result": "Unknown",
                        "reason": "Parsing LLM call error",
                    }
                )
                # Proceed, but parsing failed
            else:
                # --- 4. Parse JSON output from the AI Parser ---
                logger.info(
                    "Test result parsing LLM call successful. Parsing JSON response..."
                )
                parsing_response_text = parsing_llm_output.text
                parsed_successfully = False
                try:
                    if parsing_response_text.strip().startswith("```json"):
                        parsing_response_text = parsing_response_text.strip()[
                            7:-3
                        ].strip()
                    elif parsing_response_text.strip().startswith("```"):
                        parsing_response_text = parsing_response_text.strip()[
                            3:-3
                        ].strip()

                    parsed_data = json.loads(parsing_response_text)

                    if isinstance(parsed_data, dict):
                        if parsed_data.get("error"):
                            logger.error(
                                f"Test parsing LLM reported error: {parsed_data['error']}"
                            )
                            context.debugging_info.append(
                                f"Raw Phase 4 Output (Parser Error): {raw_testing_text}"
                            )
                            context.test_results.append(
                                {
                                    "name": "parsing_failed",
                                    "result": "Unknown",
                                    "reason": f'Parser Error: {parsed_data["error"]}',
                                }
                            )
                        else:
                            logger.info(
                                "Successfully parsed JSON test/debug info from parsing LLM."
                            )
                            # Update context fields safely using .get()
                            context.test_results.extend(
                                parsed_data.get("test_results", [])
                            )  # Append results
                            context.debugging_info.extend(
                                parsed_data.get("bugs_found", [])
                            )  # Append bugs/info
                            context.debugging_info.extend(
                                parsed_data.get("suggested_fixes", [])
                            )  # Append suggestions

                            gen_tests = parsed_data.get("generated_tests")
                            if isinstance(gen_tests, dict):
                                context.unit_tests.update(gen_tests)

                            corrected_code = parsed_data.get("corrected_code")
                            if isinstance(corrected_code, dict):
                                logger.info(
                                    f"Applying {len(corrected_code)} corrected code snippets from parser."
                                )
                                context.generated_code.update(
                                    corrected_code
                                )  # Overwrite with fixes
                            logger.debug(
                                f"Updated context. Test Summary: {parsed_data.get('test_results_summary', 'N/A')}"
                            )
                            parsed_successfully = True
                    else:
                        logger.error(
                            "Test parsing LLM response was not valid JSON object."
                        )
                        context.debugging_info.append(
                            f"Raw Phase 4 Output (Invalid JSON from parser):\n{parsing_response_text}"
                        )
                        context.test_results.append(
                            {
                                "name": "parsing_failed",
                                "result": "Unknown",
                                "reason": "Invalid JSON from parser",
                            }
                        )

                except json.JSONDecodeError as e:
                    logger.error(f"Failed JSON decode for test parsing: {e}")
                    logger.debug(f"Raw text from parsing LLM: {parsing_response_text}")
                    context.debugging_info.append(
                        f"Raw Phase 4 Output (JSONDecodeError):\n{parsing_response_text}"
                    )
                    context.test_results.append(
                        {
                            "name": "parsing_failed",
                            "result": "Unknown",
                            "reason": "JSONDecodeError",
                        }
                    )
                except Exception as e:
                    logger.error(
                        f"Unexpected error processing test parsing response: {e}",
                        exc_info=True,
                    )
                    context.debugging_info.append(
                        f"Raw Phase 4 Output (Processing Error):\n{parsing_response_text}"
                    )
                    context.test_results.append(
                        {
                            "name": "parsing_failed",
                            "result": "Unknown",
                            "reason": f"Processing error: {e}",
                        }
                    )

            # --- 5. Iterative Debugging Loop (Placeholder) ---
            logger.warning(
                "Iterative testing/debugging loop not implemented in Phase 4."
            )
            # Future: Loop based on parsed context.test_results / context.debugging_info

            # --- End Phase 4 Logic ---
            logger.info(f"Initial testing/debugging and AI parsing attempt complete.")
            return self._update_context_and_proceed(context)

        except Exception as e:
            logger.critical(
                f"An unexpected critical error occurred in {self.phase_name_key} run method: {e}",
                exc_info=True,
            )
            return self._handle_error_and_halt(
                context, f"Unexpected critical error", str(e)
            )
