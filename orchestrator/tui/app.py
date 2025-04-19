# orchestrator/tui/app.py
import logging
from pathlib import Path
import sys
from typing import Optional, List, Dict, Any
import datetime # Needed for user_feedback timestamp

# Textual Imports
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Vertical
from textual.widgets import Header, Footer, Input, Button, Static, Log, TextArea
from textual.reactive import var
from textual.logging import TextualHandler

# --- Attempt to import WizardPro components ---
try:
    from ..main import Orchestrator
    from .. import config as cfg
    from ..core.data_types import ProjectContext
    logger = logging.getLogger(__name__)
except ImportError:
    # Fallback logic (unchanged)
    logger = logging.getLogger("tui_app"); logger.warning("Running TUI potentially outside package context..."); script_dir = Path(__file__).resolve().parent; parent_dir = script_dir.parent; root_dir = parent_dir.parent
    if str(parent_dir) not in sys.path: sys.path.insert(0, str(parent_dir))
    if str(root_dir) not in sys.path: sys.path.insert(0, str(root_dir))
    try: from orchestrator.main import Orchestrator; import orchestrator.config as cfg; from orchestrator.core.data_types import ProjectContext
    except ImportError as e_inner: logger.critical(f"Failed import: {e_inner}"); raise RuntimeError("Could not import WizardPro modules.") from e_inner

class WizardProTUI(App):
    """A Textual UI for the WizardPro Orchestrator."""

    TITLE = "WizardPro Orchestrator"; SUB_TITLE = "AI-Powered Software Generation"; CSS_PATH = "app.css"; BINDINGS = [("d", "toggle_dark", "Toggle Dark Mode"),("ctrl+c", "quit", "Quit"),]
    workflow_status = var("Idle")
    current_context: Optional[ProjectContext] = var(None)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        with Container(id="app-grid"):
            # Left Pane Contents (inside a Vertical for structure)
            with Vertical(id="left-column"):
                # --- Use Static for Pane Title ---
                yield Static("--- Controls ---", classes="pane-title")
                with VerticalScroll(id="left-pane"): # Make the content scrollable
                    with Vertical(id="request-area"):
                        yield Static("Initial Request:", classes="label"); yield Input(placeholder="Describe the application...", id="initial-request");
                        yield Static("Project ID (Optional):", classes="label", id="project-id-label"); yield Input(placeholder="e.g., my-web-app-01", id="project-id");
                        yield Static("Wrappers:", classes="label", id="wrappers-label"); yield Static("[Wrapper selection TBD]", id="wrapper-selection-placeholder");
                        yield Button("Start Workflow", id="start-button", variant="primary");
                    with Vertical(id="interaction-area", classes="hidden"):
                         # --- Use Static for Pane Title ---
                         yield Static("--- User Input Required ---", classes="pane-title")
                         yield Static("Assistant Questions:", classes="label", id="interaction-label"); yield Static("...", id="interaction-questions", classes="message-display");
                         yield Static("Your Response:", classes="label"); yield TextArea(language="markdown", id="user-response-area", theme="dracula");
                         yield Button("Submit Response", id="submit-response-button", variant="success");
                # Status Line at bottom of left column
                yield Static(id="status-line", classes="status")

            # Right Pane Contents (inside a Vertical)
            with Vertical(id="right-column"):
                 # --- Use Static for Pane Title ---
                 yield Static("--- Logs / Output ---", classes="pane-title")
                 with VerticalScroll(id="right-pane"): # Make the content scrollable
                      # yield Static("Logs & Output:", classes="label") # Label redundant now? Keep or remove.
                      yield Log(highlight=True, id="log-output", auto_scroll=True)
        yield Footer()

    # --- Methods on_mount, watch_workflow_status, update_status_line, show_interaction_area, prompt_for_user_input ---
    # --- on_button_pressed, run_orchestrator_worker, __main__ block ---
    # --- (All unchanged from previous version with correct syntax) ---
    def on_mount(self) -> None:
        log_widget = self.query_one(Log); textual_handler = TextualHandler(log_widget); formatter = logging.Formatter("%(asctime)s|%(levelname)s|%(name)s:%(lineno)d| %(message)s", datefmt='%H:%M:%S'); textual_handler.setFormatter(formatter); root_logger = logging.getLogger(); handlers_to_remove = [h for h in root_logger.handlers if not isinstance(h, (logging.FileHandler, TextualHandler))];
        for handler in handlers_to_remove: logger.debug(f"Removing handler: {handler}"); root_logger.removeHandler(handler)
        if not any(isinstance(h, TextualHandler) for h in root_logger.handlers): logger.debug("Adding TextualHandler."); root_logger.addHandler(textual_handler)
        log_level = getattr(cfg, 'LOG_LEVEL', logging.INFO); root_logger.setLevel(log_level); logger.info(f"Logging configured. Level: {logging.getLevelName(root_logger.level)}."); self.query_one("#initial-request", Input).focus(); self.update_status_line("Idle. Enter request and press Start.")

    def watch_workflow_status(self, status: str) -> None: self.update_status_line(status)

    def update_status_line(self, status: str):
         try: self.query_one("#status-line", Static).update(f"Status: {status}")
         except Exception: logger.error("Failed status update.", exc_info=True)

    def show_interaction_area(self, show: bool = True):
        try:
            self.query_one("#interaction-area").set_class(not show, "hidden")
            self.query_one("#request-area").set_class(show, "hidden")
            if show: self.query_one("#user-response-area", TextArea).focus()
        except Exception as e: logger.error(f"Error toggling interaction area visibility: {e}", exc_info=True)

    def prompt_for_user_input(self, context: ProjectContext):
        logging.info("Workflow requires user input. Updating UI.")
        self.current_context = context
        try:
            question_widget = self.query_one("#interaction-questions", Static)
            questions = context.refined_requirements.get('outstanding_questions', [])
            if isinstance(questions, list) and questions: formatted_questions = "\n".join([f"- {q}" for q in questions]); question_widget.update(formatted_questions)
            else: question_widget.update("[Assistant needs input, but no specific questions extracted/found.]")
            self.show_interaction_area(True); self.update_status_line("Paused - Waiting for User Response")
        except Exception as e: logger.error(f"Error displaying user input prompt: {e}", exc_info=True); self.update_status_line("Error displaying prompt!")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-button":
            initial_request = self.query_one("#initial-request", Input).value; project_id = self.query_one("#project-id", Input).value or None
            if not initial_request: self.workflow_status = "Error: Initial request empty."; logging.error("Start empty request."); return
            selected_wrappers = [] # TODO: Get from UI
            event.button.disabled = True; self.show_interaction_area(False); self.query_one(Log).clear(); self.workflow_status = "Starting Workflow..."
            logging.info(f"Starting workflow - ID: {project_id or '(New)'}, Request: {initial_request[:50]}..., Wrappers: {selected_wrappers}")
            self.run_worker(self.run_orchestrator_worker(initial_request, project_id, False, selected_wrappers), name=f"Workflow_{project_id or 'New'}", group="orchestrator_workflows", exclusive=True, thread=True)
        elif event.button.id == "submit-response-button":
             response_text = self.query_one("#user-response-area", TextArea).text
             if not response_text: self.update_status_line("Status: Please enter a response."); return
             if not self.current_context: logging.error("Submit response: no current context."); self.update_status_line("Error: No context to resume."); return
             logging.info(f"User response submitted: {response_text[:100]}...")
             self.current_context.latest_user_response = response_text
             self.current_context.user_feedback.append({"timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "response_to_phase": self.current_context.current_phase, "response_text": response_text})
             self.current_context.status = "Resuming"; event.button.disabled = True; self.query_one("#user-response-area", TextArea).text = ""; self.show_interaction_area(False); self.update_status_line("Status: Resuming Workflow...")
             logging.info(f"Resuming workflow for Project ID: {self.current_context.project_id}")
             self.run_worker(self.run_orchestrator_worker(initial_request=None, project_id=self.current_context.project_id, resume=True, selected_wrappers=self.current_context.selected_wrappers), name=f"Workflow_{self.current_context.project_id}_Resume", group="orchestrator_workflows", exclusive=True, thread=True)

    async def run_orchestrator_worker(self, initial_request: Optional[str], project_id: Optional[str], resume: bool, selected_wrappers: Optional[List[str]]):
        final_context: Optional[ProjectContext] = None
        try:
            self.call_from_thread(setattr, self, "workflow_status", "Instantiating Orchestrator..."); orchestrator = Orchestrator(config_module=cfg)
            self.call_from_thread(setattr, self, "workflow_status", f"{'Resuming' if resume else 'Running'} Workflow...")
            final_context = orchestrator.run_workflow(initial_user_request=initial_request, project_id=project_id, resume=resume, selected_wrappers=selected_wrappers)
            if final_context.status == "NeedsUserInput": self.call_from_thread(self.prompt_for_user_input, final_context)
            else: self.call_from_thread(setattr, self, "workflow_status", f"Workflow Finished: {final_context.status}")
        except Exception as e: error_msg = f"Workflow Error: {type(e).__name__}: {e}"; logging.critical(f"Error in worker: {e}", exc_info=True); self.call_from_thread(setattr, self, "workflow_status", error_msg)
        finally:
            def enable_buttons():
                try:
                    if not final_context or final_context.status != "NeedsUserInput": self.query_one("#start-button", Button).disabled = False
                    self.query_one("#submit-response-button", Button).disabled = True # Keep submit disabled until needed
                except Exception: logger.error("Failed re-enable/disable buttons.")
            self.call_from_thread(enable_buttons)

if __name__ == "__main__":
    # Add imports needed ONLY for this block if run directly
    import datetime
    app = WizardProTUI()
    app.run()

