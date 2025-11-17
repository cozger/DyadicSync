"""
Marker Template Resolution

Handles template-based marker codes that encode:
- Trial numbers (100# → 1001 for trial 1)
- Participant-specific events (210# vs 220#)
- Complex encodings (300#0$ → trial + rating response)
"""

import re
from dataclasses import dataclass
from typing import Optional, Union, Dict, Any


@dataclass
class MarkerBinding:
    """
    Binding between an execution event and an LSL marker

    Represents: "When event X occurs, send marker Y (optionally filtered by participant)"
    """
    event_type: str              # e.g., "phase_start", "video_p1_end", "p1_response"
    marker_template: str         # e.g., "100#", "8888", "300#0$"
    participant: Optional[int] = None  # 1, 2, or None (both)

    def __post_init__(self):
        """HIGH PRIORITY FIX: Validate template syntax and participant on creation"""
        # Validate template syntax
        is_valid, error_msg = validate_template_syntax(self.marker_template)
        if not is_valid:
            raise ValueError(
                f"Invalid marker template '{self.marker_template}': {error_msg}\n"
                f"Valid formats:\n"
                f"  - Static integer: '8888'\n"
                f"  - Trial-indexed: '100#'\n"
                f"  - Trial + Response: '300#0$'\n"
                f"  - String template: '{{type}}_start'"
            )

        # Validate participant number
        if self.participant is not None and self.participant not in [1, 2]:
            raise ValueError(
                f"participant must be 1, 2, or None (both), got {self.participant}"
            )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'event_type': self.event_type,
            'marker_template': self.marker_template,
            'participant': self.participant
        }

    @staticmethod
    def from_dict(data: dict) -> 'MarkerBinding':
        """Create from dictionary"""
        return MarkerBinding(
            event_type=data['event_type'],
            marker_template=data['marker_template'],
            participant=data.get('participant')
        )

    def __repr__(self) -> str:
        participant_str = ""
        if self.participant:
            participant_str = f" [P{self.participant}]"
        return f"MarkerBinding({self.event_type} -> {self.marker_template}{participant_str})"


def resolve_marker_template(
    template: str,
    trial_data: Optional[Dict[str, Any]] = None,
    response_value: Optional[int] = None
) -> Union[int, str]:
    """
    Resolve a marker template to a concrete marker code (integer or string)

    Supports both integer and string templates:

    **Integer Templates (backward compatible):**
    - Static: "8888" → 8888
    - Trial-indexed: "100#" → 1001 (trial 1), 1002 (trial 2), etc.
    - Trial + Response: "300#0$" → 300107 (trial 1, rating 7)

    **String Templates (NEW):**
    - Variable substitution: "{type}_start" → "happy_start" (when type='happy')
    - Multiple variables: "{type}_trial_{trial_index}" → "happy_trial_3"
    - Any trial data column can be used: "{condition}", "{stimulus_set}", etc.

    Args:
        template: Template string (e.g., "100#", "{type}_start", "8888")
        trial_data: Dictionary of trial variables (e.g., {'trial_index': 3, 'type': 'happy'})
        response_value: Response value for rating markers (1-7), optional

    Returns:
        Resolved marker as integer or string

    Raises:
        ValueError: If template requires variables not provided in trial_data

    Examples:
        >>> # Integer templates (backward compatible)
        >>> resolve_marker_template("8888")
        8888
        >>> resolve_marker_template("100#", {'trial_index': 1})
        1001
        >>> resolve_marker_template("300#0$", {'trial_index': 2}, response_value=7)
        300207

        >>> # String templates (NEW)
        >>> resolve_marker_template("{type}_start", {'type': 'happy'})
        'happy_start'
        >>> resolve_marker_template("{type}_trial_{trial_index}", {'type': 'sad', 'trial_index': 3})
        'sad_trial_3'
        >>> resolve_marker_template("{condition}_{participant}", {'condition': 'sync', 'participant': 'p1'})
        'sync_p1'
    """
    # CRITICAL FIX: Validate trial_data type before using
    if trial_data is not None and not isinstance(trial_data, dict):
        raise TypeError(
            f"trial_data must be a dictionary, got {type(trial_data).__name__}. "
            f"Expected format: {{'trial_index': 1, 'type': 'happy', ...}}"
        )

    trial_data = trial_data or {}

    # Detect template type: string template (has {variable}) vs integer template (has # or $)
    has_curly_braces = '{' in template and '}' in template
    has_hash_or_dollar = '#' in template or '$' in template

    # STRING TEMPLATE: {variable} substitution
    if has_curly_braces:
        # Extract all {variable} placeholders
        variables_needed = re.findall(r'\{(\w+)\}', template)

        # Check if all required variables are in trial_data
        missing_vars = [v for v in variables_needed if v not in trial_data]
        if missing_vars:
            raise ValueError(
                f"Template '{template}' requires variables {missing_vars} "
                f"but they are not in trial_data. Available: {list(trial_data.keys())}"
            )

        # Substitute all {variable} with values from trial_data
        result = template
        for var in variables_needed:
            value = trial_data[var]
            result = result.replace(f'{{{var}}}', str(value))

        return result  # Return as string

    # INTEGER TEMPLATE: Legacy # and $ markers (backward compatible)
    elif has_hash_or_dollar:
        # Extract trial_index from trial_data if available
        trial_index = trial_data.get('trial_index')

        # Trial-indexed marker: 100# → 1001
        if '#' in template and '$' not in template:
            if trial_index is None:
                raise ValueError(f"Trial index required for template '{template}'")

            # Replace # with trial number
            result = template.replace('#', str(trial_index))
            return int(result)

        # Trial + Response marker: 300#0$ → 300[trial]0[response]
        if '#' in template and '$' in template:
            if trial_index is None or response_value is None:
                raise ValueError(f"Trial index and response value required for template '{template}'")

            # Replace # with trial, $ with response
            result = template.replace('#', str(trial_index))
            result = result.replace('$', str(response_value))
            return int(result)

        # Unknown template format
        raise ValueError(f"Unknown template format: '{template}'")

    # STATIC MARKER: No template markers, just a plain value
    else:
        # Try to parse as integer
        try:
            return int(template)
        except ValueError:
            # Not an integer, return as string
            return template


def format_marker_display(marker_code: Union[int, str], marker_name: Optional[str] = None) -> str:
    """
    Format marker for display in UI

    Args:
        marker_code: Marker code (integer or string)
        marker_name: Optional marker name from catalog

    Returns:
        Formatted string like "8888 - Baseline Start" or "happy_start - Happy Video Start"
    """
    if marker_name:
        return f"{marker_code} - {marker_name}"
    return str(marker_code)


def validate_template_syntax(template: str) -> tuple[bool, str]:
    """
    Validate template syntax

    Supports both integer templates (# and $) and string templates ({variable}).

    Args:
        template: Template string to validate

    Returns:
        (is_valid, error_message)

    Examples:
        >>> # Integer templates
        >>> validate_template_syntax("8888")
        (True, "")
        >>> validate_template_syntax("100#")
        (True, "")
        >>> validate_template_syntax("300#0$")
        (True, "")

        >>> # String templates
        >>> validate_template_syntax("{type}_start")
        (True, "")
        >>> validate_template_syntax("{condition}_{trial_index}")
        (True, "")
    """
    # Detect template type
    has_curly_braces = '{' in template and '}' in template
    has_hash_or_dollar = '#' in template or '$' in template

    # STRING TEMPLATE: {variable} syntax
    if has_curly_braces:
        # Check for valid variable names
        variables = re.findall(r'\{(\w+)\}', template)
        if not variables:
            return False, "String template must contain at least one {variable}"

        # Check for invalid characters outside {variables}
        # Remove all {variables} and check if remaining is valid
        temp = template
        for var in variables:
            temp = temp.replace(f'{{{var}}}', '')

        # Remaining should only contain alphanumeric, underscores, hyphens
        if temp and not re.match(r'^[\w\-]*$', temp):
            return False, "String template can only contain alphanumeric, underscores, hyphens, and {variables}"

        return True, ""

    # INTEGER TEMPLATE: # and $ syntax
    elif has_hash_or_dollar:
        # Must contain only digits, #, $
        if not re.match(r'^[\d#$]+$', template):
            return False, "Integer template must contain only digits, '#', and '$'"

        # # and $ can only appear once each
        if template.count('#') > 1:
            return False, "Template can contain at most one '#'"

        if template.count('$') > 1:
            return False, "Template can contain at most one '$'"

        # If $ is present, # must also be present (rating requires trial)
        if '$' in template and '#' not in template:
            return False, "Rating template '$' requires trial marker '#'"

        # Try to parse as valid number pattern
        try:
            # Replace placeholders with 0s to check if it's a valid number
            test_value = template.replace('#', '0').replace('$', '0')
            int(test_value)
        except ValueError:
            return False, "Template must resolve to a valid integer"

        return True, ""

    # STATIC MARKER: No template syntax
    else:
        # Can be either an integer or a plain string
        # Both are valid
        return True, ""


def get_template_description(template: str) -> str:
    """
    Get human-readable description of what a template does

    Args:
        template: Template string

    Returns:
        Description string

    Examples:
        >>> get_template_description("8888")
        "Static marker: 8888"
        >>> get_template_description("100#")
        "Trial-indexed: 1001, 1002, 1003, ..."
        >>> get_template_description("300#0$")
        "Trial + Response: 300[trial]0[rating]"
        >>> get_template_description("{type}_start")
        "String template: {type}_start (e.g., happy_start, sad_start)"
    """
    has_curly_braces = '{' in template and '}' in template
    has_hash_or_dollar = '#' in template or '$' in template

    # String template
    if has_curly_braces:
        # Extract variables
        variables = re.findall(r'\{(\w+)\}', template)
        var_list = ', '.join(variables)
        return f"String template: {template} (variables: {var_list})"

    # Integer templates
    if not has_hash_or_dollar:
        return f"Static marker: {template}"

    if '#' in template and '$' not in template:
        # Show examples
        example1 = resolve_marker_template(template, {'trial_index': 1})
        example2 = resolve_marker_template(template, {'trial_index': 2})
        example3 = resolve_marker_template(template, {'trial_index': 3})
        return f"Trial-indexed: {example1}, {example2}, {example3}, ..."

    if '#' in template and '$' in template:
        return f"Trial + Response: {template.replace('#', '[trial]').replace('$', '[rating]')}"

    return "Unknown template format"
