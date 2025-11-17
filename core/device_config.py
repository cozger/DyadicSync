"""
Device Configuration Handler
Manages saving and loading device configuration for DyadicSync experiments.

Author: DyadicSync Development Team
Date: 2025-11-15
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime


class DeviceConfigHandler:
    """
    Handles device configuration persistence.
    Follows the ConfigHandler pattern from YouQuantiPy.
    """

    DEFAULT_CONFIG = {
        'version': '1.0',
        'last_modified': None,
        'displays': {
            'control_monitor': None,  # Index of control monitor (experimenter)
            'participant_1_monitor': None,  # Index for P1 display
            'participant_2_monitor': None,  # Index for P2 display
        },
        'audio': {
            'participant_1_output': None,  # Audio device index for P1
            'participant_2_output': None,  # Audio device index for P2
            'participant_1_input': None,   # Optional: Input device for P1
            'participant_2_input': None,   # Optional: Input device for P2
        },
        'experiment': {
            'baseline_length': 240,  # Seconds
        },
        'gui': {
            'theme': 'dark',         # 'dark' or 'light'
            'left_panel_collapsed': False,
            'right_panel_collapsed': False,
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration handler.

        Args:
            config_path: Path to config file. If None, uses default location.
        """
        if config_path is None:
            # Default to project root
            project_root = Path(__file__).parent.parent
            config_path = project_root / "device_config.json"

        self.config_path = Path(config_path)
        self.config = self.load()

    def load(self) -> Dict[str, Any]:
        """
        Load configuration from file.
        If file doesn't exist, creates default config.

        Returns:
            Configuration dictionary
        """
        if not self.config_path.exists():
            print(f"Config file not found at {self.config_path}, creating default...")
            config = self.DEFAULT_CONFIG.copy()
            self.save(config)
            return config

        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)

            # Merge with defaults to ensure all keys exist
            config = self._merge_with_defaults(config)

            return config

        except json.JSONDecodeError as e:
            print(f"Error parsing config file: {e}")
            print("Using default configuration")
            return self.DEFAULT_CONFIG.copy()

        except Exception as e:
            print(f"Error loading config: {e}")
            return self.DEFAULT_CONFIG.copy()

    def save(self, config: Optional[Dict[str, Any]] = None):
        """
        Save configuration to file.

        Args:
            config: Configuration to save. If None, saves current config.
        """
        if config is None:
            config = self.config

        # Update timestamp
        config['last_modified'] = datetime.now().isoformat()

        try:
            # Create directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)

            print(f"Configuration saved to {self.config_path}")

        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key_path: Dot-separated path to value (e.g., 'displays.participant_1_monitor')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set(self, key_path: str, value: Any, save: bool = True):
        """
        Set configuration value using dot notation.

        Args:
            key_path: Dot-separated path to value
            value: Value to set
            save: Whether to save after setting
        """
        keys = key_path.split('.')
        config = self.config

        # Navigate to parent of target key
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        # Set the value
        config[keys[-1]] = value

        if save:
            self.save()

    def update(self, updates: Dict[str, Any], save: bool = True):
        """
        Update multiple configuration values.

        Args:
            updates: Dictionary of key_path: value pairs
            save: Whether to save after updating
        """
        for key_path, value in updates.items():
            self.set(key_path, value, save=False)

        if save:
            self.save()

    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge loaded config with defaults to ensure all keys exist.

        Args:
            config: Loaded configuration

        Returns:
            Merged configuration
        """
        def merge_dict(base: dict, overlay: dict) -> dict:
            """Recursively merge overlay into base"""
            result = base.copy()
            for key, value in overlay.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dict(result[key], value)
                else:
                    result[key] = value
            return result

        return merge_dict(self.DEFAULT_CONFIG.copy(), config)

    def validate_display_config(self) -> tuple[bool, str]:
        """
        Validate that display configuration is complete and valid.

        Returns:
            Tuple of (valid: bool, message: str)
        """
        control = self.get('displays.control_monitor')
        p1 = self.get('displays.participant_1_monitor')
        p2 = self.get('displays.participant_2_monitor')

        if control is None:
            return False, "Control monitor not configured"
        if p1 is None:
            return False, "Participant 1 monitor not configured"
        if p2 is None:
            return False, "Participant 2 monitor not configured"

        # Check for conflicts
        if p1 == p2:
            return False, "Participant monitors cannot be the same"

        # Note: Control monitor CAN be same as one participant monitor for testing

        return True, "Display configuration valid"

    def validate_audio_config(self, require_input: bool = False) -> tuple[bool, str]:
        """
        Validate that audio configuration is complete and valid.

        Args:
            require_input: Whether input devices are required

        Returns:
            Tuple of (valid: bool, message: str)
        """
        p1_output = self.get('audio.participant_1_output')
        p2_output = self.get('audio.participant_2_output')

        if p1_output is None:
            return False, "Participant 1 audio output not configured"
        if p2_output is None:
            return False, "Participant 2 audio output not configured"

        if require_input:
            p1_input = self.get('audio.participant_1_input')
            p2_input = self.get('audio.participant_2_input')

            if p1_input is None:
                return False, "Participant 1 audio input not configured"
            if p2_input is None:
                return False, "Participant 2 audio input not configured"

        return True, "Audio configuration valid"

    def is_ready_for_experiment(self) -> tuple[bool, list[str]]:
        """
        Check if configuration is complete for running experiment.

        Returns:
            Tuple of (ready: bool, issues: list[str])
        """
        issues = []

        # Check displays
        valid, msg = self.validate_display_config()
        if not valid:
            issues.append(f"Display: {msg}")

        # Check audio
        valid, msg = self.validate_audio_config(require_input=False)
        if not valid:
            issues.append(f"Audio: {msg}")

        return (len(issues) == 0, issues)

    def export_for_experiment(self) -> Dict[str, Any]:
        """
        Export configuration in format suitable for WithBaseline.py.

        Returns:
            Dictionary with experiment-ready configuration
        """
        return {
            'displays': {
                'control': self.get('displays.control_monitor'),
                'participant_1': self.get('displays.participant_1_monitor'),
                'participant_2': self.get('displays.participant_2_monitor'),
            },
            'audio': {
                'device_1_index': self.get('audio.participant_1_output'),
                'device_2_index': self.get('audio.participant_2_output'),
            },
            'experiment': {
                'baseline_length': self.get('experiment.baseline_length', 240),
            }
        }

    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self.config = self.DEFAULT_CONFIG.copy()
        self.save()

    def __str__(self):
        """String representation of config"""
        return json.dumps(self.config, indent=2)


def main():
    """Test the configuration handler"""
    config = DeviceConfigHandler()

    print("Current configuration:")
    print(config)

    # Test setting values
    print("\nSetting test values...")
    config.set('displays.participant_1_monitor', 1)
    config.set('displays.participant_2_monitor', 2)
    config.set('audio.participant_1_output', 5)
    config.set('audio.participant_2_output', 7)

    # Test validation
    print("\nValidating display config...")
    valid, msg = config.validate_display_config()
    print(f"  Valid: {valid}, Message: {msg}")

    print("\nValidating audio config...")
    valid, msg = config.validate_audio_config()
    print(f"  Valid: {valid}, Message: {msg}")

    # Test export
    print("\nExported for experiment:")
    print(json.dumps(config.export_for_experiment(), indent=2))


if __name__ == "__main__":
    main()
