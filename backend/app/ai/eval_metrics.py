"""Metric primitives for evaluating the curriculum-remap matching pipeline.

Pure by design: no database, no I/O, no clock, no randomness. The same discipline as
services/adaptive_selector.py, and for the same reason — a number that decides whether a
threshold is correct has to be reproducible and testable in isolation.

Every proportion is reported with an interval rather than as a bare point estimate. The
cambridge_v2 remap produced roughly 71 reviewable decisions; over that many samples "the
adjudicator agreed 87% of the time" and "the adjudicator agreed 87% of the time, 95% CI
[0.77, 0.93]" support very different conclusions, and only the second one is honest.
"""

from dataclasses import dataclass

# 95% two-sided. Not configurable on purpose: a report that silently varies its
# confidence level between runs is not comparable with itself.
DEFAULT_Z = 1.96


@dataclass(frozen=True)
class Rate:
    """A proportion together with its uncertainty.

    Frozen so a computed metric cannot be edited after the fact — these values end up in
    a committed report, and a mutable one invites "adjusting" an inconvenient number.
    """

    numerator: int
    denominator: int
    point: float
    low: float
    high: float

    def format(self) -> str:
        """Render for the report: point estimate, interval, and the sample size.

        The sample size is never omitted. A rate without an n is unreadable — 1/1 and
        900/900 both print as 100%.
        """
        return f"{self.point * 100:.1f}% [{self.low * 100:.1f}–{self.high * 100:.1f}] (n={self.denominator})"


def wilson_interval(successes: int, trials: int, z: float = DEFAULT_Z) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Chosen over the normal approximation because the rates being measured here live near
    the ends of the range, where the normal approximation produces intervals that extend
    below 0 or above 1 and collapse to zero width at exactly 0 and 1 — implying certainty
    from a handful of observations.

    Args:
        successes: Count of successful trials.
        trials: Total trials.
        z: Standard-normal quantile; defaults to 95% two-sided.

    Returns:
        (low, high), both clamped into [0.0, 1.0].

    Raises:
        ValueError: If counts are negative or successes exceed trials. Both indicate a
            miscounted caller, and returning a plausible-looking rate would hide it.
    """
    if successes < 0 or trials < 0:
        raise ValueError(f"counts must not be negative: successes={successes}, trials={trials}")
    if successes > trials:
        raise ValueError(f"successes ({successes}) cannot exceed trials ({trials})")

    # No evidence admits the whole range. Returning (0, 0) here would read as "measured
    # zero", which is a different and much stronger claim than "did not measure".
    if trials == 0:
        return (0.0, 1.0)

    n = float(trials)
    p = successes / n
    z_sq = z * z

    denominator = 1.0 + z_sq / n
    centre = (p + z_sq / (2.0 * n)) / denominator
    half_width = (z / denominator) * ((p * (1.0 - p) / n + z_sq / (4.0 * n * n)) ** 0.5)

    return (max(0.0, centre - half_width), min(1.0, centre + half_width))


def rate(successes: int, trials: int, z: float = DEFAULT_Z) -> Rate:
    """Build a Rate from raw counts.

    A zero denominator yields point 0.0 with the full [0, 1] interval rather than raising:
    the harness runs against databases that may legitimately have no resolved items yet,
    and a reporting script that crashes on an empty table is a silent failure to report.
    The wide interval is what signals the absence of evidence.
    """
    low, high = wilson_interval(successes, trials, z)
    point = successes / trials if trials else 0.0
    return Rate(numerator=successes, denominator=trials, point=point, low=low, high=high)


def stratify(values: list[float], edges: list[float]) -> dict[str, list[int]]:
    """Bucket values into lower-inclusive bands, returning input indices.

    Indices rather than values, so a caller can recover the whole row a value came from —
    a bare list of similarities cannot be traced back to the question it scored.

    Bands are lower-inclusive to match how the pipeline's own thresholds are written
    (">= AUTO_BIND_THRESHOLD binds automatically"), so a value sitting exactly on an edge
    is bucketed the same way the pipeline would have treated it.

    A `<{first_edge}` bucket always exists and always appears in the result. Values below
    the first edge mean the caller filtered incorrectly; folding them into the lowest real
    stratum would quietly contaminate a precision figure, and dropping them would lose
    rows without saying so.

    Args:
        values: Values to bucket.
        edges: Ascending lower bounds, at least one.

    Returns:
        Bucket label -> indices into `values`. Every bucket is present even when empty,
        and every input index appears in exactly one bucket.

    Raises:
        ValueError: If `edges` is empty, not strictly ascending, or contains values that
            collide once rendered at label precision.
    """
    if not edges:
        raise ValueError("edges must contain at least one lower bound")
    if any(b <= a for a, b in zip(edges, edges[1:], strict=False)):
        raise ValueError(f"edges must be in strictly ascending order, got {edges}")

    # Fixed two decimals rather than %g: similarity bands are quoted at 2dp throughout the
    # pipeline, and %g would render 0.90 as "0.9", making the report's band labels
    # inconsistent with the thresholds they describe.
    rendered = [f"{edge:.2f}" for edge in edges]
    if len(set(rendered)) != len(rendered):
        raise ValueError(f"edges collide at label precision (2dp): {edges}")

    labels = [f"<{rendered[0]}"]
    labels += [f"{lo}-{hi}" for lo, hi in zip(rendered, rendered[1:], strict=False)]
    labels.append(f"{rendered[-1]}+")

    buckets: dict[str, list[int]] = {label: [] for label in labels}

    for index, value in enumerate(values):
        if value < edges[0]:
            buckets[labels[0]].append(index)
            continue
        # Walk down from the top so an exact edge match lands in the upper band.
        for position in range(len(edges) - 1, -1, -1):
            if value >= edges[position]:
                buckets[labels[position + 1]].append(index)
                break

    return buckets
