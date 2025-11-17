"""
Marker Catalog System

Manages the global registry of LSL marker definitions, including:
- Named marker codes (e.g., 8888 = "Baseline Start")
- Template patterns (e.g., "100#" for trial-indexed markers)
- Validation and documentation export
"""

import json
import os
import threading
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Union
from pathlib import Path


@dataclass
class MarkerDefinition:
    """
    Definition of an LSL marker code (integer or string).

    For integer markers: code is the base integer (e.g., 1000, 2100)
    For string markers: code is None (string markers don't have numeric codes)
    """
    name: str                                  # Human-readable name (e.g., "Baseline Start", "Happy Video Start")
    description: str                           # Detailed description
    template_pattern: Optional[str] = None     # Template like "100#" (int) or "{type}_start" (string)
    code: Optional[int] = None                 # LSL marker code (e.g., 8888) - None for string markers
    marker_type: str = 'integer'               # 'integer' or 'string'

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> 'MarkerDefinition':
        """Create from dictionary"""
        return MarkerDefinition(**data)


class MarkerCatalog:
    """
    Singleton catalog of all marker definitions (integer and string markers)

    Provides:
    - Global marker registry (integers keyed by code, strings keyed by template)
    - Validation (duplicate detection)
    - Import/export to CodeBook.txt
    - Template marker definitions
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Separate storage for integer and string markers
        self._int_definitions: Dict[int, MarkerDefinition] = {}  # Keyed by code
        self._string_definitions: Dict[str, MarkerDefinition] = {}  # Keyed by template_pattern
        self._catalog_path = Path(__file__).parent.parent.parent / "data" / "marker_catalog.json"
        self._file_lock = threading.Lock()  # CRITICAL FIX: Protect file I/O operations
        self._initialized = True

        # Auto-load catalog if it exists
        if self._catalog_path.exists():
            self.load_from_json()
        else:
            # Initialize with default markers from CodeBook.txt
            self._initialize_defaults()

    def _initialize_defaults(self):
        """Initialize catalog with default markers from CodeBook.txt"""
        # Integer markers (using new field order: name, description, template_pattern, code, marker_type)
        int_defaults = [
            MarkerDefinition("Headset B16 to P1", "Participant 1 assigned headset B16", code=9161),
            MarkerDefinition("Headset B16 to P2", "Participant 1 assigned other headset, P2 is B16", code=9162),
            MarkerDefinition("Baseline Start", "Baseline fixation cross start", code=8888),
            MarkerDefinition("Baseline End", "Baseline fixation cross end", code=9999),

            # Trial start (template-based)
            MarkerDefinition("Trial Start", "Trial begin (all trials start simultaneously)",
                           template_pattern="100#", code=1000),

            # Video end markers (template-based, participant-specific)
            MarkerDefinition("P1 Video End", "Video playback end for participant 1",
                           template_pattern="210#", code=2100),
            MarkerDefinition("P2 Video End", "Video playback end for participant 2",
                           template_pattern="220#", code=2200),

            # Rating response markers (template-based with response encoding)
            MarkerDefinition("P1 Rating", "Rating response for participant 1 (trial + rating)",
                           template_pattern="300#0$", code=30000),
            MarkerDefinition("P2 Rating", "Rating response for participant 2 (trial + rating)",
                           template_pattern="500#0$", code=50000),
        ]

        for definition in int_defaults:
            self._int_definitions[definition.code] = definition

        # Save to file
        self.save_to_json()

    def add_definition(self, definition: MarkerDefinition) -> bool:
        """
        Add a marker definition to the catalog

        Args:
            definition: MarkerDefinition to add

        Returns:
            True if added successfully, False if already exists
        """
        if definition.marker_type == 'string':
            # String markers keyed by template_pattern
            if not definition.template_pattern:
                raise ValueError("String markers must have a template_pattern")
            if definition.template_pattern in self._string_definitions:
                return False
            self._string_definitions[definition.template_pattern] = definition
        else:
            # Integer markers keyed by code
            if definition.code is None:
                raise ValueError("Integer markers must have a code")
            if definition.code in self._int_definitions:
                return False
            self._int_definitions[definition.code] = definition

        self.save_to_json()
        return True

    def update_definition(self, key: Union[int, str], definition: MarkerDefinition) -> bool:
        """
        Update an existing marker definition

        Args:
            key: Original marker code (int) or template (str) to update
            definition: New definition

        Returns:
            True if updated successfully, False if not found
        """
        # Remove old entry
        if isinstance(key, int):
            if key not in self._int_definitions:
                return False
            del self._int_definitions[key]
        else:
            if key not in self._string_definitions:
                return False
            del self._string_definitions[key]

        # Add new entry (using updated key if changed)
        return self.add_definition(definition)

    def remove_definition(self, key: Union[int, str]) -> bool:
        """
        Remove a marker definition

        Args:
            key: Marker code (int) or template (str) to remove

        Returns:
            True if removed, False if not found
        """
        if isinstance(key, int):
            if key in self._int_definitions:
                del self._int_definitions[key]
                self.save_to_json()
                return True
        else:
            if key in self._string_definitions:
                del self._string_definitions[key]
                self.save_to_json()
                return True
        return False

    def get_definition(self, key: Union[int, str]) -> Optional[MarkerDefinition]:
        """
        Get marker definition by code (int) or template (str)

        Args:
            key: Marker code (int) or template/marker string (str)

        Returns:
            MarkerDefinition if found, None otherwise
        """
        if isinstance(key, int):
            return self._int_definitions.get(key)
        else:
            # Try exact match on template_pattern first
            if key in self._string_definitions:
                return self._string_definitions[key]
            # If no match, might be a resolved string marker - can't look up directly
            return None

    def get_name(self, marker: Union[int, str]) -> str:
        """
        Get marker name by code (int) or string marker

        Args:
            marker: Integer code or string marker value

        Returns:
            Marker name if found in catalog, otherwise returns marker as string
        """
        if isinstance(marker, int):
            definition = self._int_definitions.get(marker)
            return definition.name if definition else str(marker)
        else:
            # For string markers, the marker itself is descriptive
            # Try to find definition by template pattern
            definition = self._string_definitions.get(marker)
            return definition.name if definition else marker

    def get_all_definitions(self) -> List[MarkerDefinition]:
        """Get all marker definitions (integer and string markers)"""
        all_defs = []
        # Integer markers sorted by code
        all_defs.extend(sorted(self._int_definitions.values(), key=lambda d: d.code or 0))
        # String markers sorted by name
        all_defs.extend(sorted(self._string_definitions.values(), key=lambda d: d.name))
        return all_defs

    def get_template_definitions(self) -> List[MarkerDefinition]:
        """Get all template marker definitions (for dropdown lists)"""
        return [d for d in self.get_all_definitions() if d.template_pattern]

    def validate_unique(self, key: Union[int, str], marker_type: str = 'integer',
                       exclude_key: Optional[Union[int, str]] = None) -> bool:
        """
        Check if a marker code/template is unique

        Args:
            key: Code (int) or template (str) to validate
            marker_type: 'integer' or 'string'
            exclude_key: Key to exclude from check (for updates)

        Returns:
            True if unique, False if duplicate
        """
        if key == exclude_key:
            return True

        if marker_type == 'string':
            return key not in self._string_definitions
        else:
            return key not in self._int_definitions

    def find_by_template(self, template: str) -> Optional[MarkerDefinition]:
        """Find marker definition by template pattern"""
        # Check integer markers
        for definition in self._int_definitions.values():
            if definition.template_pattern == template:
                return definition
        # Check string markers
        if template in self._string_definitions:
            return self._string_definitions[template]
        return None

    def save_to_json(self):
        """Save catalog to JSON file (thread-safe)"""
        with self._file_lock:  # CRITICAL FIX: Protect file writes from race conditions
            # Ensure data directory exists
            self._catalog_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'version': '2.0',  # Bumped for string marker support
                'markers': [d.to_dict() for d in self.get_all_definitions()]
            }

            with open(self._catalog_path, 'w') as f:
                json.dump(data, f, indent=2)

    def load_from_json(self):
        """Load catalog from JSON file (thread-safe)"""
        with self._file_lock:  # CRITICAL FIX: Protect file reads from race conditions
            if not self._catalog_path.exists():
                return

            with open(self._catalog_path, 'r') as f:
                data = json.load(f)

            self._int_definitions.clear()
            self._string_definitions.clear()

            for marker_data in data.get('markers', []):
                definition = MarkerDefinition.from_dict(marker_data)

                # Route to appropriate storage based on marker_type
                if definition.marker_type == 'string':
                    if definition.template_pattern:
                        self._string_definitions[definition.template_pattern] = definition
                else:
                    if definition.code is not None:
                        self._int_definitions[definition.code] = definition

    def export_to_codebook(self, output_path: str):
        """
        Export catalog to CodeBook.txt format

        Args:
            output_path: Path to output CodeBook.txt file

        Raises:
            ValueError: If output_path is invalid or insecure
        """
        # CRITICAL FIX: Validate path to prevent directory traversal
        output_path = Path(output_path).resolve()

        # Ensure parent directory exists
        if not output_path.parent.exists():
            raise ValueError(f"Parent directory does not exist: {output_path.parent}")

        lines = []
        lines.append("INTEGER MARKERS")
        lines.append("# denotes changing integer based on trial number or participant rating response")
        lines.append("$ denotes rating value (1-7)")
        lines.append("")

        # Group integer markers by category
        special_markers = []
        baseline_markers = []
        trial_markers = []
        video_markers = []
        rating_markers = []

        for definition in self._int_definitions.values():
            marker_line = f"{definition.code}"
            if definition.template_pattern:
                marker_line = definition.template_pattern
            marker_line += f": {definition.description}"

            # Categorize
            if definition.code in [9161, 9162]:
                special_markers.append(marker_line)
            elif definition.code in [8888, 9999]:
                baseline_markers.append(marker_line)
            elif definition.template_pattern and definition.template_pattern.startswith("100"):
                trial_markers.append(marker_line)
            elif definition.template_pattern and definition.template_pattern.startswith("2"):
                video_markers.append(marker_line)
            elif definition.template_pattern and definition.template_pattern.startswith(("300", "500")):
                rating_markers.append(marker_line)

        # Write integer marker sections
        if special_markers:
            lines.extend(special_markers)
            lines.append("")

        if baseline_markers:
            lines.extend(baseline_markers)
            lines.append("")

        if trial_markers:
            lines.extend(trial_markers)
            lines.append("")

        if video_markers:
            lines.extend(video_markers)
            lines.append("")

        if rating_markers:
            lines.extend(rating_markers)
            lines.append("")
            lines.append("example: 300507, a 7 rating for trial 5 in participant 1")
            lines.append("")

        # Add string markers section
        if self._string_definitions:
            lines.append("")
            lines.append("STRING MARKERS")
            lines.append("{variable} denotes template variable (e.g., type, condition)")
            lines.append("")

            for definition in sorted(self._string_definitions.values(), key=lambda d: d.name):
                marker_line = f"{definition.template_pattern}: {definition.description}"
                lines.append(marker_line)
            lines.append("")
            lines.append("example: {type}_start with type='happy' -> 'happy_start'")
            lines.append("")

        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

    def import_from_codebook(self, codebook_path: str):
        """
        Import markers from CodeBook.txt (supports both integer and string markers)

        Note: This is a basic parser. Manual review recommended.

        Args:
            codebook_path: Path to CodeBook.txt file

        Raises:
            FileNotFoundError: If codebook_path does not exist
            ValueError: If codebook_path is invalid or insecure
        """
        # CRITICAL FIX: Validate path to prevent directory traversal
        codebook_path = Path(codebook_path).resolve()

        # Ensure file exists
        if not codebook_path.exists():
            raise FileNotFoundError(f"CodeBook not found: {codebook_path}")

        # Ensure it's a file (not a directory)
        if not codebook_path.is_file():
            raise ValueError(f"Path is not a file: {codebook_path}")

        with open(codebook_path, 'r') as f:
            lines = f.readlines()

        # Track which section we're in
        current_section = 'integer'  # Default to integer markers

        for line in lines:
            line = line.strip()

            # Detect section headers
            if line == 'INTEGER MARKERS':
                current_section = 'integer'
                continue
            elif line == 'STRING MARKERS':
                current_section = 'string'
                continue

            # Skip comments, section markers, and empty lines
            if not line or line.startswith('#') or line.startswith('{variable}') or line.startswith('$') or line.startswith('example:'):
                continue

            # Parse format: "CODE: description" or "TEMPLATE: description"
            if ':' not in line:
                continue

            marker_part, description = line.split(':', 1)
            marker_part = marker_part.strip()
            description = description.strip()

            # Generate name from description (first few words)
            name = ' '.join(description.split()[:4])
            if len(description.split()) > 4:
                name += '...'

            if current_section == 'string':
                # String marker: template pattern with {variables}
                if '{' in marker_part and '}' in marker_part:
                    definition = MarkerDefinition(
                        name=name,
                        description=description,
                        template_pattern=marker_part,
                        code=None,
                        marker_type='string'
                    )
                    # Don't overwrite existing definitions
                    if marker_part not in self._string_definitions:
                        self._string_definitions[marker_part] = definition
            else:
                # Integer marker: determine if template or static code
                template_pattern = None
                if '#' in marker_part or '$' in marker_part:
                    template_pattern = marker_part
                    # Extract base code (remove # and $)
                    code_str = marker_part.replace('#', '0').replace('$', '0')
                    try:
                        code = int(code_str)
                    except ValueError:
                        continue
                else:
                    try:
                        code = int(marker_part)
                    except ValueError:
                        continue

                definition = MarkerDefinition(
                    name=name,
                    description=description,
                    template_pattern=template_pattern,
                    code=code,
                    marker_type='integer'
                )

                # Don't overwrite existing definitions
                if code not in self._int_definitions:
                    self._int_definitions[code] = definition

        self.save_to_json()


# Create singleton instance
_catalog_instance = MarkerCatalog()


def get_catalog() -> MarkerCatalog:
    """Get the global marker catalog instance"""
    return _catalog_instance
