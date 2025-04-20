# orchestrator/phases/phase_5.py (Deployment & Optimization)
import logging
import json  # Import json for parsing
from typing import Optional, Dict, List, Any, Union  # Added Union, List

# Corrected Relative Imports
from . import Phase
from ..core.data_types import ProjectContext, LLMOutput
from ..core import utils

logger = logging.getLogger(__name__)


class Phase5(Phase):
    """
    Handles deployment prep, optimization, documentation using AI parsing.
    """

    def __init__(self, prompt_manager, llm_factory):
        super().__init__("Phase5_Deployment", prompt_manager, llm_factory)
        logger.debug("Phase 5 (Deployment - AI Parsing) Initialized")

    def run(self, context: ProjectContext) -> ProjectContext:
        logger.info(f"--- Running Phase: {self.phase_name_key} ---")
        context.update_status("Running", current_phase=self.phase_name_key)

        # 1. Validation
        if not context.generated_code:
            return self._handle_error_and_halt(
                context, "Generated code missing for Phase 5."
            )
        if context.status == "Error":
            logger.error("Cannot run Phase 5 due to previous errors.")
            return context

        try:
            # --- 2. Initial LLM Call (Deployment/Doc Generation) ---
            logger.info(
                "Calling LLM for deployment configurations and documentation..."
            )
            deploy_llm_output: Optional[LLMOutput] = self._call_llm(
                context=context, prompt_key=self.phase_name_key
            )

            if not deploy_llm_output or deploy_llm_output.error:
                return self._handle_error_and_halt(
                    context, f"LLM call failed during {self.phase_name_key}"
                )
            raw_deploy_text = deploy_llm_output.text
            logger.info(
                "Initial deployment call successful. Now calling LLM for parsing artifacts..."
            )
            logger.debug(f"Raw deployment text (start): {raw_deploy_text[:100]}...")

            # --- 3. AI Parser Sub-Injection Call ---
            parsing_llm_output: Optional[LLMOutput] = self._call_llm(
                context=context,
                prompt_key="ParseDeploymentArtifactsJSON",  # Use the artifact parsing prompt
                is_sub_injection=True,
                template_data={"raw_llm_output": raw_deploy_text},
            )

            # Initialize/clear relevant context fields
            context.deployment_config = {}
            context.documentation = {}

            if not parsing_llm_output or parsing_llm_output.error:
                logger.error(
                    "LLM call for parsing deployment artifacts failed. Storing raw text."
                )
                context.documentation["Phase5_RawOutput.md"] = raw_deploy_text
                context.deployment_config["parsing_status"] = (
                    "Failed - Parsing LLM call error"
                )
            else:
                # --- 4. Parse JSON output from the AI Parser ---
                logger.info(
                    "Artifact parsing LLM call successful. Attempting to parse JSON response..."
                )
                parsing_response_text = parsing_llm_output.text
                parsed_successfully = False
                try:
                    # Basic cleanup for potential markdown wrappers
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
                                f"Artifact parsing LLM reported error: {parsed_data['error']}"
                            )
                            context.documentation["Phase5_RawOutput.md"] = (
                                raw_deploy_text
                            )
                            context.deployment_config["parsing_status"] = (
                                f'Failed - Parser Error: {parsed_data["error"]}'
                            )
                        else:
                            logger.info(
                                "Successfully parsed JSON artifacts from parsing LLM."
                            )
                            parsing_status = "Success"  # Default status
                            if parsed_data.get("parsing_warning"):
                                logger.warning(
                                    f"Artifact parsing LLM reported: {parsed_data['parsing_warning']}"
                                )
                                parsing_status = (
                                    f'Warning - {parsed_data["parsing_warning"]}'
                                )

                            # Iterate through parsed data and sort into docs vs config
                            docs = {}
                            configs = {}
                            for file_path, content in parsed_data.items():
                                # Skip special keys potentially added by the parser prompt
                                if file_path in [
                                    "error",
                                    "parsing_warning",
                                    "parsing_status",
                                ]:
                                    continue
                                if isinstance(file_path, str) and isinstance(
                                    content, str
                                ):
                                    # Basic sorting logic (can be refined)
                                    if file_path.lower().endswith(
                                        (".md", ".txt", ".rst")
                                    ):
                                        docs[file_path] = content
                                    # Check for common config files/extensions
                                    elif file_path.lower() in [
                                        "dockerfile",
                                        "docker-compose.yml",
                                        ".gitlab-ci.yml",
                                    ] or file_path.endswith(
                                        (
                                            ".yaml",
                                            ".yml",
                                            ".conf",
                                            ".ini",
                                            ".cfg",
                                            ".json",
                                            ".xml",
                                            ".sh",
                                        )
                                    ):
                                        if (
                                            ".github/workflows/" in file_path.lower()
                                            or "jenkinsfile" in file_path.lower()
                                        ):
                                            configs[file_path] = content
                                        # Avoid classifying docs as configs if possible
                                        elif not file_path.lower().endswith(
                                            (".md", ".txt", ".rst")
                                        ):
                                            configs[file_path] = content
                                        else:
                                            docs[file_path] = (
                                                content  # Treat as doc if ambiguous extension
                                            )
                                    else:  # Store others as deployment config for now
                                        logger.info(
                                            f"Storing unknown file type '{file_path}' in deployment_config."
                                        )
                                        configs[file_path] = content
                                else:
                                    logger.warning(
                                        f"Skipping invalid item in parsed artifacts JSON: Key='{file_path}', Type={type(content)}"
                                    )

                            context.documentation = docs  # Overwrite with parsed docs
                            context.deployment_config = (
                                configs  # Overwrite with parsed configs
                            )
                            context.deployment_config["parsing_status"] = (
                                parsing_status  # Store final parsing status
                            )
                            logger.info(
                                f"Stored {len(docs)} documentation files and {len(configs)} deployment config files."
                            )
                            parsed_successfully = True
                    else:  # Parsed data is not a dictionary
                        logger.error(
                            "Artifact parsing LLM response was not a valid JSON object."
                        )
                        context.documentation["Phase5_RawOutput_InvalidJSON.txt"] = (
                            parsing_response_text
                        )
                        context.deployment_config["parsing_status"] = (
                            "Failed - Invalid JSON from parser"
                        )

                except json.JSONDecodeError as e:
                    logger.error(
                        f"Failed to decode JSON from artifact parsing LLM response: {e}"
                    )
                    logger.debug(f"Raw text from parsing LLM: {parsing_response_text}")
                    context.documentation["Phase5_RawOutput_JSONDecodeError.txt"] = (
                        parsing_response_text
                    )
                    context.deployment_config["parsing_status"] = (
                        "Failed - JSONDecodeError"
                    )
                except Exception as e:
                    logger.error(
                        f"Unexpected error processing artifact parsing LLM response: {e}",
                        exc_info=True,
                    )
                    context.documentation["Phase5_RawOutput_Exception.txt"] = (
                        parsing_response_text
                    )
                    context.deployment_config["parsing_status"] = (
                        f"Failed - Unexpected processing error: {e}"
                    )

            # Ensure some placeholders exist if maps are still empty
            if not context.deployment_config:
                context.deployment_config["placeholder"] = (
                    "Deployment config not parsed/found."
                )
            if not context.documentation:
                context.documentation["placeholder"] = "Documentation not parsed/found."

            # Log summary
            logger.debug(f"Stored docs: {list(context.documentation.keys())}")
            logger.debug(f"Stored configs: {list(context.deployment_config.keys())}")

            # --- End Phase 5 AI Parsing Logic ---
            # --- End Phase 5 Logic ---

            # 5. Final status update
            logger.info(f"Deployment/Optimization/Documentation phase complete.")
            # Mark the entire project workflow as Complete (error or not, this is the end)
            context.update_status("Complete", current_phase=self.phase_name_key)
            logger.info(
                f"WizardPro project '{context.project_id}' finished workflow. Final status: {context.status}"
            )
            return context  # Return final context

        except Exception as e:
            logger.critical(
                f"An unexpected critical error occurred in {self.phase_name_key} run method: {e}",
                exc_info=True,
            )
            context.update_status("Error", current_phase=self.phase_name_key)
            # Use base class helper to log error before returning
            return self._handle_error_and_halt(
                context, f"Unexpected critical error in Phase 5", str(e)
            )
