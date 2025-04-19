# orchestrator/phases/phase_4.py (Testing & Debugging)
import logging
from typing import Optional, Dict, Any

# Corrected Relative Imports
from . import Phase
from ..core.data_types import ProjectContext, LLMOutput
from ..core import utils

logger = logging.getLogger(__name__)

class Phase4(Phase):
    """Handles the testing and debugging phase (basic implementation)."""
    MAX_DEBUG_ATTEMPTS = 3
    def __init__(self, prompt_manager, llm_factory):
        super().__init__('Phase4_Testing', prompt_manager, llm_factory)
        logger.debug("Phase 4 (Testing - Basic) Initialized")

    def run(self, context: ProjectContext) -> ProjectContext:
        # (Method implementation unchanged from Step 9)
        logger.info(f"--- Running Phase: {self.phase_name_key} ---"); context.update_status("Running", current_phase=self.phase_name_key)
        if not context.generated_code: return self._handle_error_and_halt(context, "Generated code missing for testing.")
        try:
            logger.info("Calling LLM for initial testing/debugging analysis...")
            llm_output: Optional[LLMOutput] = self._call_llm(context=context, prompt_key=self.phase_name_key)
            if not llm_output or llm_output.error: logger.error(f"Halting phase due to LLM call failure."); return context
            logger.info("LLM call successful. Parsing testing/debugging info...")
            llm_response_text = llm_output.text
            parsed_test_info = utils.parse_yaml_from_llm(llm_response_text) # Example parsing
            if parsed_test_info and isinstance(parsed_test_info, dict):
                 logger.info("Parsed structured test/debug info (attempted).")
                 context.test_results.extend(parsed_test_info.get('test_results', [])); context.debugging_info.extend(parsed_test_info.get('bugs_found', []))
                 corrected_code = parsed_test_info.get('corrected_code', {});
                 if corrected_code: logger.info(f"Found {len(corrected_code)} corrected snippets."); context.generated_code.update(corrected_code)
                 logger.debug("Updated context with parsed info.")
            else:
                 logger.warning("Failed parse structured test/debug info. Storing raw."); context.debugging_info.append(f"Raw Phase 4 Output:\n{llm_response_text}"); context.test_results.append({'name': 'parsing_failed', 'result': 'Unknown'})
            logger.warning("Iterative testing/debugging loop not implemented.")
            logger.info(f"Initial testing/debugging attempt complete.")
            return self._update_context_and_proceed(context)
        except Exception as e: logger.critical(f"Unexpected error in {self.phase_name_key}: {e}", exc_info=True); return self._handle_error_and_halt(context, f"Unexpected critical error", str(e))

