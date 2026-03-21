import os
import logging

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("klog")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4jpassword")
JWT_SECRET = os.getenv("JWT_SECRET", "kg_log_secret_change_me_in_production")
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

_DEFAULT_SECRETS = {"kg_log_secret_change_me_in_production", "change_me_in_production"}
DEV_MODE = os.getenv("DEV_MODE", "").lower() in ("1", "true", "yes")


def check_default_secret():
    if JWT_SECRET in _DEFAULT_SECRETS:
        if DEV_MODE:
            logger.warning(
                "JWT_SECRET is set to a default value. "
                "This is allowed in DEV_MODE but must be changed for production."
            )
        else:
            raise RuntimeError(
                "JWT_SECRET is set to a default value. "
                "Set a strong, unique JWT_SECRET environment variable, "
                "or set DEV_MODE=true to bypass this check for local development."
            )
