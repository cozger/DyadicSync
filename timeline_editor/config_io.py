"""
Configuration file I/O for saving and loading experiment configurations.
"""

import json
import os
from pathlib import Path
from typing import Optional
import pandas as pd

import sys
sys.path.append(str(Path(__file__).parent.parent))

from config.experiment import ExperimentConfig


def save_config(config: ExperimentConfig, filepath: str) -> bool:
    """
    Save experiment configuration to JSON file.

    Args:
        config: ExperimentConfig object to save
        filepath: Path where JSON file should be saved

    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert config to dictionary
        config_dict = config.to_dict()

        # Ensure directory exists
        directory = os.path.dirname(filepath)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        # Write JSON with pretty formatting
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)

        print(f"Configuration saved successfully to {filepath}")
        return True

    except Exception as e:
        print(f"Error saving configuration: {str(e)}")
        return False


def load_config(filepath: str) -> Optional[ExperimentConfig]:
    """
    Load experiment configuration from JSON file.

    Args:
        filepath: Path to JSON configuration file

    Returns:
        ExperimentConfig object or None if loading fails
    """
    try:
        if not os.path.exists(filepath):
            print(f"Configuration file not found: {filepath}")
            return None

        with open(filepath, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)

        config = ExperimentConfig.from_dict(config_dict)

        print(f"Configuration loaded successfully from {filepath}")
        return config

    except Exception as e:
        print(f"Error loading configuration: {str(e)}")
        return None


def load_from_csv(csv_path: str, **config_kwargs) -> Optional[ExperimentConfig]:
    """
    Load experiment configuration from legacy CSV file format.

    Args:
        csv_path: Path to CSV file with VideoPath1 and VideoPath2 columns
        **config_kwargs: Additional parameters for ExperimentConfig

    Returns:
        ExperimentConfig object or None if loading fails
    """
    try:
        config = ExperimentConfig.create_from_csv(csv_path, **config_kwargs)
        print(f"Loaded {len(config.trials)} trials from CSV: {csv_path}")
        return config

    except Exception as e:
        print(f"Error loading CSV file: {str(e)}")
        return None


def export_to_csv(config: ExperimentConfig, csv_path: str) -> bool:
    """
    Export trial video paths to CSV file (for backward compatibility).

    Args:
        config: ExperimentConfig to export
        csv_path: Path where CSV should be saved

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create DataFrame from trials
        data = {
            'VideoPath1': [t.video_path_1 for t in config.trials],
            'VideoPath2': [t.video_path_2 for t in config.trials]
        }

        df = pd.DataFrame(data)

        # Save to CSV
        df.to_csv(csv_path, index=False)

        print(f"Exported {len(config.trials)} trials to CSV: {csv_path}")
        return True

    except Exception as e:
        print(f"Error exporting to CSV: {str(e)}")
        return False


def create_default_config(name: str = "New Experiment") -> ExperimentConfig:
    """
    Create a new experiment configuration with sensible defaults.

    Args:
        name: Name for the new experiment

    Returns:
        ExperimentConfig with default settings and no trials
    """
    config = ExperimentConfig(name=name)
    return config


def validate_config_file(filepath: str) -> tuple[bool, list[str]]:
    """
    Validate a configuration file without fully loading it.

    Args:
        filepath: Path to JSON configuration file

    Returns:
        Tuple of (valid: bool, errors: list[str])
    """
    errors = []

    try:
        if not os.path.exists(filepath):
            errors.append(f"File not found: {filepath}")
            return False, errors

        with open(filepath, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)

        # Check required top-level keys
        required_keys = ['experiment_info', 'global_defaults', 'trials']
        for key in required_keys:
            if key not in config_dict:
                errors.append(f"Missing required key: {key}")

        # Try to create config object (will validate structure)
        if not errors:
            config = ExperimentConfig.from_dict(config_dict)
            valid, validation_errors = config.validate()
            errors.extend(validation_errors)

        return len(errors) == 0, errors

    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON format: {str(e)}")
        return False, errors
    except Exception as e:
        errors.append(f"Validation error: {str(e)}")
        return False, errors
