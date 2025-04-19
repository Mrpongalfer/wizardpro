# orchestrator/core/llm_tools.py
import logging
import time
import requests # Needed for exceptions
import random # For jitter in backoff
from .. import config # Use relative import
from typing import Dict, Optional, Any
from .data_types import LLMInput, LLMOutput # Use relative import

logger = logging.getLogger(__name__)

class LLMTool:
    """Base class for interacting with Large Language Models, includes retry logic."""
    # --- Retry Configuration ---
    MAX_RETRIES = 3
    INITIAL_BACKOFF_SECS = 1 # Initial wait time for generic errors
    MAX_BACKOFF_SECS = 10    # Max wait time between retries
    RATE_LIMIT_WAIT_SECS = 25 # Default wait for 429 if Retry-After isn't provided (+ some buffer)

    def __init__(self, api_key: str, model_identifier: str):
        # (__init__ unchanged)
        if not api_key: logger.error(f"{self.__class__.__name__} needs API key for {model_identifier}. Non-functional.");
        self.api_key = api_key; self.model_identifier = model_identifier
        logger.info(f"Initialized {self.__class__.__name__} for model {self.model_identifier}")

    def execute(self, llm_input: LLMInput) -> LLMOutput:
        """
        Public method to execute the LLM request with retry logic
        for specific HTTP errors (429, 5xx).
        """
        if not self.api_key:
             logger.error(f"Cannot execute {self.model_identifier}: API key missing.")
             return LLMOutput(text="", error="API key missing", model_identifier=self.model_identifier, input_prompt=llm_input.prompt)

        logger.debug(f"Executing LLM call with {self.__class__.__name__} for model {self.model_identifier}")
        logger.debug(f"Input prompt (start): {llm_input.prompt[:100]}...") # Log less potentially sensitive data
        start_time_overall = time.monotonic()
        output = LLMOutput(text="", model_identifier=self.model_identifier, input_prompt=llm_input.prompt) # Initialize output

        last_error = None # Keep track of the last error encountered during retries

        for attempt in range(self.MAX_RETRIES + 1): # +1 because range is exclusive, allows MAX_RETRIES retries
            start_time_attempt = time.monotonic()
            is_last_attempt = (attempt == self.MAX_RETRIES)

            try:
                # --- Actual API call delegated to subclass ---
                api_output = self._execute_api_call(llm_input)

                # --- Process successful API call result ---
                output.text = api_output.text
                output.raw_response = api_output.raw_response
                output.cost = api_output.cost
                output.finish_reason = api_output.finish_reason
                if api_output.error: # Check if subclass reported a logical error despite successful call
                    output.error = api_output.error
                    logger.warning(f"API call successful but tool reported error for {self.model_identifier}: {output.error}")
                    # Don't retry logical errors reported by the tool, break immediately
                    break
                else:
                    logger.info(f"LLM call attempt {attempt + 1} successful for {self.model_identifier}.")
                    output.error = None # Ensure error is cleared on success
                    last_error = None # Clear last error
                    break # Successful call, exit retry loop

            except requests.exceptions.HTTPError as e:
                last_error = e # Store the exception
                status_code = e.response.status_code if e.response is not None else 500 # Default to 500 if no response object

                # --- Handle Retryable Errors ---
                wait_time = 0
                if status_code == 429: # Rate Limit
                    logger.warning(f"Rate limit (429) hit for {self.model_identifier} on attempt {attempt + 1}/{self.MAX_RETRIES+1}.")
                    if is_last_attempt: break # Don't wait if it's the last attempt
                    # Check for Retry-After header
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        try: wait_time = int(retry_after) + random.uniform(0.5, 1.5) # Add jitter
                        except ValueError: wait_time = self.RATE_LIMIT_WAIT_SECS * (attempt + 1) # Fallback backoff
                    else:
                         # Exponential backoff + jitter for rate limit if no header
                         wait_time = min(self.INITIAL_BACKOFF_SECS * (2 ** attempt), self.MAX_BACKOFF_SECS) + random.uniform(0, 1)
                         wait_time = max(wait_time, self.RATE_LIMIT_WAIT_SECS) # Ensure minimum wait for rate limits

                elif 500 <= status_code < 600: # Server Errors (5xx)
                    logger.warning(f"Server error ({status_code}) for {self.model_identifier} on attempt {attempt + 1}/{self.MAX_RETRIES+1}.")
                    if is_last_attempt: break
                    # Exponential backoff + jitter for server errors
                    wait_time = min(self.INITIAL_BACKOFF_SECS * (2 ** attempt), self.MAX_BACKOFF_SECS) + random.uniform(0, 1)

                else: # Non-retryable HTTP errors (e.g., 403 Forbidden, 401 Unauthorized, 400 Bad Request)
                    logger.error(f"Non-retryable HTTP error ({status_code}) for {self.model_identifier}: {e}", exc_info=True)
                    # Construct detailed error message (moved from previous version)
                    error_details = str(e); resp_text = "[No response body]"
                    if e.response is not None:
                         try: resp_text = e.response.text[:200] # Limit response snippet
                         except Exception: pass
                    output.error = f"API Request Failed (HTTP {status_code}): {error_details} | Resp: {resp_text}"
                    break # Exit loop immediately for non-retryable errors

                # --- Perform Wait and Continue to Next Attempt ---
                logger.info(f"Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
                # Continue to the next iteration of the loop

            except requests.exceptions.Timeout:
                last_error = requests.exceptions.Timeout("Request timed out")
                logger.warning(f"Timeout for {self.model_identifier} on attempt {attempt + 1}/{self.MAX_RETRIES+1}.")
                if is_last_attempt: break
                wait_time = min(self.INITIAL_BACKOFF_SECS * (2 ** attempt), self.MAX_BACKOFF_SECS) + random.uniform(0, 1)
                logger.info(f"Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time) # Wait and continue

            except requests.exceptions.RequestException as e:
                # Handle other potential connection errors (DNS, network, etc.)
                last_error = e
                logger.error(f"Connection/Request Error for {self.model_identifier} on attempt {attempt + 1}: {e}", exc_info=True)
                if is_last_attempt: break
                wait_time = min(self.INITIAL_BACKOFF_SECS * (2 ** attempt), self.MAX_BACKOFF_SECS) + random.uniform(0, 1)
                logger.info(f"Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time) # Wait and continue

            except NotImplementedError:
                 err_msg = f"_execute_api_call not implemented for {self.__class__.__name__}"; logger.error(err_msg); output.error = err_msg; last_error = NotImplementedError(err_msg); break # Cannot retry this

            except Exception as e:
                # Catch any other unexpected errors during _execute_api_call
                last_error = e
                err_msg = f"Unexpected error during LLM execution: {e}"
                logger.critical(f"Unexpected critical error in {self.__class__.__name__}._execute_api_call ({self.model_identifier}): {e}", exc_info=True)
                output.error = err_msg
                break # Stop on unexpected critical errors

        # --- After the Loop ---
        end_time_overall = time.monotonic()
        output.latency_ms = (end_time_overall - start_time_overall) * 1000

        # If loop finished due to max retries, set the final error message
        if attempt == self.MAX_RETRIES and output.error is None: # Check if we exited loop due to retries but error wasn't set by non-retryable path
            if last_error:
                error_context = f" (Last Error: {type(last_error).__name__}: {str(last_error)})"
                output.error = f"LLM call failed after {self.MAX_RETRIES + 1} attempts for {self.model_identifier}{error_context}."
                logger.error(output.error)
            else: # Should not happen, but safeguard
                 output.error = f"LLM call failed after exhausting retries for {self.model_identifier} (Unknown final error)."
                 logger.error(output.error)

        # Final log summarizing outcome
        log_level = logging.WARNING if output.error else logging.INFO
        logger.log(log_level, f"LLM execution finished: {self.model_identifier}. Latency: {output.latency_ms:.2f} ms. Status: {'FAILED' if output.error else 'Success'}. Error: {output.error or 'None'}")

        return output

    def _execute_api_call(self, llm_input: LLMInput) -> LLMOutput:
        """Subclasses implement the specific API call logic here."""
        raise NotImplementedError

# --- Implementations for OpenAITool, AnthropicTool etc. remain the same ---
# --- They don't need to change, as retry logic is in the base execute method ---

class OpenAITool(LLMTool):
    """Handles interaction with OpenAI models using Requests (Example)."""
    API_ENDPOINT = "https://api.openai.com/v1/chat/completions"
    def __init__(self, api_key: str = config.OPENAI_API_KEY, model_identifier: str = "gpt-4"): super().__init__(api_key, model_identifier)
    def _execute_api_call(self, llm_input: LLMInput) -> LLMOutput:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model_identifier, "messages": [{"role": "user", "content": llm_input.prompt}], "temperature": llm_input.temperature, "max_tokens": llm_input.max_tokens, "top_p": llm_input.top_p}; payload = {k: v for k, v in payload.items() if v is not None}
        # Note: Requests raises HTTPError on 4xx/5xx if raise_for_status() is called
        response = requests.post(self.API_ENDPOINT, json=payload, headers=headers, timeout=180)
        response.raise_for_status() # Let the base class handle HTTPError
        data = response.json()
        output_text = ""; finish_reason = None; cost = None
        if data.get('choices') and data['choices']: choice = data['choices'][0]; finish_reason = choice.get('finish_reason'); output_text = choice.get('message', {}).get('content', '').strip()
        if not output_text: logger.warning(f"OpenAI response empty. Finish:{finish_reason}. M:{self.model_identifier}")
        # TODO: cost = calculate_openai_cost(...)
        return LLMOutput(text=output_text, raw_response=data, cost=cost, finish_reason=finish_reason)

class AnthropicTool(LLMTool):
    """Handles interaction with Anthropic models using Requests (Example)."""
    API_ENDPOINT = "https://api.anthropic.com/v1/messages"
    def __init__(self, api_key: str = config.ANTHROPIC_API_KEY, model_identifier: str = "claude-3-opus-20240229"): super().__init__(api_key, model_identifier)
    def _execute_api_call(self, llm_input: LLMInput) -> LLMOutput:
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        payload = {"model": self.model_identifier, "system": llm_input.relevant_context.get("system_prompt", "You are helpful."), "messages": [{"role": "user", "content": llm_input.prompt}], "temperature": llm_input.temperature, "max_tokens": llm_input.max_tokens, "top_p": llm_input.top_p}; payload = {k: v for k, v in payload.items() if v is not None}
        response = requests.post(self.API_ENDPOINT, json=payload, headers=headers, timeout=180)
        response.raise_for_status() # Let the base class handle HTTPError
        data = response.json()
        output_text = ""; finish_reason = data.get('stop_reason'); cost = None
        if data.get('content') and isinstance(data['content'], list): output_text = "".join([item.get('text', '') for item in data['content'] if item.get('type') == 'text']).strip()
        if not output_text: logger.warning(f"Anthropic response empty. Finish:{finish_reason}. M:{self.model_identifier}")
        # TODO: cost = calculate_anthropic_cost(...)
        return LLMOutput(text=output_text, raw_response=data, cost=cost, finish_reason=finish_reason)

# --- LLMFactory remains the same ---
class LLMFactory:
    _tool_cache: Dict[str, LLMTool] = {}
    @staticmethod
    def get_tool(model_identifier: Optional[str]) -> LLMTool:
        # (Implementation unchanged - relies on config import)
        if not model_identifier: default_model = "openai:gpt-3.5-turbo"; logger.warning(f"No model specified, using default: {default_model}"); model_identifier = default_model # Changed default here too
        model_id_lower = model_identifier.lower(); provider_prefix = None
        if ":" in model_id_lower:
            try: provider_prefix, model_id_lower = model_id_lower.split(":", 1)
            except ValueError: logger.warning(f"Invalid model format: {model_identifier}")
        if model_identifier in LLMFactory._tool_cache:
            cached_tool = LLMFactory._tool_cache[model_identifier]; key_attr = None
            if isinstance(cached_tool, OpenAITool): key_attr = config.OPENAI_API_KEY
            elif isinstance(cached_tool, AnthropicTool): key_attr = config.ANTHROPIC_API_KEY
            # Add checks for other tools
            if key_attr: cached_tool.api_key = key_attr # Update key in case config changed? Risky maybe.
            else: logger.warning(f"API Key missing in config for cached {model_identifier}. Re-creating.")
            if cached_tool.api_key: return cached_tool
            else: logger.warning(f"Cached {model_identifier} lacks key, re-creating.")
        logger.info(f"Creating LLMTool instance for: {model_identifier}"); tool_instance = None; error_message = None
        try:
            if provider_prefix == "openai" or "gpt" in model_id_lower:
                if not config.OPENAI_API_KEY: error_message = "OpenAI API key missing."
                else: tool_instance = OpenAITool(api_key=config.OPENAI_API_KEY, model_identifier=model_identifier)
            elif provider_prefix == "anthropic" or "claude" in model_id_lower:
                if not config.ANTHROPIC_API_KEY: error_message = "Anthropic API key missing."
                else: tool_instance = AnthropicTool(api_key=config.ANTHROPIC_API_KEY, model_identifier=model_identifier)
            # Add elif for other providers
            else: error_message = f"Unsupported model identifier: {model_identifier}"; logger.error(error_message)
        except Exception as e: logger.error(f"Error instantiating LLM tool for {model_identifier}: {e}", exc_info=True); raise ValueError(f"Failed to create instance for {model_identifier}: {e}") from e
        if error_message: raise ValueError(f"Cannot create tool for '{model_identifier}': {error_message}")
        if tool_instance and tool_instance.api_key: LLMFactory._tool_cache[model_identifier] = tool_instance; logger.info(f"Created/cached LLMTool for {model_identifier}"); return tool_instance
        elif tool_instance: raise ValueError(f"Tool '{model_identifier}' missing API key.")
        else: raise ValueError(f"Failed to create instance for: {model_identifier}")

