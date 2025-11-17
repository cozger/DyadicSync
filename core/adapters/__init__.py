"""
Adapter module for converting between different configuration formats.

This module provides bidirectional conversion between:
- ExperimentConfig (GUI format) - flat, trial-based configuration
- Timeline (execution format) - hierarchical, block-based execution structure
"""

from .experiment_config_adapter import ExperimentConfigAdapter

__all__ = ['ExperimentConfigAdapter']
