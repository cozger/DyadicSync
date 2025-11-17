"""
Configuration structures for DyadicSync experiment.

This module contains data classes and configuration structures for defining
experiment parameters, trials, questions, and timing.
"""

from .trial import Trial
from .question import Question, ScaleType
from .experiment import ExperimentConfig

__all__ = ['Trial', 'Question', 'ScaleType', 'ExperimentConfig']
