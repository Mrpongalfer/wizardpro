# orchestrator/phases/phase_3.py (Code Generation)
import logging
import json  # Added for parsing JSON
from typing import Optional, Dict, Any, Tuple

# Corrected Relative Imports
from . import Phase
from ..core.data_types import ProjectContext, LLMOutput
from ..core import utils  # Keep utils for now, might still be useful

logger = logging.getLogger(__name__)


class Phase3(Phase):
    """Handles code generation phase, using AI for parsing code output."""

    MAX_REFINEMENT_ATTEMPTS = 3

    def __init__(self, prompt_manager, llm_factory):
        super().__init__("Phase3_CodeGeneration", prompt_manager, llm_factory)
        logger.debug("Phase 3 (Code Generation - AI Parsing) Initialized")

    def run(self, context: ProjectContext) -> ProjectContext:
        logger.info(f"--- Running Phase: {self.phase_name_key} ---")
        context.update_status("Running", current_phase=self.phase_name_key)
        # Validation (unchanged)
        if not context.architecture_document or not isinstance(
            context.architecture_document, dict
        ):
            return self._handle_error_and_halt(
                context, "Architecture document missing/invalid."
            )
        if context.architecture_document.get("parsed") == False:
            logger.warning("Arch not parsed. Code gen quality may suffer.")
        if not context.technology_stack:
            logger.warning("Tech stack missing. Code gen less specific.")

        try:
            # --- 1. Initial Code Generation Call ---
            logger.info(
                "Calling LLM for initial code generation based on architecture..."
            )
            code_gen_llm_output: Optional[LLMOutput] = self._call_llm(
                context=context, prompt_key=self.phase_name_key
            )
            if not code_gen_llm_output or code_gen_llm_output.error:
                logger.error(f"Halting phase due to initial code gen LLM call failure.")
                return context  # Error status already set

            raw_code_gen_text = code_gen_llm_output.text
            logger.info(
                "Initial code gen call successful. Now calling LLM for parsing code output..."
            )
            logger.debug(f"Raw code gen text (start): {raw_code_gen_text[:100]}...")

            # --- 2. AI Parser Sub-Injection Call ---
            parsing_llm_output: Optional[LLMOutput] = self._call_llm(
                context=context,
                prompt_key="ParseCodeFilesJSON",  # Use the code parsing prompt
                is_sub_injection=True,
                template_data={"raw_llm_output": raw_code_gen_text},
            )

            if not parsing_llm_output or parsing_llm_output.error:
                logger.error(
                    "LLM call for parsing code files failed. Storing raw code gen text."
                )
                context.generated_code["phase3_raw_output.txt"] = raw_code_gen_text
                context.code_analysis.append(
                    {"parser_status": "Failed - Parsing LLM call error"}
                )
                # Proceed, but parsing failed
                return self._update_context_and_proceed(
                    context
                )  # Mark phase complete for now

            # --- 3. Parse JSON output from the AI Parser ---
            logger.info(
                "Code parsing LLM call successful. Attempting to parse JSON response..."
            )
            parsing_response_text = parsing_llm_output.text
            parsed_files: Dict[str, str] = {}
            try:
                if parsing_response_text.strip().startswith("```json"):
                    parsing_response_text = parsing_response_text.strip()[7:-3].strip()
                parsed_data = json.loads(parsing_response_text)

                if isinstance(parsed_data, dict):
                    if parsed_data.get("error"):
                        logger.error(
                            f"Code parsing LLM reported an error: {parsed_data['error']}"
                        )
                        context.generated_code["phase3_raw_output.txt"] = (
                            raw_code_gen_text
                        )
                        context.code_analysis.append(
                            {
                                "parser_status": f'Failed - Parser Error: {parsed_data["error"]}'
                            }
                        )
                    elif parsed_data.get("parsing_warning"):
                        logger.warning(
                            f"Code parsing LLM reported: {parsed_data['parsing_warning']}"
                        )
                        placeholder_name = parsed_data.get(
                            "file_path_placeholder", "unknown_parsed_file.txt"
                        )
                        code_content = parsed_data.get(
                            "code", "# PARSING WARNING - CODE NOT EXTRACTED"
                        )
                        parsed_files[placeholder_name] = code_content
                        context.code_analysis.append(
                            {
                                "parser_status": f'Warning - {parsed_data["parsing_warning"]}',
                                "file_parsed": placeholder_name,
                            }
                        )
                        context.generated_code.update(
                            parsed_files
                        )  # Store the single parsed file
                        logger.info(
                            f"Stored 1 file with placeholder name: {placeholder_name}"
                        )
                    elif not parsed_data:  # Empty dict returned
                        logger.warning(
                            "Code parsing LLM returned empty JSON object. No files parsed."
                        )
                        context.code_analysis.append(
                            {"parser_status": "Success - No files found/parsed"}
                        )
                    else:
                        # Assume keys are file paths and values are code strings
                        parsed_files = {
                            k: v
                            for k, v in parsed_data.items()
                            if isinstance(k, str) and isinstance(v, str)
                        }
                        if parsed_files:
                            logger.info(
                                f"Successfully parsed {len(parsed_files)} code file(s) from parsing LLM."
                            )
                            context.generated_code.update(parsed_files)
                            context.code_analysis.append(
                                {
                                    "parser_status": "Success",
                                    "files_parsed": list(parsed_files.keys()),
                                }
                            )
                        else:
                            logger.warning(
                                "Code parsing LLM returned JSON object, but no valid file_path:code pairs found."
                            )
                            context.code_analysis.append(
                                {
                                    "parser_status": "Failed - No valid code pairs in JSON"
                                }
                            )
                            context.generated_code[
                                "phase3_parser_output_invalid.json"
                            ] = json.dumps(parsed_data)
                else:
                    logger.error(
                        "Code parsing LLM response was not a valid JSON object."
                    )
                    context.generated_code["phase3_parser_output_not_dict.txt"] = (
                        parsing_response_text
                    )
                    context.code_analysis.append(
                        {"parser_status": "Failed - Invalid JSON from parser"}
                    )

            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to decode JSON from code parsing LLM response: {e}"
                )
                logger.debug(f"Raw text from parsing LLM: {parsing_response_text}")
                context.generated_code["phase3_parser_output_decode_error.txt"] = (
                    parsing_response_text
                )
                context.code_analysis.append(
                    {"parser_status": "Failed - JSONDecodeError"}
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error processing code parsing LLM response: {e}",
                    exc_info=True,
                )
                context.generated_code["phase3_parser_output_unexpected_error.txt"] = (
                    parsing_response_text
                )
                context.code_analysis.append(
                    {"parser_status": f"Failed - Unexpected processing error: {e}"}
                )

            # --- 4. Iterative Refinement Loop (Placeholder Structure - Uses parsed_files now) ---
            logger.info("Entering placeholder iterative refinement loop...")
            current_attempt = 0
            # Refine files that were successfully parsed into context.generated_code this run
            files_to_refine = list(
                parsed_files.keys()
            )  # Only refine newly parsed files for now

            while current_attempt < self.MAX_REFINEMENT_ATTEMPTS and files_to_refine:
                current_attempt += 1
                logger.info(
                    f"Refinement Attempt {current_attempt}/{self.MAX_REFINEMENT_ATTEMPTS}"
                )
                file_to_refine = files_to_refine.pop(0)
                current_code = context.generated_code.get(file_to_refine)
                if not current_code:
                    logger.warning(
                        f"Skipping refinement for {file_to_refine}, code missing."
                    )
                    continue

                needs_refinement, analysis_details, suggested_sub_injection = (
                    self._analyze_code_quality(
                        file_path=file_to_refine,
                        code_content=current_code,
                        context=context,
                    )
                )

                if needs_refinement and suggested_sub_injection:
                    logger.info(
                        f"Analysis suggests {suggested_sub_injection} for '{file_to_refine}'."
                    )
                    sub_injection_data = {
                        "file_path": file_to_refine,
                        "previous_code": current_code,
                        "analysis": analysis_details,
                        "language": file_to_refine.split(".")[-1],
                    }
                    refined_llm_output: Optional[LLMOutput] = self._call_llm(
                        context=context,
                        prompt_key=suggested_sub_injection,
                        template_data=sub_injection_data,
                        is_sub_injection=True,
                    )
                    if refined_llm_output and not refined_llm_output.error:
                        refined_code = (
                            refined_llm_output.text
                        )  # Assuming output is just the refined code block
                        if refined_code and len(refined_code) > 10:
                            logger.info(
                                f"Sub-injection '{suggested_sub_injection}' successful. Updating code."
                            )
                            context.generated_code[file_to_refine] = refined_code
                        else:
                            logger.warning(
                                f"Sub-injection '{suggested_sub_injection}' for '{file_to_refine}' empty/short. Skipping."
                            )
                    else:
                        logger.error(
                            f"Sub-injection '{suggested_sub_injection}' failed for '{file_to_refine}'. Skipping."
                        )
                elif not needs_refinement:
                    logger.info(f"Analysis: '{file_to_refine}' OK (placeholder).")
                else:
                    logger.warning(
                        f"Refinement needed for '{file_to_refine}', but no sub-injection suggested."
                    )
                if not files_to_refine:
                    logger.info(
                        "Finished processing identified files for this attempt."
                    )

            if current_attempt == self.MAX_REFINEMENT_ATTEMPTS and files_to_refine:
                logger.warning(
                    f"Max refinement attempts reached with files still pending: {files_to_refine}"
                )

            # --- End Phase 3 Logic ---
            logger.info(
                f"Code generation & AI parsing attempt complete for {self.phase_name_key}."
            )
            return self._update_context_and_proceed(context)

        except Exception as e:
            logger.critical(
                f"An unexpected critical error occurred in {self.phase_name_key} run method: {e}",
                exc_info=True,
            )
            return self._handle_error_and_halt(
                context, f"Unexpected critical error", str(e)
            )

    def _analyze_code_quality(
        self, file_path: str, code_content: str, context: "ProjectContext"
    ) -> Tuple[bool, str, Optional[str]]:
        # (Placeholder implementation unchanged)
        logger.debug(f"Placeholder analysis for file: {file_path}")
        attempt_number = sum(
            1
            for log in context.llm_call_history
            if log.get("input_prompt", "").startswith(f"**Sub-Task")
            and file_path in log.get("input_prompt", "")
        )
        if file_path.endswith(".py") and attempt_number < 1:
            logger.warning(f"Placeholder: Suggesting 'RefactorCode' for {file_path}")
            analysis_details = "Placeholder: Suggest basic refactor."
            suggested_sub_injection = "RefactorCode"
            return True, analysis_details, suggested_sub_injection
        else:
            analysis_details = "Placeholder: Analysis passed."
            return False, analysis_details, None
