"""Monte-Carlo model of what the comb shuffler does to card order.

One pass through the machine:

1. The deck is dropped onto the comb.  Each blade cuts it, so the deck
   becomes a row of small *packets*, one per channel.
2. Channels alternate between a left-sloping and a right-sloping ramp, so
   packets go alternately to the LEFT bin and the RIGHT bin.  Inside each bin
   the cards keep their relative order.
3. The user stacks the left pile on the right pile and drops again.

That is an *inverse riffle shuffle* whose "bits" come in clumps of one packet.
The randomness comes from where the cuts fall, which depends on where in the
(oversized) collar the deck happened to be released and how tightly it was
squeezed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class CombModel:
    """The handful of machine numbers that matter for mixing."""

    cards_per_channel: float = 5.0   # channel_w / card_pitch
    fill_min: float = 0.6            # loosest a channel fills, as a fraction
    pattern: str = "LR"              # bin for successive channels, repeated


def cut_into_packets(n_cards: int, model: CombModel, rng: random.Random) -> list[int]:
    """Packet sizes, in deck order, for one drop.  Always sums to n_cards."""
    sizes: list[int] = []
    remaining = n_cards
    # The first blade meets the deck at a random phase -> short first packet.
    first = max(1, round(model.cards_per_channel * rng.random()))
    while remaining > 0:
        if not sizes:
            size = first
        else:
            fill = rng.uniform(model.fill_min, 1.0)
            size = max(1, round(model.cards_per_channel * fill))
        size = min(size, remaining)
        sizes.append(size)
        remaining -= size
    return sizes


def one_pass(deck: list[int], model: CombModel, rng: random.Random) -> tuple[list[int], list[int]]:
    """Drop the deck once.  Returns (left_pile, right_pile)."""
    sizes = cut_into_packets(len(deck), model, rng)
    # Which channel the first packet lands in depends on where the deck was
    # released, so the starting point in the L/R pattern is random.
    start = rng.randrange(len(model.pattern))
    left: list[int] = []
    right: list[int] = []
    pos = 0
    for k, size in enumerate(sizes):
        side = model.pattern[(start + k) % len(model.pattern)]
        (left if side == "L" else right).extend(deck[pos:pos + size])
        pos += size
    return left, right


def restack(left: list[int], right: list[int]) -> list[int]:
    """What the user does between drops: left pile goes on top of right."""
    return left + right


def shuffle(deck: list[int], passes: int, model: CombModel, rng: random.Random) -> list[int]:
    for _ in range(passes):
        deck = restack(*one_pass(deck, model, rng))
    return deck


# --------------------------------------------------------------------------
# Mixing metrics
# --------------------------------------------------------------------------

def neighbours_kept(deck: list[int]) -> float:
    """Fraction of originally-consecutive pairs (i, i+1) still adjacent, in order.

    1.0 for an untouched deck; about 1/n for a perfectly random one.
    """
    n = len(deck)
    kept = sum(1 for a, b in zip(deck, deck[1:]) if b == a + 1)
    return kept / (n - 1)


def position_bias(n_cards: int, passes: int, model: CombModel,
                  trials: int, seed: int = 0) -> float:
    """Mean total-variation distance between where a card ends up and uniform.

    0 = every card equally likely to be anywhere.  With a finite number of
    trials even a perfect shuffle scores about sqrt(n_cards / (2*pi*trials)).
    """
    rng = random.Random(seed)
    counts = [[0] * n_cards for _ in range(n_cards)]
    start = list(range(n_cards))
    for _ in range(trials):
        for pos, card in enumerate(shuffle(start, passes, model, rng)):
            counts[card][pos] += 1
    uniform = 1.0 / n_cards
    tv = [0.5 * sum(abs(c / trials - uniform) for c in row) for row in counts]
    return sum(tv) / n_cards


def mean_neighbours_kept(n_cards: int, passes: int, model: CombModel,
                         trials: int, seed: int = 0) -> float:
    rng = random.Random(seed)
    start = list(range(n_cards))
    return sum(neighbours_kept(shuffle(start, passes, model, rng))
               for _ in range(trials)) / trials


def passes_needed(n_cards: int, model: CombModel, trials: int = 400,
                  tolerance: float = 2.0, max_passes: int = 40, seed: int = 0) -> int:
    """Fewest drops until surviving neighbours are within `tolerance` x random."""
    target = tolerance / n_cards
    for k in range(1, max_passes + 1):
        if mean_neighbours_kept(n_cards, k, model, trials, seed) <= target:
            return k
    return max_passes


if __name__ == "__main__":
    n = 60
    for pattern in ("LR", "LRRL", "LRRLRLLR", "LLRR"):
        m = CombModel(pattern=pattern)
        row = [f"{mean_neighbours_kept(n, k, m, 300):.3f}" for k in (1, 3, 5, 7, 10, 14)]
        bias = [f"{position_bias(n, k, m, 3000):.3f}" for k in (5, 7, 10, 14)]
        print(f"{pattern:9s} kept@1,3,5,7,10,14: {row}  bias@5,7,10,14: {bias}"
              f"  passes_needed={passes_needed(n, m)}")
    print("random baseline kept ~", round(1 / n, 3),
          " bias noise floor ~", round((n / (2 * 3.14159 * 3000)) ** 0.5, 3))
