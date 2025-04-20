# orchestrator/config.py
import os
import logging
from dotenv import load_dotenv

# Determine the absolute path to the directory containing this config file
# Then, construct the path to the .env file in the same directory
_config_dir = os.path.dirname(os.path.abspath(__file__))
_dotenv_path = os.path.join(_config_dir, ".env")

# --- Basic Logging Setup (before loading config potentially fails) ---
# This allows logging warnings during config loading itself.
_default_log_level_str = "INFO"
_log_level_env = os.getenv(
    "LOG_LEVEL", _default_log_level_str
).upper()  # Check env var first
valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
if _log_level_env not in valid_log_levels:
    _log_level_env = _default_log_level_str
_numeric_log_level = getattr(logging, _log_level_env, logging.INFO)
logging.basicConfig(
    level=_numeric_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)  # Get logger for this module


# Load environment variables from .env file
if os.path.exists(_dotenv_path):
    loaded = load_dotenv(
        dotenv_path=_dotenv_path, override=True
    )  # override=True ensures .env takes precedence over system env vars
    if loaded:
        logger.info(f"Successfully loaded environment variables from: {_dotenv_path}")
    else:
        logger.warning(
            f".env file found at {_dotenv_path}, but loading might have failed (check permissions?)."
        )
else:
    logger.warning(
        f".env file not found at {_dotenv_path}. Relying solely on system environment variables."
    )

# --- LLM Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
QWEN_API_KEY = os.getenv("QWEN_API_KEY")  # Example

# --- Database Configuration ---
DB_TYPE = os.getenv("DB_TYPE", "postgresql").lower()
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Construct Database Connection Info (adapt based on library used)
DATABASE_CONNECTION_INFO = None
_db_vars_exist = all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD])
if _db_vars_exist:
    try:
        if DB_TYPE == "postgresql":
            # Example for psycopg2 connection string (keyword/value format)
            DATABASE_CONNECTION_INFO = f"dbname='{DB_NAME}' user='{DB_USER}' password='{DB_PASSWORD}' host='{DB_HOST}' port='{DB_PORT}'"
            # Example for SQLAlchemy URL:
            # DATABASE_CONNECTION_INFO = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        # Add elif for other DB types (e.g., mysql) here
        # elif DB_TYPE == "mysql":
        #     DATABASE_CONNECTION_INFO = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}" # Example
        else:
             logger.warning(f"Unsupported DB_TYPE '{DB_TYPE}' specified in config.")
    except Exception as e:
        logger.error(f"Error constructing database connection info: {e}", exc_info=True)
        DATABASE_CONNECTION_INFO = None
else:
    missing_vars = [
        var
        for var in ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
        if not locals().get(var)
    ]
    if missing_vars:  # Only warn if some vars were expected but missing
        logger.warning(
            f"Database configuration incomplete in environment. Missing: {', '.join(missing_vars)}. DATABASE_CONNECTION_INFO set to None."
        )

# --- Other Settings ---
# Reload LOG_LEVEL in case it was set in .env and loaded above
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", _default_log_level_str).upper()
if LOG_LEVEL_STR not in valid_log_levels:
    logger.warning(
        f"Invalid LOG_LEVEL '{LOG_LEVEL_STR}' found in environment. Using {_default_log_level_str}."
    )
    LOG_LEVEL = getattr(logging, _default_log_level_str)
else:
    LOG_LEVEL = getattr(logging, LOG_LEVEL_STR)
# Apply the potentially updated log level (optional, basicConfig might not update easily)
# logging.getLogger().setLevel(LOG_LEVEL) # May need more complex handler update

REPLIT_API_KEY = os.getenv("REPLIT_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# --- Prompt Configuration ---
PROMPT_DIR_NAME = os.getenv("PROMPT_DIR", "prompt_templates")
# Construct absolute path to prompt directory relative to this config file's location
PROMPT_DIR_PATH = os.path.abspath(os.path.join(_config_dir, PROMPT_DIR_NAME))

# --- Initial Validation Logging ---
if not OPENAI_API_KEY and not ANTHROPIC_API_KEY and not QWEN_API_KEY:
    logger.warning(
        "No common LLM API key found in environment variables (OpenAI, Anthropic, Qwen checked)."
    )

if (
    not DATABASE_CONNECTION_INFO and _db_vars_exist
):  # Warn only if vars were present but construction failed
    logger.error(
        "Database connection variables seem present, but constructing connection info failed. Check DB_TYPE and variable formats."
    )

if not os.path.isdir(PROMPT_DIR_PATH):
    logger.error(
        f"Prompt directory specified does not exist or is not a directory: {PROMPT_DIR_PATH}. Please create it or correct the PROMPT_DIR environment variable."
    )
else:
    logger.info(f"Using prompt directory: {PROMPT_DIR_PATH}")

# Final check log message
logger.info("Configuration loading complete.")
