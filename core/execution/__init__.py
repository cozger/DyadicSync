"""
Execution module for DyadicSync Framework.

This module contains the core execution architecture:
- Phase: Base class for all phase types
- Procedure: Manages sequence of phases
- Block: Manages procedure + trial list
- Timeline: Manages sequence of blocks
"""

from .phase import Phase
from .procedure import Procedure
from .block import Block
from .timeline import Timeline

__all__ = [
    'Phase',
    'Procedure',
    'Block',
    'Timeline',
]
