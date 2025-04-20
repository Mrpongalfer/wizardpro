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
        """
        Analyzes the quality of a given code snippet using an LLM sub-injection.

        Args:
            file_path: The path of the file being analyzed.
            code_content: The actual code content to analyze.
            context: The current ProjectContext (needed for _call_llm and context vars).

        Returns:
            Tuple: (needs_refinement: bool, analysis_details: str, suggested_sub_injection: Optional[str])
                   Returns (False, "Analysis OK", None) on success if quality is good.
                   Returns (True, "Details", "ActionKey") if refinement needed.
                   Returns (True, "Error Details", "RefactorCode") if analysis itself failed (fallback action).
        """
        logger.info(f"Analyzing code quality via LLM for: {file_path}")

        # Prepare data for the analysis prompt template
        template_data = {
            "file_path": file_path,
            "language": file_path.split(".")[-1]
            or "unknown",  # Basic language detection
            "code_to_analyze": code_content,
            # The prompt template 'AnalyzeCodeQuality' accesses the full context via 'ctx.'
            # No need to pass requirements/arch explicitly here if prompt uses ctx.
        }

        # Call the LLM using the analysis sub-injection prompt
        analysis_llm_output: Optional[LLMOutput] = self._call_llm(
            context=context,
            prompt_key="AnalyzeCodeQuality",  # Key from sub_injection_prompts.yaml
            is_sub_injection=True,
            template_data=template_data,
            # Consider using a more powerful model for analysis?
            # model_identifier="gpt-4" # Or another preferred model if available
        )

        # Default return values in case of failure during analysis call/parsing
        needs_refinement = True  # Default to needing refinement if analysis fails
        analysis_details = (
            "Code analysis sub-injection failed or produced invalid output."
        )
        suggested_action = "RefactorCode"  # Default fallback action

        if not analysis_llm_output or analysis_llm_output.error:
            logger.error(
                f"Code quality analysis LLM call failed for {file_path}: {analysis_llm_output.error if analysis_llm_output else 'Unknown reason'}"
            )
            analysis_details = f"Analysis LLM call failed: {analysis_llm_output.error if analysis_llm_output else 'Unknown'}"
            # Return default failure state
            return needs_refinement, analysis_details, suggested_action

        # Parse the JSON response from the analysis LLM
        analysis_response_text = analysis_llm_output.text
        try:
            logger.debug(f"Attempting to parse analysis JSON for {file_path}")
            # Basic cleanup for potential markdown wrappers
            if analysis_response_text.strip().startswith("```json"):
                analysis_response_text = analysis_response_text.strip()[7:-3].strip()
            elif analysis_response_text.strip().startswith("```"):
                analysis_response_text = analysis_response_text.strip()[3:-3].strip()

            analysis_result = json.loads(analysis_response_text)

            if isinstance(analysis_result, dict):
                # Safely get values from the parsed JSON
                quality_ok = analysis_result.get(
                    "quality_ok", False
                )  # Default to False if key missing
                details = analysis_result.get(
                    "analysis_details", "No details provided by analysis."
                )
                action = analysis_result.get(
                    "suggested_action"
                )  # Will be None if missing or explicitly null

                # Validate types
                if not isinstance(quality_ok, bool):
                    logger.warning(
                        f"Analysis JSON 'quality_ok' is not boolean ({type(quality_ok)}) for {file_path}. Assuming refinement needed."
                    )
                    quality_ok = False
                    details += (
                        " (Warning: Invalid quality_ok type in analysis response)"
                    )
                if not isinstance(details, str):
                    logger.warning(
                        f"Analysis JSON 'analysis_details' is not string ({type(details)}) for {file_path}."
                    )
                    details = "[Invalid analysis details type]"
                if action is not None and not isinstance(action, str):
                    logger.warning(
                        f"Analysis JSON 'suggested_action' is not string or null ({type(action)}) for {file_path}. Setting action to None."
                    )
                    action = None  # Treat invalid action as None

                # Determine return values based on validated parsed data
                needs_refinement = not quality_ok
                analysis_details = details
                suggested_action = (
                    action if needs_refinement else None
                )  # Only return action if refinement is needed

                logger.info(
                    f"Code analysis result for {file_path}: OK={quality_ok}, Action={suggested_action or 'None'}, Details={analysis_details}"
                )
                # Return the parsed results
                return needs_refinement, analysis_details, suggested_action

            else:  # Parsed data is not a dictionary
                logger.error(
                    f"Code analysis LLM response was not a valid JSON object for {file_path}."
                )
                analysis_details = "Analysis response was not JSON object."
                # Return default failure state
                return needs_refinement, analysis_details, suggested_action

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to decode JSON analysis response for {file_path}: {e}"
            )
            logger.debug(f"Raw text from analysis LLM: {analysis_response_text}")
            analysis_details = f"Analysis response JSON decode failed: {e}"
            # Return default failure state
            return needs_refinement, analysis_details, suggested_action
        except Exception as e:
            logger.error(
                f"Unexpected error processing analysis response for {file_path}: {e}",
                exc_info=True,
            )
            analysis_details = f"Unexpected error processing analysis: {e}"
            # Return default failure state
            return needs_refinement, analysis_details, suggested_action

    # --- END of _analyze_code_quality method ---
