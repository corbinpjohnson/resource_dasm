"""Tests for the gravity comb shuffler.

Read top to bottom, these follow a deck through the machine:

    1. the deck fits the hopper and collar
    2. the comb splits it - and cannot jam it
    3. each packet falls, tips over and slides out
    4. the bins catch the cards and let you pick them up
    5. the parts clamp together with printed hardware only
    6. every part can actually be printed, and nothing collides
    7. repeating the drop really does shuffle the deck (statistical model)
    8. a rigid-body physics engine agrees
    9. every fault the physics engine found on the way here, reproduced on
       purpose, so the reason for each design decision stays on record

Run with:  pytest test_shuffler.py                   (about 40 minutes on 4 cores)
           pytest test_shuffler.py -k "not Physics and not Limits"   (15 seconds: geometry and statistics only)
"""

import itertools
import math
import random
from dataclasses import replace

import pytest

from shuffle_sim import (CombModel, cut_into_packets, mean_neighbours_kept,
                         neighbours_kept, one_pass, passes_needed,
                         position_bias, restack, shuffle)
from shuffler_design import (BAR_KINDS, PRINT_ROTATION, Params, _box, _unplace,
                             as_printed, bar_length, bar_positions,
                             build_jam_key, build_parts, print_list,
                             resting_pile, slice_steps, wall_faces)

P = Params()
MID = P.n_channels // 2
CARD_SOLID = 0.6          # thickness of one sleeved card squeezed flat


# ------------------------------------------------------- 1. hopper & collar
class TestDeckFitsTheHopperAndCollar:
    def test_a_hundred_sleeved_cards_are_about_70mm_thick(self):
        assert P.n_cards == 100
        assert P.deck_t == pytest.approx(70.0)

    def test_a_ninety_card_deck_is_only_a_little_loose_in_the_throat(self):
        assert P.throat - 90 * P.card_pitch < 3 * P.pitch

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

    def test_nothing_leans(self):
        # Version 5 leaned the hopper and version 6 leaned the whole machine,
        # both to stop cards arriving late.  Bins that clear the tower made
        # both unnecessary (section 9), and a leaning hopper was harmful.
        assert P.hopper_lean_deg == 0.0
        assert P.machine_tilt_deg == 0.0
        assert P.hopper_shear(P.hopper_h) == 0.0

    def test_hopper_walls_stop_the_deck_leaning_far(self):
        play = (P.throat + P.tube_clear - P.deck_t) / 2 + (P.throat - P.deck_t) / 2
        extra_lean = math.degrees(math.atan(play / (P.hopper_h - P.throat_h)))
        assert extra_lean < 9
        assert P.tube_inset > 0

    def test_finger_slots_let_you_lower_the_deck_to_the_blades_by_its_edges(self):
        # Dropping it from the top of the hopper works less well, and holding
        # it by its faces squeezes it tight, which the comb cannot take.
        deck_top_at_release = -P.tip_guard + 2 + P.sleeve_h
        slot_bottom = P.hopper_h - P.finger_slot
        assert deck_top_at_release - slot_bottom >= 40, "room for fingertips on the deck's edges"
        assert slot_bottom >= 30, "enough wall left below the slot to guide the cards"
        assert P.depth - 2 * P.post_w >= P.deck_t

    def test_collar_is_no_deeper_than_the_deck_needs(self):
        used = P.deck_t + (P.throat - P.deck_t) + P.pitch       # deck, where it may land, one spare lane
        assert P.depth <= used + 2 * P.pitch

    def test_comb_is_deeper_than_the_deck_so_cards_have_room_to_spread(self):
        assert P.depth > P.deck_t + P.n_channels * P.blade_t

    def test_double_sleeved_deck_still_fits(self):
        thick = Params(card_pitch=0.80, n_channels=22)
        assert thick.deck_t < thick.capacity
        assert thick.throat < thick.depth


# ------------------------------------------------------------------ 2. comb
class TestCombSplitsTheDeck:
    def test_channels_can_swallow_the_whole_deck_with_margin(self):
        assert P.capacity >= P.deck_t                      # even at the rim, at full blade thickness
        half_way_down = sum(P.channel_width(i, -60.0) for i in range(P.n_channels))
        assert half_way_down >= 1.2 * P.deck_t             # and the fan adds room below

    def test_a_packet_is_about_seven_cards(self):
        assert 6 <= P.cards_per_channel <= 8

    def test_half_the_channels_feed_each_bin(self):
        sides = [P.side(i) for i in range(P.n_channels)]
        assert sides.count("L") == sides.count("R")

    def test_neighbouring_channels_go_opposite_ways(self):
        assert all(P.side(i) != P.side(i + 1) for i in range(P.n_channels - 1))

    def test_every_blade_is_on_the_centre_side_of_its_own_channel(self):
        # Back-half slices are mirrored, so the two halves of the comb are
        # mirror images and the two middle blades sit back to back.
        centre = P.depth / 2
        for i in range(P.n_channels):
            blade_mid = sum(P.blade_w(i)) / 2
            channel_mid = sum(P.channel_range(i)) / 2
            assert abs(blade_mid - centre) < abs(channel_mid - centre)
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

    def test_blade_tips_are_below_the_rim(self):
        assert all(P.tip_z(i) <= -P.tip_guard for i in range(P.n_channels))

    def test_blade_tops_slope_away_from_a_central_peak(self):
        left, peak, right = P.blade_top(MID)
        assert peak[0] == 0 and peak[1] == P.tip_z(MID)
        assert left[1] == right[1] == pytest.approx(peak[1] - P.top_drop)
        assert P.roof_deg >= 10

    def test_every_blade_edge_ends_inside_the_collar(self):
        lowest_edge = min(z for i in range(P.n_channels) for _, z in P.blade_top(i))
        assert -P.collar_h < lowest_edge


class TestCombCannotJam:
    """The three rules the physics test forced on the comb (see section 9)."""

    def test_blade_tip_and_blade_are_whole_numbers_of_layers(self):
        assert P.tip_land == pytest.approx(0.2)
        for thickness in (P.tip_land, P.blade_t):
            assert thickness / P.layer_h == pytest.approx(round(thickness / P.layer_h))

    def test_comb_is_printed_in_fine_layers_so_the_steps_on_the_blade_faces_are_small(self):
        # Every layer the blade gains is a ledge on the wall cards slide down.
        # At 0.2 mm a deck with a tenth air went from 32 clean drops in 32 to 29;
        # a sleeve's edge has a radius of about 0.3 mm.
        assert P.layer_h <= 0.1

    def test_rule_1_blades_fan_out_from_a_hinge_far_above_the_rim(self):
        assert P.fan_R > 3 * P.sleeve_h
        assert P.spread(0.0) == 1.0
        assert P.spread(P.z_base) > 1.4            # machine is 40%+ deeper at the table than at the rim
        assert math.degrees(P.fan_delta) < 1.0     # under a degree between neighbouring blades

    def test_the_fan_spreads_card_bottoms_by_about_the_thickness_of_all_the_blades(self):
        # While a card's bottom is at the tips its top is one card height nearer
        # the hinge.  The fan must let the bottoms of the deck spread by roughly
        # what the blades add, while the tops stay together.  Too little and the
        # deck wedges; too much and the tops are squeezed instead.
        bottoms_spread = P.depth * P.sleeve_h / P.fan_R
        blades_add = P.n_channels * P.blade_t
        assert 0.9 * blades_add <= bottoms_spread <= 1.5 * blades_add

    def test_the_fan_angle_is_inside_the_window_the_physics_test_passed(self):
        assert 350 <= P.fan_R <= 550

    def test_rule_2_no_channel_ever_gets_narrower_on_the_way_down(self):
        for i in (MID, MID + 3, P.n_channels - 1):
            z = P.tip_z(i)
            widths = []
            while z > P.z_base:
                widths.append(P.channel_width(i, z))
                z -= 1.0
            assert all(b >= a - 1e-9 for a, b in zip(widths, widths[1:])), f"blade {i}"

    def test_the_narrowest_point_holds_a_packet_plus_a_card_split_by_the_tip(self):
        narrowest = min(P.channel_width(i, P.tip_z(i)) for i in range(P.n_channels))
        packet = (P.cards_per_channel + 0.5) * CARD_SOLID
        assert narrowest >= packet + 0.2

    def test_rule_3_a_blade_is_well_into_the_deck_before_the_next_one_starts(self):
        assert P.chevron_step >= 3.0

    def test_blade_faces_are_flush_right_across_including_the_ears(self):
        # The taper line runs past the ears.  When it stopped at the collar
        # opening the ears stood proud of the blade and caught cards.
        xs = [x for x, _ in P.above_taper_line(MID, 30.0)]
        assert min(xs) < -P.px and max(xs) > P.px

    def test_a_point_further_down_a_channel_is_further_out(self):
        c = P.depth / 2
        for z in (-10.0, -100.0, -200.0):
            assert P.lane_of(c + 2.5 * P.spread(z), z) == MID
            assert P.lane_of(c + 7.5 * P.spread(z), z) == MID + 1
            assert P.lane_of(c - 2.5 * P.spread(z), z) == MID - 1


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

    def test_a_card_that_stops_an_inch_short_of_the_fence_is_still_clear_of_the_comb(self):
        # Cards left with a corner under the tower are what later cards got
        # caught on (section 9).
        assert P.bin_extra >= 25

    def test_end_fence_is_taller_than_a_card(self):
        # A card arrives at well over 1 m/s.  A 26 mm stop tripped it and it
        # somersaulted out; a 60 mm one held until the deck was dropped from
        # the top of the hopper (see section 9).
        assert P.fence_h > P.sleeve_h

    def test_walls_are_above_a_cards_centre_of_gravity(self):
        assert P.wall_h > P.sleeve_h / 2 + 5

    def test_cards_stick_out_above_the_walls_to_be_pinched(self):
        assert P.sleeve_h - P.wall_h >= 25

    def test_finger_notch_is_wide_enough_for_a_thumb_but_not_a_card(self):
        assert 22 <= P.notch_w < P.sleeve_w

    def test_end_stop_is_square_to_the_floor(self):
        a = P.bin_pt(P.bin_len, 0)
        b = P.bin_pt(P.bin_len, P.fence_h)
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
        assert len(xs) == len(BAR_KINDS) == 6
        assert sum(x < 0 for x in xs) == sum(x > 0 for x in xs) == 3

    def test_each_bar_reaches_through_both_walls_with_room_for_the_wedge(self):
        for at in bar_positions(P):
            assert bar_length(P, at) >= 2 * wall_faces(P, at[1])[1] + P.slot_len

    def test_lower_bars_are_longer_because_the_machine_fans_out(self):
        ear, _, low, _, bin_, _ = (bar_length(P, at) for at in bar_positions(P))
        assert ear < low < bin_
        assert bin_ - ear > 20

    def test_wedge_seats_part_way_along_its_taper(self):
        usable_slot = P.slot_len - 1.5        # the slot starts 1.5 mm inside the wall (see build_bar)
        assert P.wedge_narrow < usable_slot < P.wedge_wide

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

    def test_feet_are_flat_but_can_be_cut_as_wedges_to_lean_the_machine(self):
        from shuffler_design import build_foot
        flat = build_foot(P, "L").val().BoundingBox()
        assert flat.ylen == pytest.approx(P.foot_h, abs=0.01)
        leaning = build_foot(replace(P, machine_tilt_deg=2.0), "L").val().BoundingBox()
        assert leaning.ylen == pytest.approx(P.foot_h + flat.zlen * math.tan(math.radians(2.0)), abs=0.05)

    def test_bin_bar_passes_through_the_end_stop(self):
        assert P.stop_t > P.hole * 1.5

    def test_jam_key_reaches_from_the_hopper_rim_to_the_ramps_and_fits_any_channel(self):
        bb = build_jam_key(P).val().BoundingBox()
        assert bb.ylen > P.hopper_h - P.z_hi
        narrowest = min(P.channel_width(i, P.tip_z(i) - 5) for i in range(P.n_channels))
        assert bb.zlen < narrowest / 2


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
        assert files["bar_ear"] == files["bar_low"] == files["bar_bin"] == 2
        assert files["wedge"] == 6
        assert files["foot"] == 2
        assert files["hopper"] == files["jam_key"] == 1
        assert files["upper_front"] == files["upper_back"] == 1

    def test_every_part_is_one_valid_solid(self, parts):
        for name, s in parts.items():
            assert s.val().isValid(), name
            assert len(s.solids().vals()) == 1, f"{name} is in pieces"
            assert _volume(s) > 0, name

    def test_every_part_fits_the_bed_in_its_print_orientation(self, parts):
        for name, s in parts.items():
            bb = as_printed(name, s, P).val().BoundingBox()
            assert bb.xlen <= P.bed[0] and bb.ylen <= P.bed[1] and bb.zlen <= P.bed[2], name

    def test_every_slice_prints_with_its_blade_on_the_bed(self, parts):
        # ...including the mirrored back-half slices, which are turned over.
        for i in (0, MID - 1, MID, P.n_channels - 1):
            printed = as_printed(f"slice_{i:02d}", parts[f"slice_{i:02d}"], P)
            bb = printed.val().BoundingBox()
            first_layer = _box(bb.xmin, bb.xmax, bb.ymin, bb.ymax, 0.0, 0.2)
            last_layer = _box(bb.xmin, bb.xmax, bb.ymin, bb.ymax, bb.zlen - 0.2, bb.zlen)
            assert _overlap_volume(printed, first_layer) > 3 * _overlap_volume(printed, last_layer)

    def test_slice_spacers_are_wedges_thicker_at_the_bottom(self, parts):
        # This is what builds the fan: stack the slices and they splay out.
        printed = as_printed(f"slice_{MID:02d}", parts[f"slice_{MID:02d}"], P)
        thickest = printed.val().BoundingBox().zlen
        assert thickest == pytest.approx(P.pitch * P.spread(P.z_lo - P.rib_d), abs=0.2)
        assert thickest > 1.35 * P.pitch

    def test_blade_is_one_layer_thick_at_its_tip_and_full_thickness_low_down(self, parts):
        local = _unplace(P, parts[f"slice_{MID:02d}"], slice_steps(P, MID))
        tip = P.tip_z(MID)
        near_tip = _box(-10, 10, tip - 4, tip - 2, -1, 5)
        low_down = _box(-10, 10, tip - P.bevel_h - 6, tip - P.bevel_h - 4, -1, 5)
        assert local.intersect(near_tip).val().BoundingBox().zlen == pytest.approx(P.tip_land, abs=0.01)
        assert local.intersect(low_down).val().BoundingBox().zlen == pytest.approx(P.blade_t, abs=0.01)

    def test_collar_wall_is_cut_short_on_the_side_the_cards_leave_by(self, parts):
        for i in (MID, MID + 1):
            local = _unplace(P, parts[f"slice_{i:02d}"], slice_steps(P, i))
            sg = -1 if P.side(i) == "L" else 1
            lo, hi = sorted((sg * P.cx, sg * P.px))
            below_short_wall = _box(lo, hi, -P.collar_h + 1, -P.boss_short - 0.5, P.blade_t + 0.1, 3.0)
            assert _overlap_volume(local, below_short_wall) < 1e-6
            assert _overlap_volume(local, below_short_wall.mirror("YZ")) > 50

    def test_hopper_prints_upside_down_with_the_throat_ring_on_the_bed(self, parts):
        printed = as_printed("hopper", parts["hopper"], P)
        bb = printed.val().BoundingBox()
        assert bb.zlen == pytest.approx(P.hopper_h + P.tab_h)
        slab = lambda z0, z1: _box(bb.xmin, bb.xmax, bb.ymin, bb.ymax, z0, z1)
        ring, wall = _overlap_volume(printed, slab(5, 6)), _overlap_volume(printed, slab(50, 51))
        assert ring > wall, "the thick ring must be at the bottom of the print"

    def test_the_four_shells_are_mirror_images(self, parts):
        volumes = [_volume(parts[n]) for n in ("back_L", "back_R", "front_L", "front_R")]
        assert max(volumes) == pytest.approx(min(volumes), rel=1e-6)

    def test_a_shell_prints_wall_down_with_half_a_bin_floor_standing_on_it(self, parts):
        for name in ("back_L", "front_R"):
            bb = as_printed(name, parts[name], P).val().BoundingBox()
            assert bb.zlen == pytest.approx(P.plate_t + P.depth_at_base / 2, abs=4.0)

    def test_end_walls_are_split_so_the_lower_pieces_fit_the_bed(self, parts):
        lower = parts["back_L"].val().BoundingBox()
        upper = parts["upper_back"].val().BoundingBox()
        assert lower.ymax == pytest.approx(P.wall_split + P.wall_lap, abs=4)      # the walls lean with the fan
        assert upper.ymin == pytest.approx(P.wall_split, abs=4)
        assert lower.ymax - lower.ymin < P.bed[1]
        assert P.wall_split < -P.collar_h, "the seam is below the collar, where only the outermost channels pass"

    def test_the_two_wall_pieces_overlap_in_a_half_lap(self, parts):
        # same height range, different halves of the wall thickness: no clash
        assert P.wall_lap >= 8
        local_upper = _unplace(P, parts["upper_front"], P.n_channels - MID)
        lap_zone = _box(-P.px, P.px, P.wall_split + 1, P.wall_split + P.wall_lap - 1, -1, P.plate_t + 1)
        assert local_upper.intersect(lap_zone).val().BoundingBox().zlen == pytest.approx(P.plate_t / 2, abs=0.05)

    def test_bin_floor_halves_meet_on_the_centre_plane(self, parts):
        c = P.depth / 2
        assert parts["front_L"].val().BoundingBox().zmin == pytest.approx(c, abs=1e-6)
        assert parts["back_L"].val().BoundingBox().zmax == pytest.approx(c, abs=1e-6)

    def test_everything_is_flush_with_the_rim_and_the_table(self, parts):
        for name in ("slice_00", f"slice_{MID:02d}", "back_L", "front_R"):
            bb = parts[name].val().BoundingBox()
            assert bb.ymax <= 1e-6, name
            assert bb.ymin >= P.z_base - 1e-6, name

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
        assert P.width < 365
        assert P.height < 285            # taller than a 250 mm bed, which is why the end walls are in two pieces
        assert P.height + P.hopper_h < 375
        assert P.depth_at_base + 2 * P.plate_t < 185


# ------------------------------------------------ 7. shuffle (statistical model)
N = P.n_cards
MODEL = CombModel(cards_per_channel=P.cards_per_channel)
IDEAL = replace(MODEL, straggle=0.0)


class TestRepeatedDropsShuffleTheDeck:
    def test_cuts_account_for_every_card(self):
        rng = random.Random(1)
        for _ in range(200):
            sizes = cut_into_packets(N, MODEL, rng)
            assert sum(sizes) == N and min(sizes) >= 1

    def test_packets_are_six_or_seven_cards(self):
        rng = random.Random(2)
        sizes = [s for _ in range(200) for s in cut_into_packets(N, MODEL, rng)[1:-1]]
        assert set(sizes) <= {6, 7}

    def test_one_drop_loses_and_duplicates_nothing(self):
        left, right = one_pass(list(range(N)), MODEL, random.Random(3))
        assert sorted(left + right) == list(range(N))

    def test_piles_are_roughly_equal(self):
        rng = random.Random(4)
        sizes = [len(one_pass(list(range(N)), MODEL, rng)[0]) for _ in range(300)]
        assert 0.4 * N <= min(sizes) and max(sizes) <= 0.6 * N

    def test_without_stragglers_each_pile_keeps_its_cards_in_order(self):
        # ...which makes an ideal drop an inverse riffle shuffle.
        left, right = one_pass(list(range(N)), IDEAL, random.Random(5))
        assert left == sorted(left) and right == sorted(right)

    def test_a_straggler_moves_only_within_its_own_packet(self):
        left, right = one_pass(list(range(N)), replace(MODEL, straggle=1.0), random.Random(5))
        assert left != sorted(left) or right != sorted(right)
        for pile in (left, right):
            assert all(abs(a - b) <= 2 * 8 for a, b in zip(sorted(pile), pile))

    def test_restack_puts_left_on_right(self):
        assert restack([1, 2], [3]) == [1, 2, 3]

    def test_same_seed_same_shuffle(self):
        a = shuffle(list(range(N)), 8, MODEL, random.Random(6))
        b = shuffle(list(range(N)), 8, MODEL, random.Random(6))
        assert a == b and a != list(range(N))

    def test_neighbour_metric_endpoints(self):
        assert neighbours_kept(list(range(N))) == 1.0
        assert neighbours_kept(list(range(N - 1, -1, -1))) == 0.0

    def test_one_drop_separates_about_a_sixth_of_neighbours(self):
        assert 0.78 < mean_neighbours_kept(N, 1, MODEL, 300) < 0.88

    def test_more_drops_always_mix_more(self):
        kept = [mean_neighbours_kept(N, k, MODEL, 300) for k in (1, 3, 6, 10, 15)]
        assert kept == sorted(kept, reverse=True)

    def test_fifteen_drops_leave_under_a_tenth_of_neighbours_together(self):
        assert mean_neighbours_kept(N, 15, MODEL, 300) < 0.10

    def test_about_two_dozen_drops_is_indistinguishable_from_random_by_neighbours(self):
        assert 20 <= passes_needed(N, MODEL) <= 28

    def test_stragglers_were_doing_some_of_the_shuffling(self):
        # The jam-prone comb delayed a card at about half its cuts and needed
        # 13 drops.  Removing the jams removed that, and the price is more drops.
        assert passes_needed(N, replace(MODEL, straggle=0.45)) < 0.75 * passes_needed(N, MODEL)
        assert passes_needed(N, IDEAL) > passes_needed(N, MODEL)

    def test_after_eight_drops_any_card_can_be_anywhere(self):
        trials = 2000
        noise_floor = math.sqrt(N / (2 * math.pi * trials))
        assert position_bias(N, 8, MODEL, trials) < 1.15 * noise_floor

    def test_strict_alternation_beats_pairing_channels_up(self):
        paired = replace(MODEL, pattern="LLRR")
        assert mean_neighbours_kept(N, 6, MODEL, 300) < mean_neighbours_kept(N, 6, paired, 300)

    def test_restacking_habits_do_not_change_how_many_drops_are_needed(self):
        # Turning the deck round every other drop, putting either pile on top
        # at random, or cutting the deck: by 15 drops all mix the same.  Only
        # the packet size matters.
        def kept_after(habit, passes=15, trials=200):
            rng = random.Random(9)
            total = 0.0
            for _ in range(trials):
                deck = list(range(N))
                for k in range(passes):
                    left, right = one_pass(deck, MODEL, rng)
                    deck = left + right if (habit != "random" or rng.random() < 0.5) else right + left
                    if habit == "turn" and k % 2 == 0:
                        deck = deck[::-1]
                    if habit == "cut":
                        c = rng.randrange(N)
                        deck = deck[c:] + deck[:c]
                total += sum(1 for a, b in zip(deck, deck[1:]) if abs(a - b) == 1) / (N - 1)
            return total / trials
        plain = kept_after("plain")
        for habit in ("turn", "random", "cut"):
            assert kept_after(habit) == pytest.approx(plain, abs=0.03), habit

    def test_a_finer_comb_needs_fewer_drops(self):
        assert passes_needed(N, replace(MODEL, cards_per_channel=5.0)) < passes_needed(N, MODEL)


# --------------------------------------------------- 8. rigid-body physics
# MuJoCo drops rigid cards into the real geometry.  Two modelling choices
# change the outcome a great deal, so both are explicit:
#   card edges:  "round" (a sleeve's folded edge) or "flat" (a square-cut plate)
#   blade tips:  flexible one-layer films (blade_E = 2000 MPa, PETG) or rigid
# Thresholds are loose because contact dynamics are chaotic; the README has
# the 32-drop statistics.
physics_sim = pytest.importorskip("physics_sim")
pytest.importorskip("mujoco")
from physics_sim import COMB, ESCAPED, FLOP, PERCHED, Conditions  # noqa: E402

ROUND, FLAT = Conditions(card_bottom="round"), Conditions(card_bottom="flat")
SMOOTH = replace(ROUND, blade_steps=False)          # blades as a smooth taper: how versions 1 to 7 were tested
RIGID = replace(SMOOTH, blade_E=0.0)
SEEDS = (1, 2, 3)


def _drops(p, conditions=ROUND, seeds=SEEDS, n_cards=None):
    rig = physics_sim.Rig(p, n_cards=n_cards, conditions=conditions)
    deck = list(range(rig.n))
    return [rig.drop(deck, random.Random(s)) for s in seeds]


def _jammed(drops, *kinds):
    return sum(r.jam_types().get(k, 0) for r in drops for k in kinds)


@pytest.fixture(scope="module")
def drops():
    return _drops(P)


@pytest.fixture(scope="module")
def flat_drops():
    return _drops(P, FLAT)


class TestPhysicsEngineAgrees:
    def test_nearly_every_card_of_a_hundred_reaches_a_bin(self, drops):
        for r in drops:
            assert r.delivered >= 98

    def test_a_ninety_card_deck_works_too(self):
        for r in _drops(P, seeds=(1, 2), n_cards=90):
            assert r.delivered >= 88

    def test_nothing_jams_in_the_comb(self, drops):
        assert _jammed(drops, COMB) == 0

    def test_no_card_leaves_the_machine(self, drops, flat_drops):
        assert _jammed(drops + flat_drops, ESCAPED) == 0

    def test_square_edged_cards_can_perch_on_a_blade_tip_but_only_a_few(self, flat_drops):
        # A fault that is still there.  It needs a square, rigid card edge;
        # the card stays in the hopper in plain view.
        for r in flat_drops:
            assert r.delivered >= 95
            assert r.jam_types().get(PERCHED, 0) <= 4

    def test_piles_are_roughly_equal(self, drops):
        for r in drops:
            assert 38 <= len(r.left) <= 62 and 38 <= len(r.right) <= 62

    def test_even_channels_feed_the_left_bin_and_odd_the_right(self, drops):
        for r in drops:
            assert all(r.lane[c] % 2 == 0 for c in r.left)
            assert all(r.lane[c] % 2 == 1 for c in r.right)

    def test_packets_are_seven_cards_as_the_statistical_model_assumes(self, drops):
        for r in drops:
            sizes = [n for _, n in physics_sim.packets(list(range(P.n_cards)), r)]
            assert max(sizes) <= 9
            assert sum(6 <= n <= 8 for n in sizes) >= len(sizes) // 2

    def test_piles_are_in_order_apart_from_a_few_stragglers(self, drops):
        for r in drops:
            for pile in (r.left, r.right):
                out_of_order = sum(1 for a, b in zip(pile, pile[1:]) if b < a)
                assert out_of_order <= 5

    def test_one_drop_keeps_about_five_sixths_of_neighbours(self, drops):
        kept = [neighbours_kept(r.left + r.right + r.stuck) for r in drops]
        assert 0.75 < sum(kept) / len(kept) < 0.92

    def test_cards_settle_within_three_seconds(self, drops):
        assert all(r.settle_time < 3.0 for r in drops)

    def test_blade_tips_give_by_less_than_a_millimetre(self):
        import mujoco
        import numpy as np
        rig = physics_sim.Rig(P)
        rig.drop(list(range(rig.n)), random.Random(3), max_time=0.0)
        assert rig.q0 == P.n_channels, "one sprung hinge per blade tip"
        worst = 0.0
        while rig.data.time < 0.6:
            mujoco.mj_step(rig.model, rig.data, 25)
            worst = max(worst, float(np.abs(rig.data.qpos[:rig.q0]).max()))
        film = P.bevel_h / (round(P.blade_t / P.tip_land) - 1)
        assert 0.0 < math.sin(worst) * film < 1.0


# ----------------------------------- 9. faults found, reproduced on purpose
# Jams are occasional, so these run 8 or 16 drops each (in parallel) and
# compare rates.  Every threshold is well clear of what was measured.
# Versions 1 to 4 were 60-card machines tested with rigid blades, so they are
# reproduced that way.  Version 5 was the first 100-card machine.
SHORT_BINS = dict(ramp_deg=40.0, bin_extra=5.0)
SIXTY = replace(P, n_cards=60, n_channels=12, hopper_lean_deg=4.0, machine_tilt_deg=0.0, **SHORT_BINS)
V5 = replace(P, hopper_lean_deg=4.0, machine_tilt_deg=0.0, **SHORT_BINS)      # 100 cards, leaning hopper, level machine
V6 = replace(P, machine_tilt_deg=2.0, **SHORT_BINS)                           # machine leaning back, short shallow bins
OLD_BODY = dict(n_channels=14, hopper_lean_deg=0.0, fence_h=60.0, tube_clear=22.0, finger_slot=0.0)
V1 = replace(SIXTY, fan_R=0.0, blade_t=1.2, channel_w=3.5, tip_land=0.4, bevel_h=3.0, **OLD_BODY)
V2 = replace(SIXTY, fan_R=0.0, blade_t=0.8, channel_w=4.2, tip_land=0.2, bevel_h=2.0, **OLD_BODY)
RIGID_FLAT = replace(FLAT, blade_E=0.0, blade_steps=False)
FROM_THE_TOP = replace(ROUND, release_height=90.0)


def _score(p, conditions=ROUND, drops=16):
    return physics_sim.evaluate(p, conditions, range(1, drops + 1))


@pytest.fixture(scope="module")
def today():
    return _score(P)


@pytest.fixture(scope="module")
def v4():
    """The 60-card machine as it stood before the deck size changed, rigid blades."""
    return _score(SIXTY, RIGID)


class TestPhysicsExplainsTheDesign:
    """Each test is a version of the machine that failed, and how."""

    def test_today_sixteen_drops_of_a_hundred_cards_with_no_comb_jam(self, today):
        assert today.jams.get(COMB, 0) == 0
        assert today.clean >= 14
        assert today.delivered_frac > 0.995

    def test_v4_was_just_as_clean_with_sixty_cards(self, v4):
        assert v4.jams.get(COMB, 0) == 0
        assert v4.clean >= 14

    def test_v1_thick_parallel_blades_jam_most_of_the_deck(self):
        # Blades were 26% of their spacing.  The deck cannot spread that much
        # in the instant it is cut, so it fans out and locks.
        assert _score(V1, RIGID_FLAT, drops=8).delivered_frac < 0.70

    def test_v1_a_26mm_end_stop_lets_cards_somersault_out_of_the_bins(self):
        assert _score(replace(SIXTY, fence_h=26.0), RIGID, drops=8).jams.get(ESCAPED, 0) > 50

    def test_v2_thin_parallel_blades_pass_square_edges_but_jam_rounded_ones(self):
        # A square edge that does not fit is held out on the blade tip.  A
        # rounded edge wedges in.  So v2 only looked good with unrealistic cards.
        assert _score(V2, RIGID_FLAT).delivered_frac > 0.85
        assert _score(V2, RIGID).delivered_frac < 0.75

    def test_without_the_fan_todays_blades_jam(self):
        assert _score(replace(SIXTY, fan_R=0.0), RIGID, drops=8).delivered_frac < 0.75

    def test_too_strong_a_fan_squeezes_the_tops_of_the_packets_together(self):
        strong = _score(replace(SIXTY, fan_R=250.0), RIGID)
        assert strong.jam_drops.get(COMB, 0) >= 2

    def test_a_blade_that_thickens_too_quickly_narrows_its_channel_and_jams(self):
        short_taper = replace(SIXTY, bevel_h=20.0)
        z = P.tip_z(MID)
        assert short_taper.channel_width(MID, z - 20) < short_taper.channel_width(MID, z)
        assert _score(short_taper, RIGID).delivered_frac < 0.60

    def test_an_upright_hopper_leaves_more_stray_cards_than_a_leaning_one(self, v4):
        upright = _score(replace(SIXTY, hopper_lean_deg=0.0), RIGID)
        assert upright.clean < v4.clean

    def test_v3_a_60mm_stop_holds_until_the_deck_is_dropped_from_the_top_of_the_hopper(self, v4):
        from_the_top = replace(RIGID, release_height=90.0)
        assert v4.jams.get(ESCAPED, 0) == 0
        over_the_60mm_stop = _score(replace(SIXTY, fence_h=60.0), from_the_top, drops=8).jams.get(ESCAPED, 0)
        over_the_full_fence = _score(SIXTY, from_the_top, drops=8).jams.get(ESCAPED, 0)
        assert over_the_60mm_stop >= over_the_full_fence + 5

    def test_v4_looked_hopeless_on_tight_decks_only_because_its_blades_were_modelled_rigid(self):
        # With a tenth of the deck air, a packet plus half a card is as wide as
        # the mouth of a channel.  A rigid knife jams; a one-layer printed tip
        # gives by a fraction of a millimetre and lets it through.
        tight = replace(ROUND, card_t=0.63)
        narrowest = min(P.channel_width(i, P.tip_z(i)) for i in range(P.n_channels))
        assert narrowest - (P.cards_per_channel + 0.5) * tight.card_t < 0.1     # no margin left
        assert _score(P, replace(tight, blade_E=0.0, blade_steps=False), drops=8).delivered_frac < 0.92
        assert _score(P, tight, drops=8).delivered_frac > 0.98


class TestTheHundredCardMachine:
    """What changed between version 5 and today, and why."""

    def test_v5_locked_solid_when_the_deck_was_dropped_from_the_top_of_the_hopper(self):
        assert _score(V5, replace(SMOOTH, release_height=90.0), drops=8).delivered_frac < 0.90

    def test_today_a_drop_from_the_top_never_jams_the_comb(self):
        from_the_top = _score(P, FROM_THE_TOP)
        assert from_the_top.jams.get(COMB, 0) == 0
        assert from_the_top.delivered_frac > 0.99
        assert from_the_top.clean >= 14

    def test_v6_short_shallow_bins_left_cards_under_the_tower_for_later_ones_to_catch_on(self, today):
        from_the_top_v6 = _score(V6, replace(SMOOTH, release_height=90.0))
        from_the_top_today = _score(P, FROM_THE_TOP)
        assert sum(from_the_top_v6.jams.values()) >= sum(from_the_top_today.jams.values()) + 5
        assert today.clean >= 15

    def test_v6_needed_its_lean_only_because_of_those_bins(self, today):
        # With short bins a level machine left more stray cards than a leaning
        # one.  With today's bins a level machine leaves none, so it is level.
        v6_level = _score(replace(V6, machine_tilt_deg=0.0), SMOOTH, drops=32)
        v6_leaning = _score(V6, SMOOTH, drops=32)
        assert sum(v6_level.jams.values()) >= sum(v6_leaning.jams.values()) + 4
        assert sum(today.jams.values()) == 0


class TestBladesAsPrinted:
    """Version 7 modelled each blade as a smooth taper.  Printed, it thickens one layer at a time."""

    def test_coarse_layer_steps_on_the_blade_faces_catch_a_tight_deck(self):
        nearly_solid = replace(ROUND, card_t=0.66)
        coarse = _score(replace(P, layer_h=0.2), nearly_solid, drops=8)
        fine = _score(P, nearly_solid, drops=8)
        assert coarse.delivered_frac < fine.delivered_frac - 0.04


class TestTriedAndRejected:
    """Ideas that looked promising and failed in simulation."""

    def test_a_second_row_of_short_blades_cannot_take_an_uneven_split(self):
        # A short blade halfway down cuts each packet wherever it happens to
        # land, so one side often gets most of it, and its lane is only half a
        # channel wide.  The lanes would need a fan hinged ~80 mm up to fit.
        two_stage = replace(P, n_channels=32, channel_w=2.6, blade_t=0.4, sub_blade_z=-80.0)
        assert _drops(two_stage, seeds=(1,))[0].delivered < 80

    def test_a_one_layer_blade_tip_is_too_floppy_for_a_tight_deck(self):
        nearly_solid = replace(ROUND, card_t=0.66)
        assert (_score(replace(P, tip_land=0.1), nearly_solid, drops=8).delivered_frac
                < _score(P, nearly_solid, drops=8).delivered_frac)


class TestKnownLimits:
    """Faults that are still there.  These tests document them; they do not excuse them."""

    def test_a_deck_squeezed_nearly_solid_still_loses_a_few_cards(self):
        nearly_solid = _score(P, replace(ROUND, card_t=0.66), drops=8)
        assert 0.85 < nearly_solid.delivered_frac < 0.995

    def test_square_edged_cards_perch_in_a_fair_share_of_drops(self):
        assert _score(P, FLAT, drops=8).jam_drops.get(PERCHED, 0) >= 2

    def test_perching_fades_as_the_bottom_edge_gets_rounder(self):
        # A sleeve's folded edge is about fully round (radius = half the
        # thickness) and never perches.  The machine cannot fix a square edge.
        square = _score(P, replace(FLAT, blade_steps=False), drops=16)
        rounded = _score(P, replace(FLAT, blade_steps=False, edge_radius=0.2), drops=16)
        assert rounded.clean > square.clean
