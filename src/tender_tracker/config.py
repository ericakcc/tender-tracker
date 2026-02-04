"""Configuration management using YAML."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


class BudgetConfig(BaseModel):
    """Budget range filter configuration."""

    min: float = 150_000
    max: float = 3_000_000


class ScheduleConfig(BaseModel):
    """Schedule configuration for automated fetching."""

    fetch_interval: str = "0 9,14 * * 1-5"


class AppConfig(BaseModel):
    """Application configuration loaded from YAML."""

    keywords: list[str] = Field(default_factory=list)
    orgs: list[str] = Field(default_factory=list)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    procurement_types: list[str] = Field(default_factory=lambda: ["勞務"])
    ebuying_categories: list[str] = Field(default_factory=lambda: ["226"])
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)


def load_config(path: Path | None = None) -> AppConfig:
    """Load configuration from a YAML file.

    Args:
        path: Path to YAML config file. Uses default if None.

    Returns:
        Parsed application configuration.
    """
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return AppConfig()

    with config_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw:
        return AppConfig()

    return AppConfig.model_validate(raw)
