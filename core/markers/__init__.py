"""
LSL Event Marker Management System

This module provides infrastructure for managing LSL event markers with:
- Catalog-based marker definitions (integer and string markers)
- Template resolution for trial-indexed markers
- Marker logging and export
- Validation and documentation export
"""

from .catalog import MarkerDefinition, MarkerCatalog
from .templates import resolve_marker_template, MarkerBinding
from .logger import MarkerLogger, MarkerEvent

__all__ = [
    'MarkerDefinition',
    'MarkerCatalog',
    'MarkerBinding',
    'resolve_marker_template',
    'MarkerLogger',
    'MarkerEvent',
]
