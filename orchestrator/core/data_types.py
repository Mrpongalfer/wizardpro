# orchestrator/core/data_types.py
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Union
import datetime
import uuid
import logging  # Added for logging within method
import yaml  # Import at module level if used frequently

logger = logging.getLogger(__name__)

# Using Pydantic can add validation if needed: pip install pydantic
# from pydantic.dataclasses import dataclass


@dataclass
class LLMInput:
    # (Unchanged)
    prompt: str
    model_identifier: str
    temperature: float = 0.7
    max_tokens: int = 3000
    top_p: Optional[float] = None
    relevant_context: Optional[Dict[str, Any]] = field(default_factory=dict)


@dataclass
class LLMOutput:
    # (Unchanged)
    text: str
    model_identifier: Optional[str] = None
    input_prompt: Optional[str] = None
    raw_response: Optional[Any] = None
    cost: Optional[float] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    finish_reason: Optional[str] = None

    def to_dict(self):
        d = asdict(self)
        d.pop("input_prompt", None)
        d.pop("raw_response", None)
        return d


@dataclass
class ProjectContext:
    # (Fields unchanged - includes latest_user_response)
    project_id: str = field(
        default_factory=lambda: f"proj_{uuid.uuid4().hex[:8]}_{datetime.datetime.now().strftime('%Y%m%d')}"
    )
    initial_request: Optional[str] = None
    refined_requirements: Optional[Dict[str, Any]] = field(default_factory=dict)
    architecture_document: Optional[Dict[str, Any]] = field(default_factory=dict)
    technology_stack: List[str] = field(default_factory=list)
    generated_code: Dict[str, str] = field(default_factory=dict)
    code_analysis: List[Dict[str, Any]] = field(default_factory=list)
    unit_tests: Dict[str, str] = field(default_factory=dict)
    test_results: List[Dict[str, Any]] = field(default_factory=list)
    debugging_info: List[str] = field(default_factory=list)
    deployment_config: Dict[str, Union[str, Dict]] = field(default_factory=dict)
    documentation: Dict[str, str] = field(default_factory=dict)
    current_phase: str = "Initialization"
    status: str = "Pending"
    knowledge_graph: Dict[str, Any] = field(default_factory=dict)
    error_log: List[Dict[str, Any]] = field(default_factory=list)
    selected_wrappers: List[str] = field(default_factory=list)
    latest_user_response: Optional[str] = None  # Stores the most recent user text input
    user_feedback: List[Dict[str, Any]] = field(default_factory=list)
    latest_user_response: Optional[str] = None
    llm_call_history: List[Dict[str, Any]] = field(default_factory=list)

    # Methods add_log_entry, update_status, add_llm_call (Unchanged)
    def add_log_entry(
        self, phase: str, level: str, message: str, error_details: Optional[str] = None
    ):
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "phase": phase,
            "level": level.upper(),
            "message": message,
        }
        if error_details:
            entry["details"] = error_details
        self.error_log.append(entry)

    def update_status(self, new_status: str, current_phase: Optional[str] = None):
        self.status = new_status
        if current_phase:
            self.current_phase = current_phase

    def add_llm_call(self, llm_output: LLMOutput):
        call_record = llm_output.to_dict()
        self.llm_call_history.append(call_record)

    # Method get_full_codebase (Unchanged)
    def get_full_codebase(self, max_len: int = 10000) -> str:
        full_code = ""
        separator = "\n\n---\n\n"
        logger.debug(f"Generating codebase string (max ~{max_len})...")
        sorted_files = sorted(self.generated_code.keys())
        for filepath in sorted_files:
            code = self.generated_code[filepath]
            header = f"--- File: {filepath} ---\n"
            footer = "\n--- End File ---\n"
            if (
                len(full_code) + len(header) + len(code) + len(footer) + len(separator)
                > max_len
            ):
                logger.warning(f"Codebase truncated before {filepath}")
                full_code += "\n[CODEBASE TRUNCATED]"
                break
            full_code += separator + header + code + footer
        if not full_code and self.generated_code:
            full_code = "[CODEBASE TRUNCATED]"
        elif not self.generated_code:
            full_code = "[No code generated yet]"
        logger.debug(f"Codebase string length: {len(full_code)}")
        return full_code.strip()

    # --- CORRECTED Helper Methods ---
    def get_requirements_summary(self, format: str = "yaml") -> str:
        """Helper to get a string summary of requirements."""
        if not self.refined_requirements:
            return "[No requirements defined]"
        if format == "yaml":
            try:
                # PyYAML should be installed via requirements.txt
                return yaml.dump(
                    self.refined_requirements,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )
            except ImportError:
                logger.warning("PyYAML missing for requirements summary.")
                return str(self.refined_requirements)
            except Exception as e:
                logger.error(f"YAML dump failed for requirements: {e}")
                return str(self.refined_requirements)
        else:
            # Fallback to simple string representation
            return str(self.refined_requirements)

    def get_architecture_summary(self, format: str = "yaml") -> str:
        """Helper to get a string summary of the architecture."""
        if not self.architecture_document:
            return "[No architecture defined]"
        if format == "yaml":
            try:
                # PyYAML should be installed via requirements.txt
                return yaml.dump(
                    self.architecture_document,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )
            except ImportError:
                logger.warning("PyYAML missing for architecture summary.")
                return str(self.architecture_document)
            except Exception as e:
                logger.error(f"YAML dump failed for architecture: {e}")
                return str(self.architecture_document)
        else:
            # Fallback to simple string representation
            return str(self.architecture_document)

    # --- End Corrected Helper Methods ---

    # Methods to_dict, from_dict (Unchanged)
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectContext":
        instance = cls(**data)
        return instance
