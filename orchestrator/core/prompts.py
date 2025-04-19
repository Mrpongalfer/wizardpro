# orchestrator/core/prompts.py
import os
import yaml
import logging
from typing import Dict, List, Optional, Any, Union
from jinja2 import Environment, BaseLoader, TemplateNotFound, meta, StrictUndefined
# Corrected Relative Import for config
from .. import config
# Import ProjectContext for type hinting only
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .data_types import ProjectContext

logger = logging.getLogger(__name__)

# Simple Jinja2 Loader that loads templates from our dictionary cache
class DictLoader(BaseLoader):
    def __init__(self, templates: Dict[str, str]):
        self.templates = templates

    def get_source(self, environment, template):
        if template not in self.templates:
            raise TemplateNotFound(template)
        source = self.templates[template]
        return source, None, lambda: True

class PromptManager:
    """
    Manages loading, caching, templating, and assembling prompts using Jinja2.
    Loads prompts from YAML files defined in config.PROMPT_DIR_PATH.
    Handles injection of functional and tonal wrappers.
    """

    def __init__(self, prompt_dir: str = config.PROMPT_DIR_PATH):
        # (__init__ implementation unchanged - uses relative config import)
        self.prompt_dir = prompt_dir
        self.main_prompts: Dict[str, str] = {}
        self.wrapper_prompts: Dict[str, Dict[str, Any]] = {}
        self.sub_injection_prompts: Dict[str, str] = {}
        self.all_templates: Dict[str, str] = {} # Cache for Jinja env
        self._load_all_prompts() # Load prompts on initialization
        self.jinja_env = Environment(loader=DictLoader(self.all_templates), autoescape=False, undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
        self.jinja_env.filters['toyaml'] = self._to_yaml_filter
        self.gamified_tone_wrapper_details: Optional[Dict[str, Any]] = self.wrapper_prompts.get("GamifiedToneWrapper")
        logger.info(f"PromptManager initialized. Loaded {len(self.main_prompts)} main, {len(self.wrapper_prompts)} wrapper, {len(self.sub_injection_prompts)} sub prompts from {self.prompt_dir}")

    def _to_yaml_filter(self, value, **kwargs):
        # (Implementation unchanged)
        try: import yaml; default_kwargs = {'default_flow_style': False, 'allow_unicode': True, 'indent': 2, 'width': 80}; default_kwargs.update(kwargs); return yaml.dump(value, **default_kwargs)
        except ImportError: logger.warning("PyYAML not installed, 'toyaml' filter returning str()."); return str(value)
        except Exception as e: logger.error(f"Error in 'toyaml' filter: {e}"); return f"Error: {e}"

    def _load_all_prompts(self):
        # (Implementation unchanged)
        self.main_prompts = self._load_prompt_file("main_prompts.yaml", is_main=True); self.wrapper_prompts = self._load_prompt_file("wrapper_prompts.yaml"); self.sub_injection_prompts = self._load_prompt_file("sub_injection_prompts.yaml", is_sub=True)
        self.all_templates = {f"main:{k}": v for k, v in self.main_prompts.items()}; self.all_templates.update({f"wrapper:{k}": v['prompt_text'] for k, v in self.wrapper_prompts.items() if isinstance(v, dict) and isinstance(v.get('prompt_text'), str)}); self.all_templates.update({f"sub:{k}": v for k, v in self.sub_injection_prompts.items()})
        if hasattr(self, 'jinja_env'): self.jinja_env.loader = DictLoader(self.all_templates)
        else: self.jinja_env = Environment(loader=DictLoader(self.all_templates), autoescape=False, undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True); self.jinja_env.filters['toyaml'] = self._to_yaml_filter
        self.gamified_tone_wrapper_details = self.wrapper_prompts.get("GamifiedToneWrapper")

    def _load_prompt_file(self, filename: str, is_main: bool = False, is_sub: bool = False) -> Dict:
        """Loads prompts from a YAML file, handling structure variations."""
        # (Implementation with corrected indentation within the 'else' block)
        filepath = os.path.join(self.prompt_dir, filename);
        if not os.path.exists(filepath): logger.warning(f"Prompt file not found: {filepath}. Creating dummy."); self._create_dummy_prompt_file(filepath); return {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f: data = yaml.safe_load(f)
            if not data: logger.warning(f"Prompt file empty: {filepath}"); return {}

            # --- Validation/Normalization ---
            if is_main or is_sub:
                # Expect keys:strings, values:strings
                return {str(k): str(v) for k, v in data.items() if isinstance(k, (str, int)) and isinstance(v, (str, int, float))}
            else:
                # Wrappers: keys:strings, values:dicts containing 'prompt_text':string
                valid_data = {}
                # --- Start Corrected Indentation ---
                for k, v in data.items(): # Correctly indented under 'else'
                    if isinstance(k, str) and isinstance(v, dict) and isinstance(v.get('prompt_text'), str):
                        valid_data[k] = v # Correctly indented under 'if'
                    else:
                        logger.warning(f"Skipping invalid wrapper entry '{k}' in {filename}. Expected dict with 'prompt_text'.") # Correctly indented under 'else'
                return valid_data # Correctly indented under 'else'
                # --- End Corrected Indentation ---
        except yaml.YAMLError as e: logger.error(f"YAML Error in {filepath}: {e}", exc_info=True); return {}
        except Exception as e: logger.error(f"Error reading {filepath}: {e}", exc_info=True); return {}

    def _create_dummy_prompt_file(self, filepath: str):
        # (Implementation unchanged)
        if os.path.exists(filepath): return
        try:
             dirname = os.path.dirname(filepath); os.makedirs(dirname, exist_ok=True); dummy_content = "# Dummy prompt file created. Populate.\n"
             if filepath.endswith("main_prompts.yaml"): dummy_content += "Phase1_Requirements: |-\n  ...\n"
             elif filepath.endswith("wrapper_prompts.yaml"): dummy_content += "ExampleFunctionalWrapper:\n  prompt_text: |-\n    ...\n  description: ...\n"
             elif filepath.endswith("sub_injection_prompts.yaml"): dummy_content += "OptimizeAlgorithm: |-\n  ...\n"
             with open(filepath, 'w', encoding='utf-8') as f: f.write(dummy_content); logger.info(f"Created dummy file: {filepath}")
        except Exception as e: logger.error(f"Failed create dummy file {filepath}: {e}", exc_info=True)

    def _render_template(self, template_name: str, render_data: Dict[str, Any]) -> str:
        """Renders a Jinja2 template with the given data dictionary."""
        # (Implementation with corrected method call _render_template)
        logger.debug(f"Rendering template: {template_name}")
        try:
            template = self.jinja_env.get_template(template_name)
            rendered = template.render(render_data)
            logger.debug(f"Template '{template_name}' rendered successfully (length: {len(rendered)}).")
            return rendered
        except TemplateNotFound: logger.error(f"Template '{template_name}' not found. Available: {list(self.all_templates.keys())}"); return f"Error: Template '{template_name}' not found."
        except Exception as e:
            logger.error(f"Error rendering template '{template_name}': {e}", exc_info=True); missing_vars = set()
            try: template_source = self.jinja_env.loader.get_source(self.jinja_env, template_name)[0]; parsed_content = self.jinja_env.parse(template_source); declared_vars = meta.find_undeclared_variables(parsed_content); missing_vars = declared_vars - render_data.keys()
            except Exception: pass
            error_detail = f"Reason: {e}" + (f". Potential missing vars: {missing_vars}" if missing_vars else "")
            return f"--- ERROR RENDERING PROMPT TEMPLATE '{template_name}'. {error_detail}. Check Logs. ---"


    def assemble_prompt(self,
                        phase_name: str,
                        context: 'ProjectContext',
                        sub_injection_key: Optional[str] = None,
                        sub_injection_data: Optional[Dict[str, Any]] = None) -> str:
        """Assembles the final prompt, passing the context object 'ctx' to Jinja templates."""
        # (Implementation with corrected _render_template call)
        logger.info(f"Assembling prompt - Phase: {phase_name}, Sub: {sub_injection_key}, Wrappers: {context.selected_wrappers}")
        if sub_injection_key:
            if not isinstance(self.sub_injection_prompts.get(sub_injection_key), str): error_msg = f"Sub-injection key '{sub_injection_key}' invalid."; logger.error(error_msg); return f"Error: {error_msg}"
            base_template_name = f"sub:{sub_injection_key}"
        else:
            if not isinstance(self.main_prompts.get(phase_name), str): error_msg = f"Main phase key '{phase_name}' invalid."; logger.error(error_msg); return f"Error: {error_msg}"
            base_template_name = f"main:{phase_name}"
        logger.debug(f"Using base template: {base_template_name}")
        try: render_data = {'ctx': context}; # Pass context object as 'ctx'
        except Exception as e: logger.error(f"Context prep failed: {e}", exc_info=True); return f"Error: Failed context prep. Reason: {e}"
        if sub_injection_data: render_data.update(sub_injection_data); logger.debug(f"Added sub_data keys: {list(sub_injection_data.keys())}")
        core_prompt_text = self._render_template(base_template_name, render_data) # Use corrected method name
        if core_prompt_text.startswith("Error:") or core_prompt_text.startswith("--- ERROR"): return core_prompt_text
        assembled_functional_prompt = core_prompt_text
        active_functional_wrappers = [name for name in context.selected_wrappers if name != "GamifiedToneWrapper" and name in self.wrapper_prompts]
        if active_functional_wrappers:
            logger.debug(f"Applying functional wrappers: {active_functional_wrappers}"); rendered_wrapper_texts = []
            for wrapper_name in reversed(active_functional_wrappers):
                wrapper_template_name = f"wrapper:{wrapper_name}"
                if wrapper_template_name in self.all_templates:
                    rendered_wrapper = self._render_template(wrapper_template_name, render_data) # Pass same context dict
                    if not rendered_wrapper.startswith("Error:") and not rendered_wrapper.startswith("--- ERROR"):
                         if rendered_wrapper.strip(): rendered_wrapper_texts.append(rendered_wrapper.strip())
                         else: logger.debug(f"Wrapper '{wrapper_name}' rendered empty, skipping.")
                    else: logger.warning(f"Skipping wrapper '{wrapper_name}' due to render error: {rendered_wrapper}")
                else: logger.warning(f"Wrapper template '{wrapper_name}' not found.")
            if rendered_wrapper_texts: assembled_functional_prompt = "\n\n---\n[Wrapper Instructions Start]\n---\n".join(rendered_wrapper_texts) + f"\n\n---\n[End Wrapper Instructions / Start Core Task]\n---\n\n{core_prompt_text}"; logger.debug(f"Functional wrappers prepended.")
        final_prompt = assembled_functional_prompt
        if "GamifiedToneWrapper" in context.selected_wrappers and self.gamified_tone_wrapper_details:
            logger.debug("Applying Gamified Tone Wrapper."); tone_wrapper_template_name = "wrapper:GamifiedToneWrapper"
            if tone_wrapper_template_name in self.all_templates:
                 try:
                     tone_render_data = render_data.copy(); tone_render_data['core_prompt'] = assembled_functional_prompt; tone_render_data['llm_role'] = self._get_llm_role_for_context(phase_name, sub_injection_key); tone_render_data['phase_title'] = phase_name
                     final_prompt = self._render_template(tone_wrapper_template_name, tone_render_data)
                     if final_prompt.startswith("Error:") or final_prompt.startswith("--- ERROR"): logger.error(f"Failed render Gamified Tone Wrapper, falling back. Error: {final_prompt}"); final_prompt = assembled_functional_prompt
                     else: logger.debug("Successfully applied Gamified Tone Wrapper.")
                 except Exception as e: logger.error(f"Error applying Gamified Tone Wrapper: {e}", exc_info=True); final_prompt = assembled_functional_prompt
            else: logger.warning("Gamified Tone Wrapper selected, but template not found."); final_prompt = assembled_functional_prompt
        logger.info(f"Final prompt assembled (Phase: {phase_name}, Sub: {sub_injection_key}, Length: {len(final_prompt)} chars).")
        return final_prompt

    def _get_llm_role_for_context(self, phase_name: str, sub_injection_key: Optional[str]) -> str:
        # (Implementation unchanged)
        if sub_injection_key: role = sub_injection_key.replace("Optimize", "Optimizer").replace("Add", "").replace("Check", "Checker").replace("Refactor", "Refactorer").replace("Generate","Generator").replace("Identify","Identifier").replace("Fix","Fixer"); return f"{role} Specialist"
        phase_roles = {"Phase1_Requirements": "Project Initiator", "Phase2_Architecture": "System Architect", "Phase3_CodeGeneration": "Code Generation Lead", "Phase4_Testing": "Quality Assurance Lead", "Phase5_Deployment": "DevOps Engineer"}
        fallback_role = phase_name.replace("_", " "); return phase_roles.get(phase_name, fallback_role)

