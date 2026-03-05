"""
SelectionConfig class for DyadicSync Framework.

Configuration for variant selection in branch blocks.
"""

from typing import Dict, List, Optional, Any
import random


class SelectionConfig:
    """
    Configuration for variant selection in branch blocks.

    Handles:
    - Selection method (sequential, random, balanced)
    - Per-variant weights for distribution
    - Pre-computed scheduling for deterministic execution
    """

    # Valid selection methods
    METHODS = ['sequential', 'random', 'balanced']

    def __init__(self):
        """Initialize selection configuration with defaults."""
        self.method: str = 'balanced'  # 'sequential', 'random', 'balanced'
        self.weights: Dict[str, float] = {}  # variant_name -> weight (default 1.0)

    def get_weight(self, variant_name: str) -> float:
        """
        Get weight for a variant.

        Args:
            variant_name: Name of the variant

        Returns:
            Weight value (default 1.0 if not specified)
        """
        return self.weights.get(variant_name, 1.0)

    def set_weight(self, variant_name: str, weight: float):
        """
        Set weight for a variant.

        Args:
            variant_name: Name of the variant
            weight: Weight value (must be > 0)
        """
        if weight <= 0:
            raise ValueError(f"Weight must be positive, got {weight}")
        self.weights[variant_name] = weight

    def generate_schedule(self, variant_names: List[str], total_runs: int,
                          seed: Optional[int] = None) -> List[int]:
        """
        Pre-compute run schedule.

        Generates a list of variant indices determining which variant
        executes for each run.

        Args:
            variant_names: List of variant names in order
            total_runs: Total number of runs to schedule
            seed: Random seed for reproducibility (None = random)

        Returns:
            List of variant indices, one per run. E.g., [0, 2, 1, 0, 2, 1, ...]
        """
        if not variant_names:
            return []

        if total_runs <= 0:
            return []

        n_variants = len(variant_names)

        if self.method == 'sequential':
            # Cycle through variants in order: 0, 1, 2, 0, 1, 2, ...
            return [i % n_variants for i in range(total_runs)]

        elif self.method == 'random':
            # Pure random selection (respects weights)
            rng = random.Random(seed)
            weights = [self.get_weight(name) for name in variant_names]
            total_weight = sum(weights)

            schedule = []
            for _ in range(total_runs):
                # Weighted random selection
                r = rng.random() * total_weight
                cumulative = 0
                for i, w in enumerate(weights):
                    cumulative += w
                    if r <= cumulative:
                        schedule.append(i)
                        break
                else:
                    schedule.append(n_variants - 1)

            return schedule

        elif self.method == 'balanced':
            # Distribute according to weights, then shuffle
            weights = [self.get_weight(name) for name in variant_names]
            total_weight = sum(weights)

            # Calculate counts for each variant
            counts = []
            for w in weights:
                count = int(total_runs * w / total_weight)
                counts.append(count)

            # Distribute remainder to variants with highest weights
            remainder = total_runs - sum(counts)
            if remainder > 0:
                # Sort indices by weight (descending) for remainder distribution
                sorted_indices = sorted(range(n_variants),
                                         key=lambda i: weights[i],
                                         reverse=True)
                for i in range(remainder):
                    counts[sorted_indices[i % n_variants]] += 1

            # Build schedule from counts
            schedule = []
            for i, count in enumerate(counts):
                schedule.extend([i] * count)

            # Shuffle to randomize order (deterministic if seed set)
            rng = random.Random(seed)
            rng.shuffle(schedule)

            return schedule

        else:
            # Unknown method - fall back to sequential
            print(f"[SelectionConfig] Warning: Unknown method '{self.method}', using sequential")
            return [i % n_variants for i in range(total_runs)]

    def calculate_distribution(self, variant_names: List[str], total_runs: int) -> Dict[str, int]:
        """
        Calculate how many runs each variant will receive.

        Args:
            variant_names: List of variant names
            total_runs: Total number of runs

        Returns:
            Dictionary mapping variant_name to run count
        """
        if not variant_names or total_runs <= 0:
            return {name: 0 for name in variant_names}

        weights = [self.get_weight(name) for name in variant_names]
        total_weight = sum(weights)

        # Calculate base counts
        counts = {}
        remaining = total_runs

        for i, name in enumerate(variant_names):
            count = int(total_runs * weights[i] / total_weight)
            counts[name] = count
            remaining -= count

        # Distribute remainder
        if remaining > 0:
            sorted_names = sorted(variant_names,
                                  key=lambda n: self.get_weight(n),
                                  reverse=True)
            for i in range(remaining):
                counts[sorted_names[i % len(variant_names)]] += 1

        return counts

    def validate(self) -> List[str]:
        """
        Validate selection configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if self.method not in self.METHODS:
            errors.append(f"Invalid selection method: '{self.method}'. Must be one of {self.METHODS}")

        for name, weight in self.weights.items():
            if weight <= 0:
                errors.append(f"Weight for variant '{name}' must be positive, got {weight}")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'method': self.method,
            'weights': self.weights.copy()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SelectionConfig':
        """
        Deserialize from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            SelectionConfig instance
        """
        config = cls()
        config.method = data.get('method', 'balanced')
        config.weights = data.get('weights', {}).copy()
        return config

    def __repr__(self):
        return f"SelectionConfig(method='{self.method}', weights={len(self.weights)})"
