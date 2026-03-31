"""
Report configuration loader.

Loads report configuration from YAML preset files and returns
ReportConfig objects for use with the HTML report generator.
"""

import yaml
from pathlib import Path
from typing import Optional

from reporter.html_reporter import ReportConfig


def load_preset(preset_name: str) -> ReportConfig:
    """
    Load a report configuration preset from YAML file.

    Parameters
    ----------
    preset_name : str
        Name of the preset (without .yaml extension).
        Looks for preset in reporter/presets/<preset_name>.yaml

    Returns
    -------
    ReportConfig
        Configuration object ready for use with generate_report()

    Raises
    ------
    FileNotFoundError
        If preset file doesn't exist
    ValueError
        If preset YAML is invalid
    """
    preset_path = Path(__file__).parent / "presets" / f"{preset_name}.yaml"

    if not preset_path.exists():
        raise FileNotFoundError(f"Preset not found: {preset_path}")

    try:
        with open(preset_path, "r", encoding="utf-8") as f:
            preset_data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in preset {preset_name}: {e}")

    return ReportConfig(**preset_data)


def load_preset_or_default(preset_name: Optional[str]) -> ReportConfig:
    """
    Load a preset, falling back to default if not specified.

    Parameters
    ----------
    preset_name : str or None
        Preset name to load, or None to use 'default'

    Returns
    -------
    ReportConfig
        Configuration object
    """
    if preset_name is None:
        preset_name = "default"
    return load_preset(preset_name)
