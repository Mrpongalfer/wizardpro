# orchestrator/phases/phase_3.py (Code Generation)
import logging
from typing import Optional, Dict, Any, Tuple

# Corrected Relative Imports
from . import Phase
from ..core.data_types import ProjectContext, LLMOutput
from ..core import utils

logger = logging.getLogger(__name__)

class Phase3(Phase):
    """Handles code generation with iterative refinement structure."""
    MAX_REFINEMENT_ATTEMPTS = 3
    def __init__(self, prompt_manager, llm_factory):
        super().__init__('Phase3_CodeGeneration', prompt_manager, llm_factory)
        logger.debug("Phase 3 (Code Generation - Iterative Structure) Initialized")

    def run(self, context: ProjectContext) -> ProjectContext:
        logger.info(f"--- Running Phase: {self.phase_name_key} ---"); context.update_status("Running", current_phase=self.phase_name_key)
        # Validation (unchanged)
        if not context.architecture_document or not isinstance(context.architecture_document, dict): return self._handle_error_and_halt(context, "Architecture document missing/invalid.")
        if context.architecture_document.get('parsed') == False: logger.warning("Arch not parsed. Code gen quality may suffer.")
        if not context.technology_stack: logger.warning("Tech stack missing. Code gen less specific.")

        try:
            # --- Initial Code Generation Call ---
            logger.info("Calling LLM for initial code generation based on architecture...")
            llm_output: Optional[LLMOutput] = self._call_llm(context=context, prompt_key=self.phase_name_key)
            if not llm_output or llm_output.error: logger.error(f"Halting due to initial LLM call failure."); return context

            logger.info("Initial LLM call successful. Parsing generated code...")
            llm_response_text = llm_output.text

            # --- Improved Parsing Logic ---
            parsed_files: Dict[str, str] = utils.parse_code_blocks_with_filepaths(llm_response_text)

            if not parsed_files:
                logger.warning("Could not parse code blocks with file path markers. Trying simple block parsing...")
                simple_parsed_blocks = utils.parse_code_blocks(llm_response_text)
                if len(simple_parsed_blocks) == 1:
                    # If only one block, assign a default filename based on language or context
                    lang = list(simple_parsed_blocks.keys())[0]
                    # Try to guess filename from architecture/request if possible (complex)
                    # For now, use a placeholder name
                    placeholder_name = f"generated_code.{lang if lang != 'unknown' else 'txt'}"
                    parsed_files[placeholder_name] = simple_parsed_blocks[lang]
                    logger.info(f"Found one simple code block, assigned placeholder name: {placeholder_name}")
                elif len(simple_parsed_blocks) > 1:
                    logger.warning(f"Found {len(simple_parsed_blocks)} simple code blocks without paths. Storing raw output.")
                    context.generated_code['phase3_raw_output_multiple_blocks.txt'] = llm_response_text
                    # Proceed, but refinement loop might struggle
                else:
                    # No blocks found at all
                    logger.error("Could not parse any code blocks from LLM response.")
                    context.generated_code['phase3_raw_output_no_blocks.txt'] = llm_response_text
                    # Decide whether to halt or proceed cautiously
                    return self._handle_error_and_halt(context, "Failed to parse any code blocks from LLM.")

            # Store successfully parsed files (either with paths or the single placeholder)
            if parsed_files:
                 context.generated_code.update(parsed_files)
                 logger.info(f"Parsed and stored code for {len(parsed_files)} file(s).")
                 logger.debug(f"Files in context: {list(context.generated_code.keys())}")

            # --- Iterative Refinement Loop (Placeholder Structure - Unchanged) ---
            logger.info("Entering placeholder iterative refinement loop...")
            current_attempt = 0
            files_to_refine = list(parsed_files.keys()) # Refine files we actually parsed

            while current_attempt < self.MAX_REFINEMENT_ATTEMPTS and files_to_refine:
                current_attempt += 1; logger.info(f"Refinement Attempt {current_attempt}/{self.MAX_REFINEMENT_ATTEMPTS}")
                file_to_refine = files_to_refine.pop(0); current_code = context.generated_code.get(file_to_refine)
                if not current_code: logger.warning(f"Skipping refinement for {file_to_refine}, code missing."); continue
                needs_refinement, analysis_details, suggested_sub_injection = self._analyze_code_quality(file_path=file_to_refine, code_content=current_code, context=context)
                if needs_refinement and suggested_sub_injection:
                    logger.info(f"Analysis suggests {suggested_sub_injection} for '{file_to_refine}'.")
                    sub_injection_data = {"file_path": file_to_refine, "previous_code": current_code, "analysis": analysis_details, "language": file_to_refine.split('.')[-1]}
                    refined_llm_output: Optional[LLMOutput] = self._call_llm(context=context, prompt_key=suggested_sub_injection, template_data=sub_injection_data, is_sub_injection=True)
                    if refined_llm_output and not refined_llm_output.error:
                        refined_code = refined_llm_output.text
                        if refined_code and len(refined_code) > 10: logger.info(f"Sub-injection '{suggested_sub_injection}' successful. Updating code."); context.generated_code[file_to_refine] = refined_code
                        else: logger.warning(f"Sub-injection '{suggested_sub_injection}' for '{file_to_refine}' empty/short. Skipping.")
                    else: logger.error(f"Sub-injection '{suggested_sub_injection}' failed for '{file_to_refine}'. Skipping.")
                elif not needs_refinement: logger.info(f"Analysis: '{file_to_refine}' OK (placeholder).")
                else: logger.warning(f"Refinement needed for '{file_to_refine}', but no sub-injection suggested.")
                if not files_to_refine: logger.info("Finished processing identified files for this attempt.")
            if current_attempt == self.MAX_REFINEMENT_ATTEMPTS and files_to_refine: logger.warning(f"Max refinement attempts reached with files still pending: {files_to_refine}")
            logger.info(f"Code gen/refinement attempts complete.")
            return self._update_context_and_proceed(context)

        except Exception as e: logger.critical(f"Unexpected error in {self.phase_name_key}: {e}", exc_info=True); return self._handle_error_and_halt(context, f"Unexpected critical error", str(e))

    def _analyze_code_quality(self, file_path: str, code_content: str, context: 'ProjectContext') -> Tuple[bool, str, Optional[str]]:
        # (Placeholder implementation unchanged)
        logger.debug(f"Placeholder analysis for file: {file_path}"); attempt_number = sum(1 for log in context.llm_call_history if log.get('input_prompt','').startswith(f"**Sub-Task") and file_path in log.get('input_prompt',''))
        if file_path.endswith(".py") and attempt_number < 1: logger.warning(f"Placeholder: Suggesting 'RefactorCode' for {file_path}"); analysis_details = "Placeholder: Suggest basic refactor."; suggested_sub_injection = "RefactorCode"; return True, analysis_details, suggested_sub_injection
        else: analysis_details = "Placeholder: Analysis passed."; return False, analysis_details, None

