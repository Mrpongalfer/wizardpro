# orchestrator/main.py
import logging
import os
import importlib
import argparse
from typing import List, Type, Optional

from .core.data_types import ProjectContext
from .core.prompts import PromptManager
from .core.llm_tools import LLMFactory
from .core import utils
from .phases import Phase

logger = logging.getLogger(__name__)

class Orchestrator:
    """Manages the WizardPro workflow."""
    # (__init__, _load_phase_classes, _save_context, _load_context unchanged)
    def __init__(self, config_module):
        logger.info("Initializing Orchestrator...")
        self.config = config_module
        self.context_save_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'project_contexts'))
        os.makedirs(self.context_save_dir, exist_ok=True)
        logger.info(f"Project context save/load directory: {self.context_save_dir}")
        prompt_dir = getattr(self.config, 'PROMPT_DIR_PATH', None)
        if not prompt_dir or not os.path.isdir(prompt_dir): raise ValueError(f"Invalid prompt directory path: {prompt_dir}")
        self.prompt_manager = PromptManager(prompt_dir=prompt_dir)
        self.llm_factory = LLMFactory()
        self.phase_sequence: List[Type[Phase]] = self._load_phase_classes()
        if not self.phase_sequence: raise ImportError("Failed to load phase classes.")
        logger.info(f"Loaded {len(self.phase_sequence)} phases: {[p.__name__ for p in self.phase_sequence]}")
        logger.info("Orchestrator initialized successfully.")

    def _load_phase_classes(self) -> List[Type[Phase]]:
        phase_classes = []; phases_package_path = os.path.join(os.path.dirname(__file__), 'phases'); logger.debug(f"Loading phases from: {phases_package_path}")
        try:
             if not os.path.isdir(phases_package_path): logger.error(f"Phases directory not found: {phases_package_path}"); return []
             expected_phase_files = sorted([f for f in os.listdir(phases_package_path) if f.startswith("phase_") and f.endswith(".py")])
        except FileNotFoundError: logger.error(f"Phases directory listing failed: {phases_package_path}"); return []
        for filename in expected_phase_files:
            module_name = filename[:-3]; module_import_path = f".phases.{module_name}"
            try:
                module = importlib.import_module(module_import_path, package='orchestrator')
                class_name_found = None
                for name, obj in module.__dict__.items():
                     if isinstance(obj, type) and issubclass(obj, Phase) and obj is not Phase and obj.__module__ == module.__name__:
                          phase_classes.append(obj); class_name_found = name; logger.debug(f"Loaded phase class: {name} from {module_import_path}"); break
                if not class_name_found: logger.warning(f"No Phase subclass found in {module_import_path}")
            except Exception as e: logger.error(f"Error loading phase module {module_import_path}: {e}", exc_info=True)
        try: phase_classes.sort(key=lambda cls: int(''.join(filter(str.isdigit, cls.__name__))))
        except: logger.warning("Could not sort phase classes numerically.")
        return phase_classes

    def _save_context(self, context: ProjectContext):
        if not context or not context.project_id: logger.error("Invalid context/project_id for saving."); return
        logger.debug(f"Saving context for project ID: {context.project_id}")
        if not utils.save_project_context(context, self.context_save_dir, project_id_in_path=True): logger.error(f"Failed to save context for {context.project_id}")

    def _load_context(self, project_id: str) -> Optional[ProjectContext]:
        logger.debug(f"Attempting load for project ID: {project_id}")
        context = utils.load_project_context(self.context_save_dir, project_id_in_path=True, project_id=project_id)
        if context: logger.info(f"Loaded context for project ID: {project_id}")
        return context

    def run_workflow(self, initial_user_request: Optional[str] = None, project_id: Optional[str] = None, resume: bool = False, selected_wrappers: Optional[List[str]] = None) -> ProjectContext:
        context: Optional[ProjectContext] = None; loaded_context = False
        # --- Load or Initialize Context (Unchanged) ---
        if resume:
            if not project_id: raise ValueError("Project ID required for resume.")
            context = self._load_context(project_id)
            if not context: raise FileNotFoundError(f"Context file not found for resume ID {project_id}.")
            loaded_context = True; logger.info(f"Resuming workflow {context.project_id} from phase: {context.current_phase}")
            if selected_wrappers: logger.warning("Resuming: --wrapper args ignored, using loaded context wrappers.")
        if not context:
            if not initial_user_request: raise ValueError("Initial request required if not resuming.")
            context = ProjectContext(initial_request=initial_user_request)
            if project_id: context.project_id = project_id
            context.selected_wrappers = selected_wrappers if selected_wrappers else []
            logger.info(f"Initialized new Project Context. ID: {context.project_id}, Wrappers: {context.selected_wrappers}")
            self._save_context(context) # Initial save

        # --- Determine start phase index (Unchanged) ---
        current_phase_index = 0
        if loaded_context:
            try:
                 phase_keys = [p(self.prompt_manager, self.llm_factory).phase_name_key for p in self.phase_sequence]
                 current_phase_index = phase_keys.index(context.current_phase)
                 if context.status == "PhaseComplete": current_phase_index += 1 # Start next phase after a completed one
            except ValueError: logger.error(f"Loaded unknown phase '{context.current_phase}'. Starting from 0."); current_phase_index = 0

        if current_phase_index >= len(self.phase_sequence) and context.status != "Error":
             # If already past the last phase index AND not errored, consider it complete.
             logger.info(f"Workflow for project {context.project_id} already completed. Status: {context.status}")
             context.update_status("Complete") # Ensure status is 'Complete' if resuming after Phase 5 success
             return context

        # --- Corrected Main Workflow Loop ---
        logger.info(f"Starting workflow execution from phase index {current_phase_index}.")
        while current_phase_index < len(self.phase_sequence):
            phase_class = self.phase_sequence[current_phase_index]; phase_instance = None
            try:
                phase_instance = phase_class(self.prompt_manager, self.llm_factory); phase_name_key = phase_instance.phase_name_key
                logger.info(f"--- Executing Phase: {phase_name_key} ---")
                context = phase_instance.run(context) # Run phase logic
                self._save_context(context) # Save state *after* phase attempt

                # Check status set by the phase.run() method
                if context.status == "Error":
                    logger.error(f"Workflow halted: Error occurred in phase {phase_name_key}")
                    break # Stop workflow on error
                elif context.status == "NeedsInput":
                    logger.info(f"Workflow paused: Needs input in phase {phase_name_key}")
                    break # Stop workflow for input
                elif context.status == "PhaseComplete":
                    logger.info(f"Phase '{phase_name_key}' completed successfully.")
                    current_phase_index += 1 # Increment index to move to next phase
                    # Loop will naturally terminate if this was the last phase
                else:
                    # If status is something else (e.g., still "Running", or unexpected value)
                    logger.warning(f"Phase '{phase_name_key}' ended with unexpected status: '{context.status}'. Treating as error and halting.")
                    context.update_status("Error", current_phase=phase_name_key) # Explicitly set error status
                    self._save_context(context) # Save the error state
                    break

            except Exception as e:
                 # Catch critical errors during phase instantiation or unexpected exceptions from run()
                 phase_name_for_log = phase_instance.phase_name_key if phase_instance else f"Index {current_phase_index}"
                 logger.critical(f"Critical orchestrator error during phase '{phase_name_for_log}': {e}", exc_info=True)
                 if context: context.add_log_entry(phase_name_for_log, "CRITICAL", "Orchestrator exception", str(e)); context.update_status("Error", phase_name_for_log); self._save_context(context)
                 break # Halt workflow on critical errors

        # --- End Workflow Loop ---

        # Set final overall status if loop completed naturally
        if current_phase_index >= len(self.phase_sequence) and context.status != "Error" and context.status != "NeedsInput":
             context.update_status("Complete")
             logger.info(f"All phases completed. Final project status set to: {context.status}")
             self._save_context(context) # Save final complete state


        final_status = context.status if context else "Unknown"; final_project_id = context.project_id if context else project_id or "Unknown"
        logger.info(f"--- Workflow Execution Finished for Project ID: {final_project_id} ---"); logger.info(f"Final Status: {final_status}")
        if context: logger.info(f"Ended at Phase: {context.current_phase}")
        return context


if __name__ == "__main__":
    # (Arg parsing unchanged)
    parser = argparse.ArgumentParser(description="WizardPro Orchestrator")
    parser.add_argument("initial_request", nargs='?', help="Initial request (required if not resuming).")
    parser.add_argument("-p", "--project_id", help="Project ID to use or resume.")
    parser.add_argument("-r", "--resume", action="store_true", help="Resume workflow for --project_id.")
    parser.add_argument("-w", "--wrapper", action="append", help="Activate wrapper by name (repeatable).")
    args = parser.parse_args()
    if args.resume and not args.project_id: parser.error("--project_id required with --resume.")
    if not args.resume and not args.initial_request: parser.error("initial_request required if not resuming.")

    logger = logging.getLogger(__name__)
    logger.info("Orchestrator script started directly via -m.")
    logger.debug(f"Args: {args}")

    final_context = None
    exit_code = 0
    try:
        from . import config as cfg # Relative import
        if not hasattr(cfg, 'PROMPT_DIR_PATH') or not os.path.isdir(cfg.PROMPT_DIR_PATH): logger.critical(f"Prompt directory path invalid: {getattr(cfg, 'PROMPT_DIR_PATH', 'Not Found')}."); exit(1)
        orchestrator = Orchestrator(config_module=cfg)
        final_context = orchestrator.run_workflow(initial_user_request=args.initial_request, project_id=args.project_id, resume=args.resume, selected_wrappers=args.wrapper)
        # Check final status for exit code MORE accurately
        if final_context and final_context.status != "Complete":
             exit_code = 1 # Any status other than Complete is considered non-zero exit

    # (Error handling unchanged)
    except ImportError as e: logger.critical(f"Import Error: {e}", exc_info=True); exit_code = 1
    except FileNotFoundError as e: logger.critical(f"Failed to resume: {e}"); exit_code = 1
    except ValueError as e: logger.critical(f"Config/Arg Error: {e}"); exit_code = 1
    except Exception as e: logger.critical(f"Unexpected error: {e}", exc_info=True); exit_code = 1

    # (Final summary unchanged)
    if final_context:
        logger.info("--- Workflow Execution Summary ---"); logger.info(f"Project ID: {final_context.project_id}"); logger.info(f"Final Status: {final_context.status}"); logger.info(f"Final Phase: {final_context.current_phase}"); logger.info(f"Activated Wrappers: {final_context.selected_wrappers}"); logger.info(f"Generated Files Count: {len(final_context.generated_code)}"); logger.info(f"LLM Calls Made: {len(final_context.llm_call_history)}"); logger.info(f"Error Log Entries: {len(final_context.error_log)}")
        if final_context.status == "Error" or final_context.error_log: logger.warning("Workflow ended with errors.")
    else: logger.error("Workflow did not complete. No final context.")
    logger.info(f"Orchestrator script finished with exit code {exit_code}.")
    exit(exit_code)

