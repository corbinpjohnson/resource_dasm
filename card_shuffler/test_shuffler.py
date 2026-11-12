"""Tests for the gravity comb shuffler.

Read top to bottom, these follow a deck through the machine:

    1. the deck fits the collar
    2. the comb splits it without jamming
    3. each packet falls, tips over and slides out
    4. the bins catch the cards and let you pick them up
    5. the parts clamp together with printed hardware only
    6. every part can actually be printed, and nothing collides
    7. repeating the drop really does shuffle the deck

Run with:  pytest test_shuffler.py
"""

import itertools
import math
import random

import pytest

from shuffle_sim import (CombModel, cut_into_packets, mean_neighbours_kept,
                         neighbours_kept, one_pass, passes_needed,
                         position_bias, restack, shuffle)
from shuffler_design import (PRINT_ROTATION, Params, as_printed, bar_positions,
                             build_parts, print_list, resting_pile)

P = Params()


# ---------------------------------------------------------------- 1. collar
class TestDeckFitsTheCollar:
    def test_sixty_sleeved_cards_are_about_42mm_thick(self):
        assert P.deck_t == pytest.approx(42.0)

    def test_card_has_clearance_across_its_width(self):
        assert 2 * P.cx - P.sleeve_w == pytest.approx(2 * P.side_clear)
        assert P.side_clear >= 1.0

    def test_collar_is_deeper_than_the_deck_is_thick(self):
        # The slack is deliberate: where the deck lands decides where the
        # blades cut, and that is the machine's source of randomness.
        slack = P.depth - P.deck_t
        assert slack > P.pitch, "deck must be able to land at any phase of the comb"

    def test_double_sleeved_deck_still_fits(self):
        thick = Params(card_pitch=0.80)
        assert thick.deck_t < thick.capacity


# ------------------------------------------------------------------ 2. comb
class TestCombSplitsTheDeckWithoutJamming:
    def test_channels_can_swallow_the_whole_deck_with_margin(self):
        assert P.capacity >= 1.15 * P.deck_t

    def test_a_channel_takes_about_five_cards(self):
        assert 4 <= P.cards_per_channel <= 6

    def test_half_the_channels_feed_each_bin(self):
        sides = [P.side(i) for i in range(P.n_channels)]
        assert sides.count("L") == sides.count("R")

    def test_neighbouring_channels_go_opposite_ways(self):
        assert all(P.side(i) != P.side(i + 1) for i in range(P.n_channels - 1))

    def test_centre_blade_is_highest_and_tips_step_down_outwards(self):
        # Chevron: the deck is split one blade at a time, each split pushing
        # the outer cards sideways before the next blade arrives.
        mid = P.n_channels // 2
        tips = [P.tip_z(i) for i in range(1, P.n_channels)]
        assert max(tips) == P.tip_z(mid)
        for i in range(mid, P.n_channels - 1):
            assert P.tip_z(i + 1) == pytest.approx(P.tip_z(i) - P.chevron_step)
        for i in range(mid, 1, -1):
            assert P.tip_z(i - 1) == pytest.approx(P.tip_z(i) - P.chevron_step)

    def test_a_blade_is_fully_in_before_the_next_one_starts(self):
        assert P.chevron_step >= P.bevel_h

    def test_blade_tips_are_below_the_rim(self):
        assert all(P.tip_z(i) <= -P.tip_guard for i in range(P.n_channels))

    def test_blade_tops_slope_so_a_card_cannot_balance_on_one(self):
        outline = P.blade_outline(P.n_channels // 2)
        peak = max(z for x, z in outline if abs(x) < P.cx)
        eave = min(z for x, z in outline if abs(x) == P.cx and z > -P.collar_h)
        assert peak - eave == pytest.approx(P.roof_drop)
        assert P.roof_deg >= 10

    def test_every_blade_edge_is_guided_by_the_collar(self):
        deepest_eave = min(P.tip_z(i) for i in range(P.n_channels)) - P.roof_drop
        assert -P.collar_h < deepest_eave - P.bevel_h


# ------------------------------------------------------------- 3. card path
class TestPacketFallsTipsAndSlidesOut:
    def test_ramp_is_much_steeper_than_friction(self):
        assert P.ramp_deg >= P.friction_deg + 15

    def test_card_is_clear_of_the_collar_before_it_tips(self):
        # A card pivots on its landing corner and swings towards the exit.
        # The collar wall on that side must already be above it.
        assert P.landing_card_top() <= -P.boss_short

    def test_left_and_right_ramps_are_mirror_images(self):
        for x in (-30.0, 0.0, 12.5, 30.0):
            assert P.ramp_z(x, "L") == pytest.approx(P.ramp_z(-x, "R"))

    def test_left_ramp_descends_to_the_left(self):
        assert P.ramp_z(-P.bx, "L") < P.ramp_z(P.bx, "L")
        assert P.ramp_z(P.bx, "L") == pytest.approx(P.z_hi)

    def test_blade_separates_channels_all_the_way_down_both_ramps(self):
        bottom = min(z for _, z in P.blade_outline(3))
        assert bottom <= P.z_lo - P.rib_d + 1e-9

    def test_bin_floor_never_presents_a_lip_to_a_sliding_card(self):
        x, z = P.bin_origin
        assert z < P.ramp_z(x, "L")
        assert x < -P.bx

    def test_card_at_rest_has_left_the_comb_completely(self):
        assert max(x for x, _ in P.resting_card("L")) < -P.bx
        assert min(x for x, _ in P.resting_card("R")) > P.bx


# ------------------------------------------------------------------ 4. bins
class TestBinsCatchAndReleaseTheCards:
    def test_bin_is_longer_than_a_card_is_wide(self):
        assert P.bin_len > P.sleeve_w

    def test_walls_are_above_a_cards_centre_of_gravity(self):
        assert P.wall_h > P.sleeve_h / 2 + 5

    def test_cards_stick_out_above_the_walls_to_be_pinched(self):
        assert P.sleeve_h - P.wall_h >= 25

    def test_finger_notch_is_wide_enough_for_a_thumb_but_not_a_card(self):
        assert 22 <= P.notch_w < P.sleeve_w

    def test_end_stop_is_square_to_the_floor(self):
        a = P.bin_pt(P.bin_len, 0)
        b = P.bin_pt(P.bin_len, P.stop_h)
        c = P.bin_pt(0, 0)
        dot = (b[0] - a[0]) * (c[0] - a[0]) + (b[1] - a[1]) * (c[1] - a[1])
        assert dot == pytest.approx(0, abs=1e-9)

    def test_machine_stands_on_a_flat_base_below_the_bins(self):
        lowest_floor = min(z for _, z in P.bin_floor_outline())
        assert P.z_base < lowest_floor


# -------------------------------------------------------------- 5. hardware
class TestPrintedHardwareClampsTheStack:
    def test_six_bars_three_in_each_half(self):
        xs = [x for x, _ in bar_positions(P)]
        assert len(xs) == 6
        assert sum(x < 0 for x in xs) == sum(x > 0 for x in xs) == 3

    def test_bar_reaches_through_both_walls_with_room_for_the_wedge(self):
        assert P.bar_len - (P.depth + 2 * P.plate_t) >= P.slot_len

    def test_wedge_slot_starts_inside_the_wall_so_the_wedge_pulls_the_bar_tight(self):
        # slot begins 1 mm behind the wall's outer face (see build_bar)
        assert P.slot_len - 1.0 > P.wedge_narrow
        assert P.slot_len - 1.0 < P.wedge_wide

    def test_wedge_taper_is_self_locking(self):
        assert P.wedge_deg < 10

    def test_wedge_slides_in_its_slot(self):
        assert P.slot_w - P.wedge_t >= 2 * P.fit - 1e-9

    def test_lower_bar_holes_sit_inside_a_rib(self):
        z_top = P.ramp_z(P.bar_x, "R")
        assert z_top - P.rib_d < P.bar_z_low - P.hole / 2
        assert P.bar_z_low + P.hole / 2 < z_top

    def test_lower_bars_are_out_of_the_card_path(self):
        # In a LEFT channel the bar at +bar_x passes underneath the left rib,
        # so no card ever meets it.
        underside_of_left_rib = P.ramp_z(P.bar_x, "L") - P.rib_d
        assert P.bar_z_low + P.hole / 2 < underside_of_left_rib


# ---------------------------------------------------------- 6. printability
@pytest.fixture(scope="module")
def parts():
    return build_parts(P)


def _volume(solid):
    return solid.val().Volume()


def _boxes_overlap(a, b):
    A, B = a.val().BoundingBox(), b.val().BoundingBox()
    return (A.xmin < B.xmax and B.xmin < A.xmax and A.ymin < B.ymax and
            B.ymin < A.ymax and A.zmin < B.zmax and B.zmin < A.zmax)


class TestEveryPartIsPrintableAndNothingCollides:
    def test_print_list_names_every_distinct_part(self):
        files = print_list(P)
        assert sum(n for f, n in files.items() if f.startswith("slice")) == P.n_channels
        assert files["bar"] == files["wedge"] == 6
        assert files["foot"] == 2

    def test_every_part_is_one_valid_solid(self, parts):
        for name, s in parts.items():
            assert s.val().isValid(), name
            assert len(s.solids().vals()) == 1, f"{name} is in pieces"
            assert _volume(s) > 0, name

    def test_every_part_fits_the_bed_in_its_print_orientation(self, parts):
        for name, s in parts.items():
            bb = as_printed(name, s).val().BoundingBox()
            assert bb.xlen <= P.bed[0] and bb.ylen <= P.bed[1] and bb.zlen <= P.bed[2], name

    def test_flat_parts_print_without_rotation(self):
        assert all(PRINT_ROTATION[k] is None for k in ("slice", "back", "front"))

    def test_blade_tip_is_one_nozzle_wide(self):
        assert P.tip_land >= P.nozzle
        assert P.blade_t / 3 == pytest.approx(0.4)   # each terrace = two 0.2 mm layers

    def test_slice_is_exactly_one_pitch_thick(self, parts):
        bb = parts["slice_05"].val().BoundingBox()
        assert bb.zlen == pytest.approx(P.pitch)

    def test_slices_stack_to_fill_the_gap_between_the_walls(self, parts):
        lo = min(parts[f"slice_{i:02d}"].val().BoundingBox().zmin for i in range(P.n_channels))
        hi = max(parts[f"slice_{i:02d}"].val().BoundingBox().zmax for i in range(P.n_channels))
        assert (lo, hi) == (pytest.approx(0.0), pytest.approx(P.depth))

    def test_collar_wall_is_cut_short_on_the_side_the_cards_leave_by(self, parts):
        from shuffler_design import _box
        for i in (4, 5):
            sg = -1 if P.side(i) == "L" else 1
            lo, hi = sorted((sg * P.cx, sg * P.px))
            w = i * P.pitch
            below_short_wall = _box(lo, hi, -P.collar_h, -P.boss_short - 0.1, w + P.blade_t + 0.1, w + P.pitch)
            exit_side = parts[f"slice_{i:02d}"].intersect(below_short_wall)
            assert not exit_side.vals() or exit_side.val().Volume() < 1e-6
            guide_side = parts[f"slice_{i:02d}"].intersect(below_short_wall.mirror("YZ"))
            assert guide_side.val().Volume() > 100

    def test_bin_floor_stops_short_of_the_comb(self):
        gap = -P.bx - max(x for x, _ in P.bin_floor_outline("L"))
        assert gap == pytest.approx(P.bin_gap)

    def test_no_two_parts_occupy_the_same_space(self, parts):
        clashes = []
        for (na, a), (nb, b) in itertools.combinations(parts.items(), 2):
            if _boxes_overlap(a, b):
                v = a.intersect(b).val().Volume() if a.intersect(b).vals() else 0.0
                if v > 0.5:      # mm^3
                    clashes.append((na, nb, round(v, 1)))
        assert not clashes

    def test_resting_piles_do_not_touch_any_part(self, parts):
        for side in "LR":
            pile = resting_pile(P, side)
            for name, s in parts.items():
                if _boxes_overlap(pile, s):
                    hit = pile.intersect(s)
                    assert not hit.vals() or hit.val().Volume() < 0.5, name

    def test_overall_size(self):
        assert P.width < 300 and P.height < 250 and P.depth + 2 * P.plate_t < 80


# --------------------------------------------------------------- 7. shuffle
MODEL = CombModel(cards_per_channel=P.cards_per_channel)


class TestRepeatedDropsShuffleTheDeck:
    def test_cuts_account_for_every_card(self):
        rng = random.Random(1)
        for _ in range(200):
            sizes = cut_into_packets(60, MODEL, rng)
            assert sum(sizes) == 60 and min(sizes) >= 1

    def test_packets_are_about_one_channel_of_cards(self):
        rng = random.Random(2)
        sizes = [s for _ in range(200) for s in cut_into_packets(60, MODEL, rng)[1:-1]]
        assert 3.5 < sum(sizes) / len(sizes) <= P.cards_per_channel

    def test_one_drop_loses_and_duplicates_nothing(self):
        left, right = one_pass(list(range(60)), MODEL, random.Random(3))
        assert sorted(left + right) == list(range(60))

    def test_piles_are_roughly_equal(self):
        rng = random.Random(4)
        sizes = [len(one_pass(list(range(60)), MODEL, rng)[0]) for _ in range(300)]
        assert 20 <= min(sizes) and max(sizes) <= 40

    def test_each_pile_keeps_its_cards_in_order(self):
        # ...which makes a drop an inverse riffle shuffle.
        left, right = one_pass(list(range(60)), MODEL, random.Random(5))
        assert left == sorted(left) and right == sorted(right)

    def test_restack_puts_left_on_right(self):
        assert restack([1, 2], [3]) == [1, 2, 3]

    def test_same_seed_same_shuffle(self):
        a = shuffle(list(range(60)), 8, MODEL, random.Random(6))
        b = shuffle(list(range(60)), 8, MODEL, random.Random(6))
        assert a == b and a != list(range(60))

    def test_neighbour_metric_endpoints(self):
        assert neighbours_kept(list(range(60))) == 1.0
        assert neighbours_kept(list(range(59, -1, -1))) == 0.0

    def test_one_drop_only_separates_about_a_quarter_of_neighbours(self):
        assert 0.6 < mean_neighbours_kept(60, 1, MODEL, 300) < 0.85

    def test_more_drops_always_mix_more(self):
        kept = [mean_neighbours_kept(60, k, MODEL, 300) for k in (1, 3, 6, 10, 15)]
        assert kept == sorted(kept, reverse=True)

    def test_ten_drops_leave_under_a_tenth_of_neighbours_together(self):
        assert mean_neighbours_kept(60, 10, MODEL, 400) < 0.10

    def test_about_fifteen_drops_is_indistinguishable_from_random_by_neighbours(self):
        assert 10 <= passes_needed(60, MODEL) <= 18

    def test_after_seven_drops_any_card_can_be_anywhere(self):
        trials = 3000
        noise_floor = math.sqrt(60 / (2 * math.pi * trials))
        assert position_bias(60, 7, MODEL, trials) < 1.15 * noise_floor

    def test_strict_alternation_beats_pairing_channels_up(self):
        paired = CombModel(cards_per_channel=P.cards_per_channel, pattern="LLRR")
        assert mean_neighbours_kept(60, 6, MODEL, 300) < mean_neighbours_kept(60, 6, paired, 300)

    def test_a_finer_comb_needs_fewer_drops(self):
        fine = CombModel(cards_per_channel=4.0)
        assert passes_needed(60, fine) < passes_needed(60, MODEL)
