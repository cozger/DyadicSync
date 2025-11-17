"""
Constraint classes for trial list randomization.

Provides various constraint types to control trial ordering during randomization.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from collections import Counter


class Constraint(ABC):
    """
    Abstract base class for trial ordering constraints.

    Constraints are used during randomization to ensure trial lists
    meet specific ordering requirements (e.g., no more than 2 consecutive
    trials of the same type).
    """

    @abstractmethod
    def check(self, trials: List['Trial']) -> bool:
        """
        Check if the trial list satisfies this constraint.

        Args:
            trials: List of Trial objects in the proposed order

        Returns:
            True if constraint is satisfied, False otherwise
        """
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize constraint to dictionary."""
        pass

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Constraint':
        """
        Deserialize constraint from dictionary.

        Args:
            data: Dictionary with 'type' key and type-specific parameters

        Returns:
            Constraint instance
        """
        constraint_type = data.get('type')

        if constraint_type == 'max_consecutive':
            return MaxConsecutiveConstraint(
                attribute=data['attribute'],
                value=data.get('value'),
                limit=data['limit']
            )
        elif constraint_type == 'balance':
            return BalanceConstraint(
                attribute=data['attribute'],
                values=data.get('values')
            )
        elif constraint_type == 'no_repeat':
            return NoRepeatConstraint(
                attribute=data['attribute'],
                within_trials=data['within_trials']
            )
        else:
            raise ValueError(f"Unknown constraint type: {constraint_type}")


class MaxConsecutiveConstraint(Constraint):
    """
    Constraint that limits consecutive trials with the same attribute value.

    Example:
        # No more than 2 consecutive "happy" emotion trials
        MaxConsecutiveConstraint(attribute='emotion', value='happy', limit=2)

        # No more than 3 consecutive trials with any same emotion
        MaxConsecutiveConstraint(attribute='emotion', limit=3)
    """

    def __init__(self, attribute: str, value: Optional[Any] = None, limit: int = 1):
        """
        Initialize max consecutive constraint.

        Args:
            attribute: Trial data attribute to check (e.g., 'emotion', 'category')
            value: Specific value to check (None = check any value)
            limit: Maximum consecutive trials allowed
        """
        self.attribute = attribute
        self.value = value
        self.limit = limit

    def check(self, trials: List['Trial']) -> bool:
        """
        Check if no more than `limit` consecutive trials have the same attribute value.

        Args:
            trials: List of Trial objects

        Returns:
            True if constraint satisfied, False otherwise
        """
        if not trials:
            return True

        consecutive_count = 1
        prev_value = trials[0].data.get(self.attribute)

        for i in range(1, len(trials)):
            current_value = trials[i].data.get(self.attribute)

            # Check if we should count this trial
            if self.value is None:
                # Check any value - count if same as previous
                if current_value == prev_value:
                    consecutive_count += 1
                else:
                    consecutive_count = 1
            else:
                # Check specific value - count only if matches target value
                if current_value == self.value:
                    if prev_value == self.value:
                        consecutive_count += 1
                    else:
                        consecutive_count = 1
                else:
                    consecutive_count = 0  # Reset if not target value

            # Check if limit exceeded
            if consecutive_count > self.limit:
                return False

            prev_value = current_value

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'type': 'max_consecutive',
            'attribute': self.attribute,
            'value': self.value,
            'limit': self.limit
        }

    def __repr__(self) -> str:
        if self.value is None:
            return f"MaxConsecutive({self.attribute}, limit={self.limit})"
        return f"MaxConsecutive({self.attribute}={self.value}, limit={self.limit})"


class BalanceConstraint(Constraint):
    """
    Constraint that ensures equal counts of different attribute values.

    Example:
        # Equal number of 'happy', 'sad', 'neutral' trials
        BalanceConstraint(attribute='emotion', values=['happy', 'sad', 'neutral'])

        # Equal number of all emotion types (auto-detect values)
        BalanceConstraint(attribute='emotion')
    """

    def __init__(self, attribute: str, values: Optional[List[Any]] = None):
        """
        Initialize balance constraint.

        Args:
            attribute: Trial data attribute to check
            values: List of values to balance (None = auto-detect from trials)
        """
        self.attribute = attribute
        self.values = values

    def check(self, trials: List['Trial']) -> bool:
        """
        Check if all attribute values appear with equal frequency.

        Args:
            trials: List of Trial objects

        Returns:
            True if constraint satisfied, False otherwise
        """
        if not trials:
            return True

        # Count occurrences of each value
        counts = Counter(trial.data.get(self.attribute) for trial in trials)

        # If values specified, check only those
        if self.values is not None:
            target_values = set(self.values)
            counts = {k: v for k, v in counts.items() if k in target_values}

        # Check if all counts are equal
        count_values = list(counts.values())
        if not count_values:
            return True

        return len(set(count_values)) == 1  # All counts same = balanced

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'type': 'balance',
            'attribute': self.attribute,
            'values': self.values
        }

    def __repr__(self) -> str:
        if self.values is None:
            return f"Balance({self.attribute})"
        return f"Balance({self.attribute}, values={self.values})"


class NoRepeatConstraint(Constraint):
    """
    Constraint that prevents the same value from repeating within N trials.

    Example:
        # Same video1 can't appear within 3 trials
        NoRepeatConstraint(attribute='video1', within_trials=3)
    """

    def __init__(self, attribute: str, within_trials: int):
        """
        Initialize no-repeat constraint.

        Args:
            attribute: Trial data attribute to check
            within_trials: Minimum trials between repeats
        """
        self.attribute = attribute
        self.within_trials = within_trials

    def check(self, trials: List['Trial']) -> bool:
        """
        Check if same value doesn't repeat within specified window.

        Args:
            trials: List of Trial objects

        Returns:
            True if constraint satisfied, False otherwise
        """
        if not trials:
            return True

        for i in range(len(trials)):
            current_value = trials[i].data.get(self.attribute)

            # Check window of trials after this one
            window_end = min(i + self.within_trials, len(trials))
            for j in range(i + 1, window_end):
                if trials[j].data.get(self.attribute) == current_value:
                    return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'type': 'no_repeat',
            'attribute': self.attribute,
            'within_trials': self.within_trials
        }

    def __repr__(self) -> str:
        return f"NoRepeat({self.attribute}, within={self.within_trials})"


def create_constraint(constraint_type: str, **kwargs) -> Constraint:
    """
    Factory function to create constraints.

    Args:
        constraint_type: Type of constraint ('max_consecutive', 'balance', 'no_repeat')
        **kwargs: Type-specific parameters

    Returns:
        Constraint instance

    Examples:
        >>> create_constraint('max_consecutive', attribute='emotion', value='happy', limit=2)
        >>> create_constraint('balance', attribute='emotion')
        >>> create_constraint('no_repeat', attribute='video1', within_trials=3)
    """
    if constraint_type == 'max_consecutive':
        return MaxConsecutiveConstraint(**kwargs)
    elif constraint_type == 'balance':
        return BalanceConstraint(**kwargs)
    elif constraint_type == 'no_repeat':
        return NoRepeatConstraint(**kwargs)
    else:
        raise ValueError(f"Unknown constraint type: {constraint_type}")
