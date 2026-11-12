"""Tests for the gravity comb shuffler.

Read top to bottom, these follow a deck through the machine:

    1. the deck fits the hopper and collar
    2. the comb splits it
    3. each packet falls, tips over and slides out
    4. the bins catch the cards and let you pick them up
    5. the parts clamp together with printed hardware only
    6. every part can actually be printed, and nothing collides
    7. repeating the drop really does shuffle the deck (statistical model)
    8. a rigid-body physics engine agrees, and shows why the design is the
       way it is (the first version failed these)

Run with:  pytest test_shuffler.py          (about a minute; section 8 is the slow part)
"""

import itertools
import math
import random
from dataclasses import replace

import pytest

from shuffle_sim import (CombModel, cut_into_packets, mean_neighbours_kept,
                         neighbours_kept, one_pass, passes_needed,
                         position_bias, restack, shuffle)
from shuffler_design import (PRINT_ROTATION, Params, _box, as_printed,
                             bar_positions, build_parts, print_list,
                             resting_pile)

P = Params()
MID = P.n_channels // 2


# ------------------------------------------------------- 1. hopper & collar
class TestDeckFitsTheHopperAndCollar:
    def test_sixty_sleeved_cards_are_about_42mm_thick(self):
        assert P.deck_t == pytest.approx(42.0)

    def test_card_has_clearance_across_its_width(self):
        assert 2 * P.cx - P.sleeve_w == pytest.approx(2 * P.side_clear)
        assert P.side_clear >= 1.0

    def test_throat_holds_the_deck_upright_but_lets_it_land_anywhere_on_the_comb(self):
        # Where the deck lands decides where the blades cut; that is the
        # machine's source of randomness, so the slack must cover a full pitch.
        slack = P.throat - P.deck_t
        assert P.pitch <= slack <= 10

    def test_throat_is_level_with_the_top_of_a_deck_resting_on_the_tips(self):
        deck_top = -P.tip_guard + P.sleeve_h
        assert P.hopper_h - P.throat_h < deck_top <= P.hopper_h

    def test_below_the_throat_the_hopper_is_as_deep_as_the_comb(self):
        w_inner_at_rim = max(w for w, z in P.hopper_end_wz(front=False) if z == 0.0)
        assert w_inner_at_rim == 0.0

    def test_comb_is_deeper_than_the_deck_so_cards_have_room_to_spread(self):
        assert P.depth > P.deck_t + P.n_channels * P.blade_t

    def test_double_sleeved_deck_still_fits(self):
        thick = Params(card_pitch=0.80)
        assert thick.deck_t < thick.capacity
        assert thick.throat < thick.depth


# ------------------------------------------------------------------ 2. comb
class TestCombSplitsTheDeck:
    def test_channels_can_swallow_the_whole_deck_with_margin(self):
        assert P.capacity >= 1.15 * P.deck_t

    def test_a_packet_is_about_seven_cards(self):
        assert 6 <= P.cards_per_channel <= 8

    def test_blades_are_thin_compared_with_their_spacing(self):
        # Learned from the physics test: 1.2 mm blades at 4.7 mm pitch (26%)
        # jam two thirds of the deck; 0.8 at 5.0 (16%) passes.
        assert P.blade_t / P.pitch <= 0.17

    def test_blade_is_a_whole_number_of_layers_and_its_tip_is_one_layer(self):
        assert (P.blade_t / 0.2) == pytest.approx(round(P.blade_t / 0.2))
        assert P.tip_land == pytest.approx(0.2)

    def test_half_the_channels_feed_each_bin(self):
        sides = [P.side(i) for i in range(P.n_channels)]
        assert sides.count("L") == sides.count("R")

    def test_neighbouring_channels_go_opposite_ways(self):
        assert all(P.side(i) != P.side(i + 1) for i in range(P.n_channels - 1))

    def test_every_blade_is_on_the_centre_side_of_its_own_channel(self):
        # Back-half slices are mirrored, so every bevel faces away from the
        # centre and nudges the rest of the deck outwards.
        centre = P.depth / 2
        for i in range(P.n_channels):
            blade_mid = sum(P.blade_w(i)) / 2
            channel_mid = sum(P.channel_range(i)) / 2
            assert abs(blade_mid - centre) < abs(channel_mid - centre)

    def test_the_two_middle_blades_sit_back_to_back(self):
        assert P.blade_w(MID - 1)[1] == pytest.approx(P.blade_w(MID)[0])

    def test_exactly_one_blade_leads(self):
        # Two equal-height tips back to back make a flat a card can sit on.
        tips = [P.tip_z(i) for i in range(P.n_channels)]
        assert tips.count(max(tips)) == 1
        assert P.tip_z(MID) == max(tips)

    def test_tips_step_down_outwards_in_a_chevron(self):
        for i in range(MID, P.n_channels - 1):
            assert P.tip_z(i + 1) == pytest.approx(P.tip_z(i) - P.chevron_step)
        for i in range(MID, 0, -1):
            assert P.tip_z(i - 1) == pytest.approx(P.tip_z(i) - P.chevron_step)

    def test_a_blade_is_fully_in_before_the_next_one_starts(self):
        assert P.chevron_step >= P.bevel_h

    def test_blade_tips_are_below_the_rim(self):
        assert all(P.tip_z(i) <= -P.tip_guard for i in range(P.n_channels))

    def test_blade_tops_slope_away_from_a_central_peak(self):
        outline = P.blade_outline(MID)
        peak = max(z for x, z in outline if abs(x) < P.cx)
        eave = min(z for x, z in outline if abs(x) == P.cx and z > -P.collar_h)
        assert peak - eave == pytest.approx(P.roof_drop)
        assert P.roof_deg >= 10

    def test_every_blade_edge_ends_inside_the_collar(self):
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

    def test_bin_floor_stops_short_of_the_comb(self):
        gap = -P.bx - max(x for x, _ in P.bin_floor_outline("L"))
        assert gap == pytest.approx(P.bin_gap)

    def test_card_at_rest_has_left_the_comb_completely(self):
        assert max(x for x, _ in P.resting_card("L")) < -P.bx
        assert min(x for x, _ in P.resting_card("R")) > P.bx


# ------------------------------------------------------------------ 4. bins
class TestBinsCatchAndReleaseTheCards:
    def test_bin_is_longer_than_a_card_is_wide(self):
        assert P.bin_len > P.sleeve_w

    def test_end_stop_is_taller_than_a_cards_centre_of_gravity(self):
        # A card arrives at well over 1 m/s.  A stop below its centre of
        # gravity trips it and it somersaults out (see section 8).
        assert P.stop_h > P.sleeve_h / 2 + 10

    def test_walls_are_above_a_cards_centre_of_gravity(self):
        assert P.wall_h > P.sleeve_h / 2 + 5

    def test_cards_stick_out_above_the_walls_to_be_pinched(self):
        assert P.sleeve_h - max(P.wall_h, P.stop_h) >= 25

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
        assert P.wedge_narrow < P.slot_len - 1.0 < P.wedge_wide

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

    def test_bin_bar_passes_through_the_end_stop(self):
        assert 0 < 11.0 < P.stop_h
        assert P.stop_t > P.hole * 1.5


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


def _overlap_volume(a, b):
    hit = a.intersect(b)
    return hit.val().Volume() if hit.vals() else 0.0


class TestEveryPartIsPrintableAndNothingCollides:
    def test_print_list_names_every_distinct_part(self):
        files = print_list(P)
        assert sum(n for f, n in files.items() if f.startswith("slice")) == P.n_channels
        assert files["bar"] == files["wedge"] == 6
        assert files["foot"] == 2
        assert files["hopper"] == 1

    def test_every_part_is_one_valid_solid(self, parts):
        for name, s in parts.items():
            assert s.val().isValid(), name
            assert len(s.solids().vals()) == 1, f"{name} is in pieces"
            assert _volume(s) > 0, name

    def test_every_part_fits_the_bed_in_its_print_orientation(self, parts):
        for name, s in parts.items():
            bb = as_printed(name, s, P).val().BoundingBox()
            assert bb.xlen <= P.bed[0] and bb.ylen <= P.bed[1] and bb.zlen <= P.bed[2], name

    def test_walls_print_flat_as_modelled(self):
        assert PRINT_ROTATION["back"] is None and PRINT_ROTATION["front"] is None

    def test_every_slice_prints_with_its_blade_on_the_bed(self, parts):
        # ...including the mirrored back-half slices, which are turned over.
        for i in (0, MID - 1, MID, P.n_channels - 1):
            printed = as_printed(f"slice_{i:02d}", parts[f"slice_{i:02d}"], P)
            bb = printed.val().BoundingBox()
            assert bb.zlen == pytest.approx(P.pitch)
            first_layer = _box(bb.xmin, bb.xmax, bb.ymin, bb.ymax, 0.0, 0.2)
            last_layer = _box(bb.xmin, bb.xmax, bb.ymin, bb.ymax, P.pitch - 0.2, P.pitch)
            assert _overlap_volume(printed, first_layer) > 3 * _overlap_volume(printed, last_layer)

    def test_hopper_prints_upside_down_with_the_throat_ring_on_the_bed(self, parts):
        printed = as_printed("hopper", parts["hopper"], P)
        bb = printed.val().BoundingBox()
        assert bb.zlen == pytest.approx(P.hopper_h + P.tab_h)
        slab = lambda z0, z1: _box(bb.xmin, bb.xmax, bb.ymin, bb.ymax, z0, z1)
        ring, wall = _overlap_volume(printed, slab(5, 6)), _overlap_volume(printed, slab(50, 51))
        assert ring > wall, "the thick ring must be at the bottom of the print"

    def test_slices_stack_to_fill_the_gap_between_the_walls(self, parts):
        lo = min(parts[f"slice_{i:02d}"].val().BoundingBox().zmin for i in range(P.n_channels))
        hi = max(parts[f"slice_{i:02d}"].val().BoundingBox().zmax for i in range(P.n_channels))
        assert (lo, hi) == (pytest.approx(0.0), pytest.approx(P.depth))

    def test_collar_wall_is_cut_short_on_the_side_the_cards_leave_by(self, parts):
        for i in (MID, MID + 1):
            sg = -1 if P.side(i) == "L" else 1
            lo, hi = sorted((sg * P.cx, sg * P.px))
            c0, c1 = P.channel_range(i)
            below_short_wall = _box(lo, hi, -P.collar_h, -P.boss_short - 0.1, c0 + 0.1, c1 - 0.1)
            assert _overlap_volume(parts[f"slice_{i:02d}"], below_short_wall) < 1e-6
            assert _overlap_volume(parts[f"slice_{i:02d}"], below_short_wall.mirror("YZ")) > 100

    def test_no_two_parts_occupy_the_same_space(self, parts):
        clashes = []
        for (na, a), (nb, b) in itertools.combinations(parts.items(), 2):
            if _boxes_overlap(a, b):
                v = _overlap_volume(a, b)
                if v > 0.5:      # mm^3
                    clashes.append((na, nb, round(v, 1)))
        assert not clashes

    def test_resting_piles_do_not_touch_any_part(self, parts):
        for side in "LR":
            pile = resting_pile(P, side)
            for name, s in parts.items():
                if _boxes_overlap(pile, s):
                    assert _overlap_volume(pile, s) < 0.5, name

    def test_overall_size(self):
        assert P.width < 300
        assert P.height < 250, "tower walls must fit a 250 mm bed"
        assert P.height + P.hopper_h < 340
        assert P.depth + 2 * P.plate_t < 80


# ------------------------------------------------ 7. shuffle (statistical model)
MODEL = CombModel(cards_per_channel=P.cards_per_channel)
IDEAL = replace(MODEL, straggle=0.0)


class TestRepeatedDropsShuffleTheDeck:
    def test_cuts_account_for_every_card(self):
        rng = random.Random(1)
        for _ in range(200):
            sizes = cut_into_packets(60, MODEL, rng)
            assert sum(sizes) == 60 and min(sizes) >= 1

    def test_packets_are_six_or_seven_cards(self):
        rng = random.Random(2)
        sizes = [s for _ in range(200) for s in cut_into_packets(60, MODEL, rng)[1:-1]]
        assert set(sizes) <= {6, 7}

    def test_one_drop_loses_and_duplicates_nothing(self):
        left, right = one_pass(list(range(60)), MODEL, random.Random(3))
        assert sorted(left + right) == list(range(60))

    def test_piles_are_roughly_equal(self):
        rng = random.Random(4)
        sizes = [len(one_pass(list(range(60)), MODEL, rng)[0]) for _ in range(300)]
        assert 22 <= min(sizes) and max(sizes) <= 38

    def test_without_stragglers_each_pile_keeps_its_cards_in_order(self):
        # ...which makes an ideal drop an inverse riffle shuffle.
        left, right = one_pass(list(range(60)), IDEAL, random.Random(5))
        assert left == sorted(left) and right == sorted(right)

    def test_a_straggler_moves_only_within_its_own_packet(self):
        left, right = one_pass(list(range(60)), MODEL, random.Random(5))
        assert left != sorted(left) or right != sorted(right)
        for pile in (left, right):
            assert all(abs(a - b) <= 2 * 8 for a, b in zip(sorted(pile), pile))

    def test_restack_puts_left_on_right(self):
        assert restack([1, 2], [3]) == [1, 2, 3]

    def test_same_seed_same_shuffle(self):
        a = shuffle(list(range(60)), 8, MODEL, random.Random(6))
        b = shuffle(list(range(60)), 8, MODEL, random.Random(6))
        assert a == b and a != list(range(60))

    def test_neighbour_metric_endpoints(self):
        assert neighbours_kept(list(range(60))) == 1.0
        assert neighbours_kept(list(range(59, -1, -1))) == 0.0

    def test_one_drop_separates_about_a_quarter_of_neighbours(self):
        assert 0.65 < mean_neighbours_kept(60, 1, MODEL, 300) < 0.80

    def test_more_drops_always_mix_more(self):
        kept = [mean_neighbours_kept(60, k, MODEL, 300) for k in (1, 3, 6, 10, 15)]
        assert kept == sorted(kept, reverse=True)

    def test_ten_drops_leave_under_a_tenth_of_neighbours_together(self):
        assert mean_neighbours_kept(60, 10, MODEL, 400) < 0.10

    def test_about_thirteen_drops_is_indistinguishable_from_random_by_neighbours(self):
        assert 10 <= passes_needed(60, MODEL) <= 16

    def test_stragglers_halve_the_number_of_drops_needed(self):
        assert passes_needed(60, IDEAL) > 1.5 * passes_needed(60, MODEL)

    def test_after_seven_drops_any_card_can_be_anywhere(self):
        trials = 3000
        noise_floor = math.sqrt(60 / (2 * math.pi * trials))
        assert position_bias(60, 7, MODEL, trials) < 1.15 * noise_floor

    def test_strict_alternation_beats_pairing_channels_up(self):
        paired = replace(MODEL, pattern="LLRR")
        assert mean_neighbours_kept(60, 6, MODEL, 300) < mean_neighbours_kept(60, 6, paired, 300)

    def test_a_finer_comb_needs_fewer_drops(self):
        assert passes_needed(60, replace(MODEL, cards_per_channel=5.0)) < passes_needed(60, MODEL)


# --------------------------------------------------- 8. rigid-body physics
# MuJoCo drops 60 rigid 0.6 mm cards into the real geometry.  Thresholds are
# loose because contact dynamics are chaotic: over 16 seeds the design
# delivered 98% of cards, with 11 drops perfectly clean.
physics_sim = pytest.importorskip("physics_sim")
pytest.importorskip("mujoco")

SEEDS = (1, 2, 3)


def _drops(p, seeds=SEEDS):
    rig = physics_sim.Rig(p)
    deck = list(range(rig.n))
    return [rig.drop(deck, random.Random(s)) for s in seeds]


@pytest.fixture(scope="module")
def drops():
    return _drops(P)


class TestPhysicsEngineAgrees:
    def test_nearly_every_card_reaches_a_bin(self, drops):
        for r in drops:
            assert len(r.left) + len(r.right) >= 57

    def test_no_card_leaves_the_machine(self, drops):
        assert all(not r.escaped for r in drops)

    def test_piles_are_roughly_equal(self, drops):
        for r in drops:
            assert 22 <= len(r.left) <= 38 and 22 <= len(r.right) <= 38

    def test_even_channels_feed_the_left_bin_and_odd_the_right(self, drops):
        for r in drops:
            assert all(r.lane[c] % 2 == 0 for c in r.left)
            assert all(r.lane[c] % 2 == 1 for c in r.right)

    def test_packets_are_seven_cards_as_the_statistical_model_assumes(self, drops):
        for r in drops:
            sizes = [n for _, n in physics_sim.packets(list(range(60)), r)]
            assert max(sizes) <= 8
            assert sizes.count(7) >= len(sizes) // 2

    def test_piles_are_in_order_apart_from_a_few_stragglers(self, drops):
        for r in drops:
            for pile in (r.left, r.right):
                out_of_order = sum(1 for a, b in zip(pile, pile[1:]) if b < a)
                assert out_of_order <= 6

    def test_one_drop_keeps_about_two_thirds_of_neighbours(self, drops):
        kept = [neighbours_kept(r.left + r.right + r.stuck) for r in drops]
        assert 0.5 < sum(kept) / len(kept) < 0.85

    def test_cards_settle_within_three_seconds(self, drops):
        assert all(r.settle_time < 3.0 for r in drops)


class TestPhysicsExplainsTheDesign:
    """Each of these is a fault the first version had, reproduced on purpose."""

    def test_thick_blades_jam_the_deck(self):
        first_version = replace(P, blade_t=1.2, channel_w=3.5)
        for r in _drops(first_version, seeds=(1, 2)):
            assert len(r.stuck) > 20

    def test_a_low_end_stop_lets_cards_somersault_out_of_the_bins(self):
        low_stop = replace(P, stop_h=26.0)
        assert sum(len(r.escaped) for r in _drops(low_stop, seeds=(1, 2))) > 10
