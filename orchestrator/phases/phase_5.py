# orchestrator/phases/phase_5.py (Deployment & Optimization)
import logging
from typing import Optional, Dict, Any

# Corrected Relative Imports
from . import Phase
from ..core.data_types import ProjectContext, LLMOutput
from ..core import utils

logger = logging.getLogger(__name__)

class Phase5(Phase):
    """Handles deployment prep, optimization, documentation (basic implementation)."""
    def __init__(self, prompt_manager, llm_factory):
        super().__init__('Phase5_Deployment', prompt_manager, llm_factory)
        logger.debug("Phase 5 (Deployment - Basic) Initialized")

    def run(self, context: ProjectContext) -> ProjectContext:
        logger.info(f"--- Running Phase: {self.phase_name_key} ---"); context.update_status("Running", current_phase=self.phase_name_key)
        if not context.generated_code: return self._handle_error_and_halt(context, "Generated code missing for Phase 5.")
        if context.status == "Error": logger.error("Cannot run Phase 5 due to previous errors."); return context
        try:
            logger.info("Calling LLM for deployment configs and documentation...")
            llm_output: Optional[LLMOutput] = self._call_llm(context=context, prompt_key=self.phase_name_key)
            if not llm_output or llm_output.error: return self._handle_error_and_halt(context, f"LLM call failed during {self.phase_name_key}")

            logger.info("LLM call successful. Parsing deployment/doc info...")
            llm_response_text = llm_output.text
            # --- Attempt Parsing (Logic unchanged) ---
            parsed_output = utils.parse_yaml_from_llm(llm_response_text)
            if parsed_output and isinstance(parsed_output, dict):
                 logger.info("Parsed structured YAML from Phase 5 response.")
                 context.deployment_config.update(parsed_output.get('deployment_config', {})); context.documentation.update(parsed_output.get('documentation', {}))
            else: logger.warning("Failed parse YAML from Phase 5. Storing raw.")
            parsed_files = utils.parse_code_blocks_with_filepaths(llm_response_text)
            if parsed_files:
                 logger.info(f"Parsed {len(parsed_files)} file blocks from Phase 5 response.")
                 for file_path, content in parsed_files.items():
                      if file_path.lower() in ['dockerfile', 'docker-compose.yml', '.gitlab-ci.yml', 'github_workflow.yaml']: context.deployment_config[file_path] = content
                      elif file_path.lower().endswith(('.md', '.txt')): context.documentation[file_path] = content
                      else: context.deployment_config[f"generated_file_{file_path}"] = content
            if not context.deployment_config: context.deployment_config['placeholder'] = 'Deployment config not parsed.'; logger.warning("No deployment config parsed.")
            if not context.documentation: context.documentation['placeholder'] = 'Documentation not parsed.'; logger.warning("No documentation parsed.")
            # --- End Parsing ---

            logger.info(f"Deployment/Optimization/Documentation phase complete.")
            # --- CORRECTED: Use standard helper to finish phase ---
            return self._update_context_and_proceed(context)
            # --- Do NOT set status to "Complete" here, let orchestrator handle final state ---

        except Exception as e:
            logger.critical(f"Unexpected error in {self.phase_name_key}: {e}", exc_info=True)
            # Ensure context status reflects error if this phase crashes
            context.update_status("Error", current_phase=self.phase_name_key) # Set error before handling
            return self._handle_error_and_halt(context, f"Unexpected critical error", str(e))

