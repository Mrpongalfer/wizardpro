# orchestrator/phases/__init__.py
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Dict, Any

# Use TYPE_CHECKING to avoid circular imports during runtime
if TYPE_CHECKING:
    from ..core.data_types import ProjectContext, LLMOutput
    from ..core.llm_tools import LLMFactory
    from ..core.prompts import PromptManager

logger = logging.getLogger(__name__)

class Phase(ABC):
    """Abstract Base Class for all development phases in the WizardPro workflow."""

    def __init__(self, phase_name_key: str, prompt_manager: 'PromptManager', llm_factory: 'LLMFactory'):
        self.phase_name_key = phase_name_key
        self.prompt_manager = prompt_manager
        self.llm_factory = llm_factory
        logger.info(f"Initialized Phase: {self.phase_name_key}")

    @abstractmethod
    def run(self, context: 'ProjectContext') -> 'ProjectContext':
        """Executes the primary logic for this specific phase."""
        pass

    def _call_llm(self, context: 'ProjectContext', prompt_key: str, model_identifier: Optional[str] = None,
                  template_data: Optional[Dict[str, Any]] = None, is_sub_injection: bool = False) -> Optional['LLMOutput']:
        """Helper method to assemble prompt, call LLM, and handle basic logging/history."""
        phase_for_logging = context.current_phase
        logger.debug(f"Preparing LLM call for prompt key '{prompt_key}' within phase '{phase_for_logging}'")

        sub_key = prompt_key if is_sub_injection else None
        main_key = self.phase_name_key if not is_sub_injection else context.current_phase

        try:
            assembled_prompt = self.prompt_manager.assemble_prompt(
                phase_name=main_key, context=context, sub_injection_key=sub_key, sub_injection_data=template_data
            )
            if assembled_prompt.startswith("Error:") or assembled_prompt.startswith("--- ERROR"):
                 logger.error(f"Failed to assemble prompt: {assembled_prompt}")
                 context.add_log_entry(phase_for_logging, "ERROR", f"Prompt assembly failed for key '{prompt_key}'", assembled_prompt)
                 context.update_status("Error")
                 return None

            # --- Determine the target LLM model ---
            target_model = model_identifier # Use specified model if provided
            if not target_model:
                # TODO: Fetch default model from config more robustly
                # Example: target_model = getattr(config, 'DEFAULT_MODEL_IDENTIFIER', None)
                if not target_model:
                    # --- TEMPORARY FALLBACK MODEL CHANGED ---
                    target_model = "gpt-3.5-turbo" # Using 3.5-turbo as a more accessible default
                    logger.warning(f"No specific model requested or configured, using default fallback: {target_model}")

            llm_tool = self.llm_factory.get_tool(target_model)

            from ..core.data_types import LLMInput # Local import
            llm_input_data = LLMInput(prompt=assembled_prompt, model_identifier=target_model)
            # TODO: Set temperature, max_tokens etc. from config/phase logic

            llm_output = llm_tool.execute(llm_input_data)
            context.add_llm_call(llm_output) # Add result to history regardless of error

            if llm_output.error:
                logger.error(f"LLM call failed for {target_model}: {llm_output.error}")
                context.add_log_entry(phase_for_logging, "ERROR", f"LLM call failed for model '{target_model}' on prompt key '{prompt_key}'", llm_output.error)
                # Let the calling run method decide if this halts the phase
                return llm_output # Return object containing error

            logger.info(f"LLM call using prompt key '{prompt_key}' successful.")
            return llm_output

        except Exception as e:
            logger.critical(f"Unexpected critical error during LLM call setup/execution in phase '{phase_for_logging}': {e}", exc_info=True)
            context.add_log_entry(phase_for_logging, "CRITICAL", f"Unexpected error in _call_llm for prompt key '{prompt_key}'", str(e))
            context.update_status("Error")
            return None


    def _update_context_and_proceed(self, context: 'ProjectContext') -> 'ProjectContext':
        """Helper method to update context status for successful phase completion."""
        context.update_status("PhaseComplete", current_phase=self.phase_name_key)
        logger.info(f"Phase '{self.phase_name_key}' marked as complete.")
        return context

    def _handle_error_and_halt(self, context: 'ProjectContext', error_message: str, details: Optional[str] = None) -> 'ProjectContext':
         """Helper method to log an error, update status, and indicate phase failure."""
         logger.error(f"Phase '{self.phase_name_key}' encountered an error: {error_message}" + (f" Details: {details}" if details else ""))
         context.add_log_entry(self.phase_name_key, "ERROR", error_message, details)
         context.update_status("Error", current_phase=self.phase_name_key)
         return context

