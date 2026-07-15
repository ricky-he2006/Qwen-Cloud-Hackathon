"""
Configuration for the Research Society agent system.
Supports OpenAI-compatible APIs (Qwen Cloud / DashScope, Ollama, etc.).
"""

import os
import warnings

from dotenv import load_dotenv

load_dotenv()


def _resolve_api_key() -> str:
    key = (
        os.getenv("API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
        or "not-needed"
    ).strip()
    if key.startswith("sk-sp-"):
        warnings.warn(
            "Token Plan keys (sk-sp-...) do not work with DashScope compatible-mode "
            "or backend scripts. Use a pay-as-you-go key (sk-...).",
            UserWarning,
            stacklevel=2,
        )
    return key


class Settings:
    """Application settings loaded from environment variables."""

    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:11434/v1")
    API_KEY: str = _resolve_api_key()
    MODEL_NAME: str = os.getenv("MODEL_NAME", "qwen3.7-max")

    MAX_ROUNDS: int = int(os.getenv("MAX_ROUNDS", "5"))
    CONSENSUS_THRESHOLD: float = float(
        os.getenv("CONSENSUS_THRESHOLD", os.getenv("MIN_CONSENSUS_MAJORITY", "0.8"))
    )
    MIN_CONSENSUS_MAJORITY: float = CONSENSUS_THRESHOLD

    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "120"))

    AGENT_COUNT: int = 4
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()


def get_model_path() -> str:
    return settings.MODEL_NAME


def has_cloud_api_key() -> bool:
    key = settings.API_KEY.strip()
    if not key or key in ("not-needed", "sk-your-dashscope-api-key"):
        return False
    if key.startswith("sk-your") or "PASTE" in key.upper() or "YOUR-KEY" in key.upper():
        return False
    if key.startswith("sk-sp-"):
        return False
    return key.startswith("sk-")


def is_using_dashscope() -> bool:
    base = settings.API_BASE_URL.lower()
    return "dashscope" in base or "aliyuncs.com" in base or "maas.aliyuncs.com" in base


def is_qwen_compatible() -> bool:
    return (
        "qwen" in settings.MODEL_NAME.lower()
        or "localhost" in settings.API_BASE_URL
        or is_using_dashscope()
    )
