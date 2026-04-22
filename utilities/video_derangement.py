"""
Video derangement utility for the joint-different variant.

Given a pool of video paths, generates (p1_video, p2_video) pairs such that
within each pair p1_video != p2_video, and across the returned pairs both
participants watch the same subset of videos (supporting offline
"pseudo-pair" analysis where a video seen by P1 at time t1 can be matched
to the same video seen by P2 at time t2).

Uses a Sattolo-style explicit-swap algorithm, which guarantees a derangement
in a single pass without the unbounded retries of a naive shuffle-and-check
approach.
"""

from typing import List, Optional, Tuple
import random


def derange_pool(
    pool: List[str],
    k: int,
    seed: Optional[int] = None
) -> List[Tuple[str, str]]:
    """
    Generate k (p1_video, p2_video) pairs from the given video pool.

    Guarantees:
      - Every pair has p1 != p2.
      - When k <= len(unique pool), the set of P1 videos equals the set of
        P2 videos (same subset, enabling pseudo-pair analysis).
      - When k > len(unique pool), the pool is cycled in blocks of
        len(pool) derangements; each block preserves the same-subset
        property independently.

    Args:
        pool: List of video paths. Duplicates are collapsed to preserve
              derangement semantics (a pool like ['A','A','B'] becomes
              ['A','B']).
        k: Number of pairs to generate.
        seed: Optional RNG seed for reproducibility.

    Returns:
        List of k (p1_video, p2_video) tuples, or an empty list if the
        pool has fewer than 2 unique videos (a single-element pool cannot
        be deranged).
    """
    unique_pool = list(dict.fromkeys(pool))
    n = len(unique_pool)

    if n < 2:
        print(f"[derange_pool] ERROR: pool has {n} unique videos; need at least 2")
        return []
    if k <= 0:
        return []

    rng = random.Random(seed)

    # Single block covers the request — no cycling needed.
    if k <= n:
        return _derangement_block(unique_pool, k, rng)

    # Cycling: split k into a series of block sizes, each >= 2, each <= n.
    # Naive (k // n) + (k % n) can leave a size-1 remainder that cannot be
    # deranged. Steal one slot from the previous block to promote the
    # remainder to size 2.
    block_sizes: List[int] = []
    remaining = k
    while remaining > 0:
        if remaining >= n:
            block_sizes.append(n)
            remaining -= n
        else:
            if remaining == 1 and block_sizes and block_sizes[-1] > 2:
                # Borrow 1 from previous block to make this one size 2.
                block_sizes[-1] -= 1
                block_sizes.append(2)
            else:
                block_sizes.append(remaining)
            remaining = 0

    print(f"[derange_pool] WARNING: k={k} > pool size={n}; cycling pool "
          f"as blocks of sizes {block_sizes}")

    pairs: List[Tuple[str, str]] = []
    for size in block_sizes:
        pairs.extend(_derangement_block(unique_pool, size, rng))
    return pairs


def _derangement_block(
    pool: List[str],
    k: int,
    rng: random.Random
) -> List[Tuple[str, str]]:
    """
    Generate k pairs from pool where s1 is a random size-k sample and
    s2 is a derangement of s1 (s1[i] != s2[i] for all i).

    Uses Sattolo's algorithm: iterate i from len-1 down to 1 and swap
    s2[i] with s2[j] where j is uniform in [0, i). This produces a
    uniform cyclic permutation, which is always a derangement for
    len >= 2.
    """
    n = len(pool)
    if k > n:
        raise ValueError(f"_derangement_block called with k={k} > pool size={n}")

    # Sample k items for P1 and shuffle their order.
    s1 = rng.sample(pool, k)

    if k < 2:
        # Cannot derange a single element.
        return []

    # Sattolo's algorithm on a copy of s1.
    s2 = s1.copy()
    for i in range(len(s2) - 1, 0, -1):
        j = rng.randrange(0, i)  # strictly less than i → guarantees no fixed points
        s2[i], s2[j] = s2[j], s2[i]

    return list(zip(s1, s2))
