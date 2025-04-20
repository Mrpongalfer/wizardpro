# orchestrator/core/utils.py
import logging
import json
import os
import datetime
import uuid  # Needed for potential default reconstruction if using dataclasses.asdict directly
from typing import Optional, Dict, Union, List
from dataclasses import is_dataclass, asdict

# Corrected Relative Import for config

# Logging is configured based on config import now
logger = logging.getLogger(__name__)


# --- JSON Encoder/Decoder Helpers ---
class EnhancedJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime and other types."""

    def default(self, o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return {"__datetime__": True, "value": o.isoformat()}
        if isinstance(o, uuid.UUID):
            return {"__uuid__": True, "value": str(o)}
        if is_dataclass(o):
            return asdict(o)  # Use dataclasses.asdict for nested dataclasses
        try:
            return super().default(o)
        except TypeError:
            # Fallback for other potentially problematic types
            logger.warning(
                f"Could not JSON-encode type {type(o)}, converting to string."
            )
            return str(o)


def json_object_hook(dct):
    """Custom object hook for json.load to reconstruct specific types."""
    if "__datetime__" in dct:
        try:
            return datetime.datetime.fromisoformat(dct["value"])
        except ValueError:
            logger.warning(f"Failed to decode datetime string: {dct.get('value')}")
            return dct  # Return original dict if decoding fails
    if "__uuid__" in dct:
        try:
            return uuid.UUID(dct["value"])
        except ValueError:
            logger.warning(f"Failed to decode UUID string: {dct.get('value')}")
            return dct
    # TODO: Add reconstruction logic for other custom objects if needed
    return dct


# --- Context Persistence Functions ---
def save_project_context(
    context, filepath: str, project_id_in_path: bool = True
) -> bool:
    """
    Saves the ProjectContext state to a JSON file using the enhanced encoder.
    """
    project_id = getattr(context, "project_id", None)
    if project_id_in_path:
        if not project_id:
            logger.error("Cannot save by ID: context.project_id missing.")
            return False
        save_path = os.path.join(filepath, f"{project_id}.json")
    else:
        save_path = filepath

    logger.debug(f"Attempting to save project context to: {save_path}")
    # --- Corrected Syntax: try starts on new line ---
    try:
        dir_path = os.path.dirname(save_path)
        if dir_path:  # Only create if there's a directory part
            logger.debug(f"Ensuring directory exists: {dir_path}")
            os.makedirs(dir_path, exist_ok=True)

        # Use the context's built-in to_dict method if available and preferred,
        # otherwise use the enhanced encoder with asdict for dataclasses.
        if hasattr(context, "to_dict") and callable(context.to_dict):
            context_dict = context.to_dict()
            logger.debug("Using context.to_dict() for serialization.")
        elif is_dataclass(context):
            context_dict = asdict(
                context
            )  # Handles nested dataclasses better than __dict__
            logger.debug("Using dataclasses.asdict() for serialization.")
        else:
            logger.warning(
                "Context object is not a dataclass and has no to_dict method. Using basic __dict__."
            )
            context_dict = context.__dict__  # Less reliable fallback

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(context_dict, f, indent=4, cls=EnhancedJSONEncoder)

        logger.info(f"Project context saved successfully to {save_path}")
        return True
    # --- End Corrected Block ---
    except TypeError as e:
        logger.error(
            f"Serialization Error saving project context to {save_path}: {e}. Check EnhancedJSONEncoder.",
            exc_info=True,
        )
        return False
    except IOError as e:
        logger.error(
            f"I/O Error saving project context to {save_path}: {e}", exc_info=True
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error saving project context to {save_path}: {e}",
            exc_info=True,
        )
        return False


def load_project_context(
    filepath: str, project_id_in_path: bool = True, project_id: Optional[str] = None
):
    # (Implementation from Step 8a - unchanged internally)
    if project_id_in_path:
        if not project_id:
            logger.error("Cannot load by ID: project_id missing.")
            return None
        load_path = os.path.join(filepath, f"{project_id}.json")
    else:
        load_path = filepath
    logger.debug(f"Attempting load from: {load_path}")
    if not os.path.exists(load_path):
        logger.warning(f"Context file not found: {load_path}")
        return None
    try:
        with open(load_path, "r", encoding="utf-8") as f:
            context_dict = json.load(f, object_hook=json_object_hook)
        from .data_types import ProjectContext  # Local import

        if hasattr(ProjectContext, "from_dict") and callable(ProjectContext.from_dict):
            context = ProjectContext.from_dict(context_dict)
            logger.debug("Using ProjectContext.from_dict()")
        else:
            logger.warning("No from_dict method, using direct instantiation.")
            context = ProjectContext(
                **context_dict
            )  # May need more robust reconstruction
        logger.info(f"Context loaded from {load_path}")
        return context
    except Exception as e:
        logger.error(f"Error loading context from {load_path}: {e}", exc_info=True)
        return None


# --- Parsing Utilities (Unchanged) ---
def parse_yaml_from_llm(llm_output: str) -> Optional[Union[Dict, List]]:
    try:
        import yaml
        import re

        match = re.search(
            r"```yaml\s*(.*?)\s*```", llm_output, re.DOTALL | re.IGNORECASE
        )
        if match:
            yaml_str = match.group(1)
            logger.debug("Found YAML block, parsing.")
            return yaml.safe_load(yaml_str)
        else:
            logger.warning("No YAML Markdown block found in LLM output.")
            return None
    except ImportError:
        logger.warning("PyYAML not installed. Cannot parse YAML.")
        return None
    except yaml.YAMLError as e:
        logger.warning(f"YAML Decode Error: {e}. Snippet: {llm_output[:100]}...")
        return None
    except Exception as e:
        logger.error(f"YAML parsing error: {e}", exc_info=True)
        return None


def parse_code_blocks(llm_output: str) -> Dict[str, str]:
    code_blocks = {}
    try:
        import re

        pattern = re.compile(r"```(\w+)?\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
        matches = pattern.findall(llm_output)
        for lang, code in matches:
            language_key = lang.lower() if lang else "unknown"
            if language_key not in code_blocks:
                code_blocks[language_key] = code.strip()
                logger.debug(f"Parsed code block: {language_key}")
        if not matches:
            logger.warning("No standard Markdown code blocks found.")
    except Exception as e:
        logger.error(f"Error parsing code blocks: {e}", exc_info=True)
    return code_blocks


def parse_code_blocks_with_filepaths(llm_output: str) -> Dict[str, str]:
    file_code_map = {}
    try:
        import re

        pattern = re.compile(
            r"^(?:[#\/-]+\s*File:|--- File:)\s*([\w\/\.\-\_]+)\s*\n```(?:\w+)?\s*\n(.*?)\n```",
            re.MULTILINE | re.DOTALL | re.IGNORECASE,
        )
        matches = pattern.findall(llm_output)
        for filepath, code in matches:
            clean_filepath = filepath.strip()
            if clean_filepath not in file_code_map:
                file_code_map[clean_filepath] = code.strip()
                logger.debug(f"Parsed code block for file: {clean_filepath}")
            else:
                logger.warning(
                    f"Multiple blocks for file: {clean_filepath}. Using first."
                )
        if not file_code_map:
            logger.warning("No code blocks with 'File:' markers found.")
    except Exception as e:
        logger.error(f"Error parsing code blocks with file paths: {e}", exc_info=True)
    return file_code_map
