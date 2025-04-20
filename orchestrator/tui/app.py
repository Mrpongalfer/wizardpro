# orchestrator/tui/app.py
import logging
from pathlib import Path
import sys
from typing import Optional, List  # Keep Dict, Any for type hints if needed
import datetime

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
    # Fallback logic
    logger = logging.getLogger("tui_app")
    logger.warning(
        "Running TUI potentially outside package context. Attempting path modification."
    )
    script_dir = Path(__file__).resolve().parent
    parent_dir = script_dir.parent
    root_dir = parent_dir.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    try:
        from orchestrator.main import Orchestrator
        import orchestrator.config as cfg
        from orchestrator.core.data_types import ProjectContext
    except ImportError as e_inner:
        logger.critical(f"Failed import: {e_inner}")
        raise RuntimeError("Could not import required WizardPro modules.") from e_inner


class WizardProTUI(App):
    """A Textual UI for the WizardPro Orchestrator."""

    TITLE = "WizardPro Orchestrator"
    SUB_TITLE = "AI-Powered Software Generation"
    CSS_PATH = "app.css"
    BINDINGS = [
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("ctrl+c", "quit", "Quit"),
    ]

    workflow_status = var("Idle")
    current_context: Optional[ProjectContext] = var(None)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        with Container(id="app-grid"):
            with Vertical(id="left-column"):
                yield Static("--- Controls ---", classes="pane-title")
                with VerticalScroll(id="left-pane"):
                    with Container(id="request-area"):
                        yield Static("Initial Request:", classes="label")
                        yield Input(
                            placeholder="Describe the application...",
                            id="initial-request",
                        )
                        yield Static(
                            "Project ID (Optional):",
                            classes="label",
                            id="project-id-label",
                        )
                        yield Input(placeholder="e.g., my-web-app-01", id="project-id")
                        yield Static("Wrappers:", classes="label", id="wrappers-label")
                        yield Static(
                            "[Wrapper selection TBD]",
                            id="wrapper-selection-placeholder",
                        )
                        yield Button(
                            "Start Workflow",
                            id="start-button",
                            variant="primary",
                        )
                    with Container(id="interaction-area", classes="hidden"):
                        yield Static(
                            "Assistant Questions:",
                            classes="label",
                            id="interaction-label",
                        )
                        yield Static(
                            "...",
                            id="interaction-questions",
                            classes="message-display",
                        )
                        yield Static("Your Response:", classes="label")
                        yield TextArea(
                            language="markdown",
                            id="user-response-area",
                            theme="dracula",
                        )
                        yield Button(
                            "Submit Response",
                            id="submit-response-button",
                            variant="success",
                            disabled=True,
                        )
                yield Static(id="status-line", classes="status")
            with Vertical(id="right-column"):
                yield Static("--- Logs / Output ---", classes="pane-title")
                with VerticalScroll(id="right-pane"):
                    yield Log(highlight=True, id="log-output", auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        """Configure logging and focus input on app mount."""
        log_widget = self.query_one(Log)
        textual_handler = TextualHandler(log_widget)
        formatter = logging.Formatter(
            "%(asctime)s|%(levelname)s|%(name)s:%(lineno)d| %(message)s",
            datefmt="%H:%M:%S",
        )
        textual_handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        handlers_to_remove = [
            h
            for h in root_logger.handlers
            if not isinstance(h, (logging.FileHandler, TextualHandler))
        ]
        for handler in handlers_to_remove:
            logger.debug(f"Removing handler: {handler}")
            root_logger.removeHandler(handler)
        if not any(isinstance(h, TextualHandler) for h in root_logger.handlers):
            logger.debug("Adding TextualHandler.")
            root_logger.addHandler(textual_handler)
        log_level = getattr(cfg, "LOG_LEVEL", logging.INFO)
        root_logger.setLevel(log_level)
        logger.info(
            f"Logging configured. Level: {logging.getLevelName(root_logger.level)}."
        )
        self.query_one("#initial-request", Input).focus()
        self.update_status_line("Idle. Enter request and press Start.")

    def watch_workflow_status(self, status: str) -> None:
        """Update status line when reactive variable changes."""
        self.update_status_line(status)

    def update_status_line(self, status: str):
        """Helper to update the status line widget."""
        try:
            status_line = self.query_one("#status-line", Static)
            status_line.update(f"Status: {status}")
        except Exception:
            logger.error("Failed status update.", exc_info=True)

    def show_interaction_area(self, show: bool = True):
        """Show or hide the user interaction widgets and manage button/focus states."""
        try:
            interaction_area = self.query_one("#interaction-area")
            request_area = self.query_one("#request-area")
            submit_button = self.query_one("#submit-response-button", Button)
            start_button = self.query_one("#start-button", Button)
            text_area = self.query_one("#user-response-area", TextArea)

            interaction_area.set_class(not show, "hidden")
            request_area.set_class(show, "hidden")

            if show:
                # When showing interaction: enable submit, disable start, focus text area
                submit_button.disabled = False
                start_button.disabled = True
                text_area.disabled = False
                self.set_timer(0.1, text_area.focus)  # Focus after slight delay
            else:
                # When hiding interaction: disable submit
                submit_button.disabled = True
                text_area.disabled = True  # Also disable textarea when hidden

        except Exception as e:
            logger.error(
                f"Error toggling interaction area visibility: {e}", exc_info=True
            )

    def prompt_for_user_input(self, context: ProjectContext):
        """Called by worker when user input is needed."""
        logging.info("Workflow requires user input. Updating UI.")
        self.current_context = context
        try:
            question_widget = self.query_one("#interaction-questions", Static)
            # Safely get questions
            questions = (
                context.refined_requirements.get("outstanding_questions", [])
                if context.refined_requirements
                else []
            )
            if isinstance(questions, list) and questions:
                formatted_questions = "\n".join([f"- {q}" for q in questions])
                question_widget.update(formatted_questions)
            else:
                question_widget.update(
                    "[Assistant needs input, but no specific questions extracted/found.]"
                )
            self.show_interaction_area(True)
            self.update_status_line("Paused - Waiting for User Response")
        except Exception as e:
            logger.error(f"Error displaying user input prompt: {e}", exc_info=True)
            self.update_status_line("Error displaying prompt!")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle start and submit buttons."""
        if event.button.id == "start-button":
            initial_request = self.query_one("#initial-request", Input).value
            project_id = self.query_one("#project-id", Input).value or None
            if not initial_request:
                self.workflow_status = "Error: Initial request empty."
                logging.error("Start empty request.")
                return
            selected_wrappers = []  # TODO: Get from UI
            event.button.disabled = True
            self.show_interaction_area(False)
            self.query_one(Log).clear()
            self.workflow_status = "Starting Workflow..."
            logging.info(
                f"Starting workflow - ID: {project_id or '(New)'}, Request: {initial_request[:50]}..., Wrappers: {selected_wrappers}"
            )
            # Run the worker
            self.run_worker(
                self.run_orchestrator_worker(
                    initial_request, project_id, False, selected_wrappers
                ),
                name=f"Workflow_{project_id or 'New'}",
                group="orchestrator_workflows",
                exclusive=True,
                thread=True,
            )

        elif event.button.id == "submit-response-button":
            response_text = self.query_one("#user-response-area", TextArea).text
            current_ctx = self.current_context
            if not response_text:
                self.update_status_line("Status: Please enter a response.")
                return

            # Check context exists before proceeding
            if not current_ctx:
                logging.error("Submit response: no current context.")
                self.update_status_line("Error: No context to resume.")
                self.show_interaction_area(False)
                try:  # Try to re-enable start button if possible
                    self.query_one("#start-button", Button).disabled = False
                except Exception:
                    pass
                return

            logging.info(f"User response submitted: {response_text[:100]}...")
            current_ctx.latest_user_response = response_text
            current_ctx.user_feedback.append(
                {
                    "timestamp": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                    "response_to_phase": current_ctx.current_phase,
                    "response_text": response_text,
                }
            )
            current_ctx.status = "Resuming"
            # Update UI immediately
            event.button.disabled = True
            self.query_one("#user-response-area", TextArea).text = ""
            self.show_interaction_area(False)
            self.update_status_line("Status: Resuming Workflow...")
            logging.info(f"Resuming workflow for Project ID: {current_ctx.project_id}")
            # Run the worker again for resume
            self.run_worker(
                self.run_orchestrator_worker(
                    initial_request=None,
                    project_id=current_ctx.project_id,
                    resume=True,
                    selected_wrappers=current_ctx.selected_wrappers,
                ),
                name=f"Workflow_{current_ctx.project_id}_Resume",
                group="orchestrator_workflows",
                exclusive=True,
                thread=True,
            )

    async def run_orchestrator_worker(
        self,
        initial_request: Optional[str],
        project_id: Optional[str],
        resume: bool,
        selected_wrappers: Optional[List[str]],
    ):
        """Runs the orchestrator workflow in a background worker."""
        final_context: Optional[ProjectContext] = None
        try:
            self.call_from_thread(
                setattr, self, "workflow_status", "Instantiating Orchestrator..."
            )
            orchestrator = Orchestrator(config_module=cfg)
            self.call_from_thread(
                setattr,
                self,
                "workflow_status",
                f"{'Resuming' if resume else 'Running'} Workflow...",
            )
            final_context = orchestrator.run_workflow(
                initial_user_request=initial_request,
                project_id=project_id,
                resume=resume,
                selected_wrappers=selected_wrappers,
            )
            # Update UI based on final state
            if final_context.status == "NeedsUserInput":
                self.call_from_thread(self.prompt_for_user_input, final_context)
            else:
                self.call_from_thread(
                    setattr,
                    self,
                    "workflow_status",
                    f"Workflow Finished: {final_context.status}",
                )
        except Exception as e:
            error_msg = f"Workflow Error: {type(e).__name__}: {e}"
            logging.critical(f"Error in worker: {e}", exc_info=True)
            self.call_from_thread(setattr, self, "workflow_status", error_msg)
        finally:
            # Re-enable appropriate button(s) based on final state
            def enable_buttons():
                """Safely enable/disable buttons in the main thread."""
                try:
                    should_start_be_disabled = (
                        final_context is not None
                        and final_context.status == "NeedsUserInput"
                    )
                    self.query_one(
                        "#start-button", Button
                    ).disabled = should_start_be_disabled
                    # Submit button always disabled unless shown by show_interaction_area
                    submit_button = self.query_one("#submit-response-button", Button)
                    if submit_button:
                        submit_button.disabled = True
                except Exception:
                    logger.error("Failed re-enable/disable buttons.")

            self.call_from_thread(enable_buttons)


if __name__ == "__main__":
    import datetime  # Keep import here for direct run if needed

    app = WizardProTUI()
    app.run()
