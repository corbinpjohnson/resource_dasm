"""Gravity comb shuffler for sleeved cards - parametric design.

How it works (see README.md for pictures):

* A deck of up to 100 sleeved cards is lowered or dropped, short edge down,
  into a HOPPER whose throat ring holds it upright.
* Under it is a COMB of thin blades that slices the deck into packets of
  about seven cards.  Three things about the comb were forced by the physics
  test (physics_sim.py) and none of them is optional:
    - the blades are arranged like the ribs of a FAN, hinged far above the
      rim, so the card bottoms can spread by the total thickness of the
      blades while the tops stay together, and every channel gets wider on
      the way down;
    - each blade TAPERS from a one-layer tip to full thickness slowly enough
      that its channel never narrows: whatever the tips let in can fall;
    - the tips form a CHEVRON with one centre blade highest, so the deck is
      split one blade at a time.
* Each CHANNEL between two blades has a sloping floor (RAMP).  Ramps
  alternate: left, right, left, right...  A packet free-falls one card height,
  lands on its ramp, tips over onto its short edge and slides out sideways.
* Two tilted BINS catch the left-going and right-going cards.
* Stack one pile on the other and drop again.

Every part prints flat without supports:

    slice_NN   blade + ramp rib + spacers, one per channel; the spacers are
               slightly wedge-shaped, which is what builds the fan
    back_L/R   half of an end wall with half of a bin floor and end stop
    front_L/R  the mirror images
    bar_*      square tie bars (three lengths) with a slot for ...
    wedge      ... a tapered key that clamps the whole stack (no screws)
    foot       cross-lapped outrigger so the tower cannot tip
    hopper     sits on the rim and holds the deck upright while it is released
    jam_key    a stick for pushing a stuck card down its channel

Frame used in this file:  x = across the card face, z = up (0 at the rim),
w = depth (the direction the cards are stacked in).  2-D outlines are lists
of (x, z).  CadQuery is only needed for `build_parts`; all the numbers work
without it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]


@dataclass(frozen=True)
class Params:
    # --- the cards -------------------------------------------------------
    sleeve_w: float = 67.0        # sleeved card, short side
    sleeve_h: float = 92.0        # sleeved card, long side
    card_pitch: float = 0.70      # deck thickness per sleeved card
    n_cards: int = 100            # the largest deck it must take; 90 works too

    # --- the comb --------------------------------------------------------
    n_channels: int = 18          # must be even: half go left, half right.  No more than the
                                  # deck needs: a narrower collar limits how far a deck can lean
    channel_w: float = 4.0        # gap between blades at the rim, below the taper
    blade_t: float = 1.0          # full thickness, reached only well down the blade
    tip_land: float = 0.2         # width of the blade tip: a single layer
    bevel_h: float = 110.0        # height over which a blade thickens from tip to full.  With
                                  # the fan this keeps every channel widening all the way down
    chevron_step: float = 3.5     # each blade's tip is this much lower than its inner neighbour
    blade_outside: bool = False   # True puts each blade on the outer side of its own channel with
                                  # an extra divider in the middle.  Tried, to move the layer steps
                                  # off the wall cards ride on; worse, because the taper then
                                  # pushes cards inwards
    layer_h: float = 0.1          # layer height the comb slices are printed at.  The blade thickens
                                  # by this much at each step, and each step is a small ledge on
                                  # the wall cards slide down: at 0.2 mm they catch tight packets
    centre_drop: float = 0.0      # the second of the two middle blades starts this much lower,
                                  # so the first cut is made by one blade, not two back to back
    roof_deg: float = 12.0        # (rake_deg = 0 only) blade top slopes away from a central peak
    rake_deg: float = 0.0         # blade top is one straight slope across the card, alternate
                                  # blades sloping opposite ways, so each blade enters the deck
                                  # from one side like a scissor instead of all along its length
    tip_guard: float = 6.0        # highest tip sits this far below the rim
    fan_R: float = 400.0          # 0: blades parallel.  Otherwise the blades are tilted like the
                                  # ribs of a fan whose hinge is this far above the rim, so every
                                  # channel gets wider on the way down

    # --- the path of a card ----------------------------------------------
    side_clear: float = 1.5       # collar clearance each side of the card
    ear_w: float = 12.0           # width of the collar walls
    exit_clear: float = 3.0       # blades extend this far past the collar
    boss_short: float = 14.0      # collar wall height on the side a card leaves by
    fall_clear: float = 3.0       # extra free fall beyond one card height
    ramp_deg: float = 46.0        # steep enough that cards reach the fence even when they rub
    friction_deg: float = 22.0    # pessimistic sleeve-on-PLA friction angle
    rib_d: float = 16.0           # depth of the rib that carries a ramp
    bar_x: float = 18.0           # lower tie bars sit this far off centre

    # --- the bins --------------------------------------------------------
    bin_extra: float = 35.0       # bin length beyond one card width.  Generous, so that a card
                                  # which stops short is still clear of the comb: one left with a
                                  # corner under the tower is what later cards got caught on
    bin_gap: float = 0.5          # gap between comb and bin floor
    bin_step: float = 0.6         # bin floor is this much lower than the ramp (no lip)
    floor_t: float = 3.0
    stop_h: float = 26.0          # the solid block the bin tie bar passes through
    fence_h: float = 96.0         # thin fence above it, taller than a card: a deck dropped from
                                  # the top of the hopper sends cards over anything lower
    fence_t: float = 3.0
    stop_t: float = 14.0
    wall_h: float = 58.0          # bin side walls, measured square to the floor
    notch_w: float = 28.0         # finger notch
    notch_floor: float = 22.0

    # --- the hopper (sits on top, keeps the deck upright) -----------------
    hopper_h: float = 92.0        # walls all round, with a throat ring at the top
    throat_clear: float = 6.0     # throat depth = deck thickness + this
    tube_clear: float = 6.0       # below the ring the hopper is this much deeper than the throat:
                                  # tight enough that the deck cannot lean more than about 4 degrees
    throat_h: float = 32.0        # the ring holds the top of the deck upright at release; below
                                  # it the hopper is as deep as the comb so cards can spread
    hopper_t: float = 2.4
    hopper_lean_deg: float = 0.0  # the hopper stands square on the comb.  Leaning it (4 degrees, in
                                  # version 5) tilts the cards against half the channels and locks
                                  # the whole deck when it is dropped from a height
    machine_tilt_deg: float = 0.0  # the machine stands level.  Leaning the whole machine back two
                                  # degrees (version 6) stopped cards arriving late, but so do
                                  # bins long and steep enough to clear the tower, and those also
                                  # cope with the deck being dropped in
    finger_slot: float = 54.0     # depth of the slots in the hopper sides, for lowering the deck
                                  # in by its edges (holding it by its faces squeezes it tight)
    post_w: float = 9.0           # width of the corner posts left beside each slot
    tab_h: float = 10.0

    # --- structure -------------------------------------------------------
    plate_t: float = 3.0
    wall_split: float = -60.0     # each end wall is two pieces, lapped at this height, so that
                                  # the lower one fits a 250 mm bed
    wall_lap: float = 10.0
    bar: float = 6.0              # tie bar is bar x bar
    fit: float = 0.2              # clearance per side for anything that slides together
    head_t: float = 3.0
    tail: float = 14.0
    slot_w: float = 2.4
    slot_len: float = 8.0
    wedge_t: float = 2.0
    wedge_len: float = 30.0
    wedge_narrow: float = 4.0
    wedge_wide: float = 8.5
    foot_x: float = 85.0
    foot_w: float = 10.0
    foot_h: float = 12.0
    foot_out: float = 20.0        # how far a foot sticks out front and back
    ground: float = 3.0

    # --- the printer -----------------------------------------------------
    bed: tuple[float, float, float] = (250.0, 250.0, 250.0)
    nozzle: float = 0.4

    # ================= derived: deck and comb ============================
    @property
    def deck_t(self) -> float:
        return self.n_cards * self.card_pitch

    @property
    def pitch(self) -> float:
        return self.channel_w + self.blade_t

    @property
    def depth(self) -> float:
        """Inside depth of the machine = collar opening in the stacking direction."""
        return self.n_channels * self.pitch

    @property
    def capacity(self) -> float:
        """Total card thickness the channels can swallow."""
        return self.n_channels * self.channel_w

    @property
    def cards_per_channel(self) -> float:
        """Cards between two neighbouring blade tips = size of a packet."""
        return self.pitch / self.card_pitch

    # ---- the fan ---------------------------------------------------------
    @property
    def fan_delta(self) -> float:
        """Angle between neighbouring blades, radians (0 when parallel)."""
        return self.pitch / self.fan_R if self.fan_R > 0 else 0.0

    def spread(self, z: float) -> float:
        """How much wider everything is at height z than at the rim."""
        return 1.0 - z / self.fan_R if self.fan_R > 0 else 1.0

    def channel_at(self, z: float, blade_t: float | None = None) -> float:
        """Width of a channel at height z (z = 0 at the rim, negative below)."""
        return self.pitch * self.spread(z) - (self.blade_t if blade_t is None else blade_t)

    def blade_thickness(self, i: int, z: float) -> float:
        """Thickness of blade i at height z: one layer at its tip, full thickness bevel_h lower."""
        grown = min(1.0, max(0.0, (self.tip_z(i) - z) / self.bevel_h))
        return self.tip_land + (self.blade_t - self.tip_land) * grown

    def channel_width(self, i: int, z: float) -> float:
        """Clear width of the channel beside blade i at height z."""
        return self.pitch * self.spread(z) - self.blade_thickness(i, z)

    @property
    def depth_at_base(self) -> float:
        """Inside depth of the machine at table level (the fan makes it deeper than at the rim)."""
        return self.depth * self.spread(self.z_base)

    def lane_of(self, w: float, z: float) -> int:
        """Which channel a point at depth w and height z is in."""
        c = self.depth / 2
        if self.fan_R > 0:
            idx = math.atan2(w - c, self.fan_R - z) / self.fan_delta
        else:
            idx = (w - c) / self.pitch
        return self.n_channels // 2 + math.floor(idx)

    def side(self, i: int) -> str:
        """Which bin channel i feeds."""
        return "LR"[i % 2]

    def slice_plane(self, i: int) -> tuple[int, int]:
        """Where slice i sits on the fan: (plane, direction).

        `plane` counts blade spacings from the centre plane; the flat back of
        the slice's blade lies on it.  `direction` is +1 if the blade's body and
        the rest of the slice extend towards the front from there, -1 if
        towards the back.
        """
        mid = self.n_channels // 2
        if self.blade_outside:
            return (i - mid + 1, -1) if i >= mid else (-(mid - i), +1)
        return (i - mid, +1) if i >= mid else (-(mid - 1 - i), -1)

    def blade_in_front(self, i: int) -> bool:
        """True if slice i is the mirror image of the basic slice (direction -1)."""
        return self.slice_plane(i)[1] < 0

    def blade_w(self, i: int) -> tuple[float, float]:
        """Depth range occupied by blade i at the rim."""
        plane, d = self.slice_plane(i)
        w = self.depth / 2 + plane * self.pitch
        return tuple(sorted((w, w + d * self.blade_t)))

    def channel_range(self, i: int) -> tuple[float, float]:
        """Depth range of channel i at the rim."""
        plane, d = self.slice_plane(i)
        w = self.depth / 2 + plane * self.pitch
        return tuple(sorted((w + d * self.blade_t, w + d * self.pitch)))

    def tip_z(self, i: int) -> float:
        """Height of the peak of blade i: a chevron, highest in the middle."""
        mid = self.n_channels // 2
        if self.blade_outside:
            return -self.tip_guard - self.chevron_step * abs(self.slice_plane(i)[0])
        if i == mid - 1 and self.centre_drop > 0:
            return -self.tip_guard - self.centre_drop
        return -self.tip_guard - self.chevron_step * abs(i - mid)

    # ================= derived: outline in x ============================
    @property
    def cx(self) -> float:
        """Half-width of the collar opening."""
        return self.sleeve_w / 2 + self.side_clear

    @property
    def px(self) -> float:
        """Half-width of the tower."""
        return self.cx + self.ear_w

    @property
    def bx(self) -> float:
        """Half-width of a blade below the collar."""
        return self.cx + self.exit_clear

    def top_from_peak(self, peak: float, parity: int = 0) -> list[Point]:
        """Top edge of a blade whose highest point is at `peak`, left to right."""
        if self.rake_deg > 0:
            drop = 2 * self.cx * math.tan(math.radians(self.rake_deg))
            ends = (peak, peak - drop) if parity % 2 == 0 else (peak - drop, peak)
            return [(-self.cx, ends[0]), (self.cx, ends[1])]
        eave = peak - self.cx * math.tan(math.radians(self.roof_deg))
        return [(-self.cx, eave), (0.0, peak), (self.cx, eave)]

    def blade_top(self, i: int) -> list[Point]:
        """Top edge of blade i across the collar opening, left to right."""
        return self.top_from_peak(self.tip_z(i), i)

    def divider_top(self) -> list[Point]:
        """Top edge of the extra blade in the middle: the one that leads."""
        return self.top_from_peak(-self.tip_guard)

    @property
    def top_drop(self) -> float:
        """How far a blade's top edge falls from its highest to its lowest point."""
        zs = [z for _, z in self.blade_top(0)]
        return max(zs) - min(zs)

    @property
    def collar_h(self) -> float:
        """Deep enough that every blade edge ends inside the collar."""
        deepest = -min(self.tip_z(i) for i in range(self.n_channels))
        return deepest + self.top_drop + 6.0

    # ================= derived: heights =================================
    @property
    def tan_ramp(self) -> float:
        return math.tan(math.radians(self.ramp_deg))

    @property
    def free_fall(self) -> float:
        """Drop from the bottom of the exit-side collar wall to the top of a ramp."""
        return self.sleeve_h + self.fall_clear

    @property
    def z_hi(self) -> float:
        """Top end of every ramp."""
        return -self.boss_short - self.free_fall

    def ramp_z(self, x: float, side: str) -> float:
        """Height of the ramp surface at x.  'L' ramps descend towards -x."""
        run = (self.bx - x) if side == "L" else (self.bx + x)
        return self.z_hi - run * self.tan_ramp

    @property
    def z_lo(self) -> float:
        """Bottom end of a ramp, at the edge of the blades."""
        return self.ramp_z(-self.bx, "L")

    @property
    def z_cross(self) -> float:
        """Where left and right ramps cross, on the centre line."""
        return self.ramp_z(0.0, "L")

    @property
    def bar_z_low(self) -> float:
        return self.ramp_z(self.bar_x, "R") - self.rib_d / 2

    @property
    def bar_z_ear(self) -> float:
        return -self.boss_short / 2

    @property
    def hole(self) -> float:
        return self.bar + 2 * self.fit

    # ================= derived: bins ====================================
    @property
    def bin_len(self) -> float:
        return self.sleeve_w + self.bin_extra

    @property
    def bin_origin(self) -> Point:
        """Top of the LEFT bin floor."""
        x = -self.bx - self.bin_gap
        return (x, self.ramp_z(x, "L") - self.bin_step)

    def bin_pt(self, s: float, n: float, side: str = "L") -> Point:
        """Point s along the left bin floor (downhill) and n square above it."""
        a = math.radians(self.ramp_deg)
        ox, oz = self.bin_origin
        x = ox - s * math.cos(a) - n * math.sin(a)
        z = oz - s * math.sin(a) + n * math.cos(a)
        return (x if side == "L" else -x, z)

    @property
    def bin_bar(self) -> Point:
        return self.bin_pt(self.bin_len + self.stop_t / 2, 11.0)

    @property
    def z_base(self) -> float:
        return self.bin_pt(self.bin_len + self.stop_t, -self.floor_t)[1] - self.ground

    @property
    def height(self) -> float:
        return -self.z_base

    @property
    def width(self) -> float:
        corners = [self.bin_pt(self.bin_len + self.stop_t, self.wall_h), self.bin_pt(self.bin_len + self.fence_t, self.fence_h)]
        return 2 * max(self.px, *(-x for x, _ in corners))

    @property
    def wedge_deg(self) -> float:
        return math.degrees(math.atan((self.wedge_wide - self.wedge_narrow) / self.wedge_len))

    # ================= 2-D outlines =====================================
    def blade_outline(self, i: int) -> list[Point]:
        """Blade i seen face-on."""
        shoulder = -self.collar_h - (self.px - self.bx)
        bottom = self.z_lo - self.rib_d
        return [(-self.px, 0.0), (-self.cx, 0.0), *self.blade_top(i), (self.cx, 0.0), (self.px, 0.0),
                (self.px, -self.collar_h), (self.bx, shoulder), (self.bx, bottom),
                (0.0, self.z_cross - self.rib_d), (-self.bx, bottom),
                (-self.bx, shoulder), (-self.px, -self.collar_h)]

    def above_taper_line(self, i: int, lower_by: float) -> list[Point]:
        """Region removed from an upper layer of blade i: everything above its top edge lowered by `lower_by`.

        The line runs the full width of the blade, ears included, so the face
        of the blade stays flush.  A step there catches cards as they swing
        out sideways (it did, in the physics test).
        """
        top = [(x, z - lower_by) for x, z in self.blade_top(i)]
        far = self.px + 5.0
        return [(-far, 20.0), (-far, top[0][1]), *top, (far, top[-1][1]), (far, 20.0)]

    def rib_outline(self, side: str, x0: float | None = None, x1: float | None = None) -> list[Point]:
        """The band of material whose top edge is a ramp (optionally just a piece)."""
        x0 = -self.bx if x0 is None else x0
        x1 = self.bx if x1 is None else x1
        return [
            (x0, self.ramp_z(x0, side)), (x1, self.ramp_z(x1, side)),
            (x1, self.ramp_z(x1, side) - self.rib_d), (x0, self.ramp_z(x0, side) - self.rib_d),
        ]

    def collar_wall(self, x_sign: int, full: bool) -> list[Point]:
        """Spacer in the collar; short on the side a card leaves by."""
        h = self.collar_h if full else self.boss_short
        a, b = sorted((x_sign * self.cx, x_sign * self.px))
        return [(a, 0.0), (b, 0.0), (b, -h), (a, -h)]

    def bar_holes(self) -> list[Point]:
        """Centres of the four tie bars that pass through every slice."""
        ex = self.cx + self.ear_w / 2
        return [(-ex, self.bar_z_ear), (ex, self.bar_z_ear),
                (-self.bar_x, self.bar_z_low), (self.bar_x, self.bar_z_low)]

    def bin_floor_outline(self, side: str = "L") -> list[Point]:
        L, t = self.bin_len, self.stop_t
        # The top end is cut plumb so the floor's underside stays clear of the comb.
        plumb = self.floor_t * self.tan_ramp
        sn = [(0, 0), (L, 0), (L, self.fence_h), (L + self.fence_t, self.fence_h), (L + self.fence_t, self.stop_h),
              (L + t, self.stop_h), (L + t, -self.floor_t), (plumb, -self.floor_t)]
        return [self.bin_pt(s, n, side) for s, n in sn]

    def wall_outlines(self, side: str = "L") -> list[list[Point]]:
        """Pieces whose union is one half of an end wall."""
        sg = -1 if side == "L" else 1
        end = self.bin_len + self.stop_t
        tower = [(sg * self.px, 0.0), (0.0, 0.0), (0.0, self.z_base), (sg * self.px, self.z_base)]
        bin_wall = [self.bin_pt(s, n, side) for s, n in
                    [(-15, -self.floor_t), (end, -self.floor_t), (end, self.wall_h), (-15, self.wall_h)]]
        low = self.bin_pt(end, -self.floor_t, side)
        skirt = [(0.0, self.z_base), self.bin_pt(-15, -self.floor_t, side), low, (low[0], self.z_base)]
        return [tower, bin_wall, skirt]

    def finger_notch(self, side: str = "L") -> list[Point]:
        mid = self.bin_len / 2 + 2
        sn = [(mid - self.notch_w / 2, self.notch_floor), (mid + self.notch_w / 2, self.notch_floor),
              (mid + self.notch_w / 2, self.wall_h + 5), (mid - self.notch_w / 2, self.wall_h + 5)]
        return [self.bin_pt(s, n, side) for s, n in sn]

    def resting_card(self, side: str = "L") -> list[Point]:
        """A card at rest in a bin: on its short edge, against the stop."""
        L = self.bin_len
        sn = [(L - self.sleeve_w, 0), (L, 0), (L, self.sleeve_h), (L - self.sleeve_w, self.sleeve_h)]
        return [self.bin_pt(s, n, side) for s, n in sn]

    # ---- hopper outlines -------------------------------------------------
    @property
    def throat(self) -> float:
        return self.deck_t + self.throat_clear

    @property
    def tube_inset(self) -> float:
        """How far the hopper's front and back walls stand inside the comb's."""
        return max(0.0, (self.depth - self.throat - self.tube_clear) / 2)

    def hopper_shear(self, z: float) -> float:
        """How far back the leaning hopper has moved at height z (nothing at the rim)."""
        return -z * math.tan(math.radians(self.hopper_lean_deg))

    def hopper_end_pieces(self, front: bool) -> list[list[Point]]:
        """Front/back end of the hopper as two convex pieces in (w, z): wall, then throat ring."""
        inset = (self.depth - self.throat) / 2
        top, lo, t = self.hopper_h, self.hopper_h - self.throat_h, self.hopper_t
        wall = [(-t, 0.0), (self.tube_inset, 0.0), (self.tube_inset, lo), (-t, lo)]
        ring = [(-t, lo), (inset, lo), (inset, top - 2.0), (inset - 2.0, top), (-t, top)]
        pieces = [[(self.depth - w, z) for w, z in pc] for pc in (wall, ring)] if front else [wall, ring]
        return [[(w + self.hopper_shear(z), z) for w, z in pc] for pc in pieces]

    def hopper_end_wz(self, front: bool) -> list[Point]:
        """Outline of the same thing in one piece."""
        wall, ring = self.hopper_end_pieces(front)
        return wall[:3] + ring[1:]

    def hopper_return(self, x_sign: int, front: bool) -> tuple[list[Point], float, float]:
        """Hook on a hopper corner that grips the outside of the tower.

        Returns its (x, z) outline and depth range.  It is a 45 degree wedge so
        it prints without support, sits outboard of the tie-bar wedges, and has
        extra clearance because the end walls lean.
        """
        out, reach = self.px + self.fit, 3.2
        pts = [(out + self.hopper_t, 6.0), (out + self.hopper_t, -reach), (out - reach, -reach), (out, 0.0), (out, 6.0)]
        a, b = self.plate_t + self.fit + 0.5, self.plate_t + self.fit + 0.5 + self.hopper_t
        w0, w1 = (self.depth + a, self.depth + b) if front else (-b, -a)
        return [(x_sign * x, z) for x, z in pts], w0, w1

    def hopper_lug(self, x_sign: int) -> tuple[float, float, float, float, float, float]:
        """Strip down the outside of the tower that carries the hooks: (x0, x1, z0, z1, w0, w1)."""
        out = self.px + self.fit
        b = self.plate_t + self.fit + 0.5 + self.hopper_t
        x0, x1 = sorted((x_sign * out, x_sign * (out + self.hopper_t)))
        return (x0, x1, -self.tab_h, 6.0, -b, self.depth + b)

    def hopper_side_xz(self, x_sign: int) -> list[Point]:
        """Side wall: stands on the collar wall and hooks over the tower side."""
        t, out = self.hopper_t, self.px + self.fit
        pts = [(self.cx, 0.0), (self.cx, self.hopper_h), (self.cx + t, self.hopper_h),
               (self.cx + t, 6.0 + (out + t - self.cx - t)), (out + t, 6.0),
               (out + t, -self.tab_h), (out, -self.tab_h), (out, 0.0)]
        return [(x_sign * x, z) for x, z in pts]

    def landing_card_top(self) -> float:
        """Top of a card at the instant its corner touches the top of a ramp."""
        return self.ramp_z(self.sleeve_w / 2, "L") + self.sleeve_h


# ==========================================================================
# Solids (CadQuery).  Model frame: X = x, Y = z (up), Z = w (depth).
# ==========================================================================

def _prism(pts, w0, w1):
    import cadquery as cq
    return cq.Workplane("XY").workplane(offset=w0).polyline(pts).close().extrude(w1 - w0)


def _box(x0, x1, z0, z1, w0, w1):
    return _prism([(x0, z0), (x1, z0), (x1, z1), (x0, z1)], w0, w1)


def _square(c: Point, size: float) -> list[Point]:
    h = size / 2
    return [(c[0] - h, c[1] - h), (c[0] + h, c[1] - h), (c[0] + h, c[1] + h), (c[0] - h, c[1] + h)]


# ---- placing things on the fan -------------------------------------------
# Slices and end walls are modelled lying on the centre plane (w = 0 here) and
# then moved to their place `steps` blade spacings from the centre: a rotation
# about the hinge line for a fan comb, a plain shift for a parallel one.

def _place(p: Params, solid, steps: float):
    c = p.depth / 2
    solid = solid.translate((0, 0, c))
    if p.fan_R > 0:
        return solid.rotate((0, p.fan_R, c), (1, p.fan_R, c), -math.degrees(steps * p.fan_delta))
    return solid.translate((0, 0, steps * p.pitch))


def _unplace(p: Params, solid, steps: float):
    c = p.depth / 2
    if p.fan_R > 0:
        solid = solid.rotate((0, p.fan_R, c), (1, p.fan_R, c), math.degrees(steps * p.fan_delta))
    else:
        solid = solid.translate((0, 0, -steps * p.pitch))
    return solid.translate((0, 0, -c))


def _beyond(p: Params, steps: float, thick: float = 500.0):
    """Everything on the far side of the fan plane `steps` out from the centre (local frame)."""
    slab = _box(-400, 400, p.z_base - 60, 30, 0, thick)
    if p.fan_R > 0:
        return slab.rotate((0, p.fan_R, 0), (1, p.fan_R, 0), -math.degrees(steps * p.fan_delta))
    return slab.translate((0, 0, steps * p.pitch))


def _trim(p: Params, solid):
    """Cut flush with the rim and the table."""
    solid = solid.cut(_box(-400, 400, 0, 60, -300, 400))
    return solid.cut(_box(-400, 400, p.z_base - 80, p.z_base, -300, 400))


def slice_steps(p: Params, i: int) -> int:
    mid = p.n_channels // 2
    return -(mid - 1 - i) if p.blade_in_front(i) else i - mid


def _bar_cut(p: Params, at: Point):
    return _prism(_square(at, p.hole), -300, 400)


def build_slice(p: Params, i: int):
    """Blade i plus everything that fills channel i, in its assembled position."""
    side = p.side(i)
    other = "R" if side == "L" else "L"
    exit_sign = -1 if side == "L" else 1
    thick = p.pitch * p.spread(p.z_base) + 2      # more than the widest the channel gets

    # Blade: tip_land thick at the tip, gaining one printed layer at a time on the way down.
    n_terr = max(1, round((p.blade_t - p.tip_land) / p.layer_h))
    outline = p.blade_outline(i)
    body = _prism(outline, 0.0, p.tip_land)
    for k in range(1, n_terr + 1):
        a = p.tip_land + (k - 1) * p.layer_h
        lam = _prism(outline, a, a + p.layer_h)
        body = body.union(lam.cut(_prism(p.above_taper_line(i, k * p.bevel_h / n_terr), a - 1, a + 1)))

    # Ramp rib, a short piece of the opposite rib (spacer round the far tie
    # bar) and the collar walls, all filling the channel up to the next blade.
    x_far = -exit_sign * p.bar_x
    fill = [p.rib_outline(side), p.rib_outline(other, x_far - 8, x_far + 8),
            p.collar_wall(-exit_sign, full=True), p.collar_wall(exit_sign, full=False)]
    for pts in fill:
        body = body.union(_prism(pts, 0.0, thick))
    body = body.cut(_beyond(p, 1))

    # Index mark: when stacked in order the marks form one diagonal line.
    zm = -p.collar_h - 20 - 2.5 * i
    body = body.cut(_box(p.bx - 1.5, p.bx + 1, zm - 1, zm + 1, -1, thick))
    if p.blade_in_front(i):
        body = body.mirror("XY")
    body = _trim(p, _place(p, body, slice_steps(p, i)))
    for c in p.bar_holes():
        body = body.cut(_bar_cut(p, c))
    return body


def build_hopper(p: Params):
    """Tube with a throat ring and finger slots; sits on the rim."""
    import cadquery as cq
    back = min(0.0, p.hopper_shear(p.hopper_h)) - p.hopper_t     # how far the lean carries the top
    body = None
    for sg in (-1, 1):
        # The side wall stands on the collar walls only, clear of the tie-bar wedges.
        side = _prism(p.hopper_side_xz(sg), back, p.depth).union(_box(*p.hopper_lug(sg)))
        lo, hi = sorted((sg * (p.cx - 1), sg * (p.cx + p.hopper_t + 1)))
        slot_z = p.hopper_h - p.finger_slot
        slot = (cq.Workplane("YZ").workplane(offset=lo)
                .polyline([(slot_z, p.post_w + p.hopper_shear(slot_z)), (slot_z, p.depth - p.post_w + p.hopper_shear(slot_z)),
                           (p.hopper_h + 1, p.depth - p.post_w + p.hopper_shear(p.hopper_h + 1)),
                           (p.hopper_h + 1, p.post_w + p.hopper_shear(p.hopper_h + 1))]).close().extrude(hi - lo))
        side = side.cut(slot)
        body = side if body is None else body.union(side)
        for front in (False, True):
            pts, w0, w1 = p.hopper_return(sg, front)
            body = body.union(_prism(pts, w0, w1))
    reach = p.cx + p.hopper_t
    for front in (False, True):
        end = (cq.Workplane("YZ").workplane(offset=-reach)
               .polyline([(z, w) for w, z in p.hopper_end_wz(front)]).close().extrude(2 * reach))
        body = body.union(end)
    # nothing may hang inside the collar or outside the back wall below the rim
    return body.cut(_box(-p.cx, p.cx, -50, 0, -50, p.depth + 50))


def build_shell(p: Params, side: str, front: bool):
    """Half of an end wall, with half of the bin floor and end stop standing on it.

    The four shells are mirror images of each other; the two halves of each
    bin floor meet on the centre plane.
    """
    sg = -1 if side == "L" else 1
    out = p.n_channels - p.n_channels // 2          # the wall lies on the outermost fan plane
    tower, bin_wall, skirt = p.wall_outlines(side)
    tower = [(x, 5.0 if z == 0.0 else z - 8.0 if z == p.z_base else z) for x, z in tower]
    skirt = [(x, z - 8.0 if z == p.z_base else z) for x, z in skirt]
    wall = None
    for pts in (tower, bin_wall, skirt):
        piece = _prism(pts, 0.0, p.plate_t)
        wall = piece if wall is None else wall.union(piece)
    wall = wall.cut(_prism(p.finger_notch(side), -1, p.plate_t + 1))
    # The top of the tower wall is a separate plate (build_upper).  The two
    # overlap in a half lap: this piece keeps the outer half.
    far = 2 * p.width
    wall = wall.cut(_box(-far, far, p.wall_split, 50, -1, p.plate_t / 2))
    wall = wall.cut(_box(-far, far, p.wall_split + p.wall_lap, 50, -1, p.plate_t + 1))
    wall = _place(p, wall, out)

    c = p.depth / 2
    floor = _prism(p.bin_floor_outline(side), c, c + 200).cut(_place(p, _beyond(p, 0), out))
    body = _trim(p, wall.union(floor))

    holes = [h for h in p.bar_holes() if h[0] * sg > 0]
    bb = p.bin_bar
    holes.append((bb[0] if side == "L" else -bb[0], bb[1]))
    for h in holes:
        body = body.cut(_bar_cut(p, h))
    fx, half = sg * p.foot_x, p.foot_w / 2 + p.fit
    body = body.cut(_box(fx - half, fx + half, p.z_base - 1, p.z_base + p.foot_h / 2, -300, 400))
    return body if front else body.mirror("XY", (0, 0, c))


def build_upper(p: Params, front: bool):
    """Top of an end wall: one plate across the tower, carrying both upper tie bars."""
    out = p.n_channels - p.n_channels // 2
    plate = _box(-p.px, p.px, p.wall_split, 5.0, 0.0, p.plate_t)
    # inner half of the lap
    plate = plate.cut(_box(-p.px - 1, p.px + 1, p.wall_split - 1, p.wall_split + p.wall_lap, p.plate_t / 2, p.plate_t + 1))
    body = _trim(p, _place(p, plate, out))
    for h in p.bar_holes():
        if h[1] > p.wall_split:
            body = body.cut(_bar_cut(p, h))
    return body if front else body.mirror("XY", (0, 0, p.depth / 2))


def wall_faces(p: Params, z: float) -> tuple[float, float]:
    """Distance from the centre plane to the inner and outer face of an end wall at height z."""
    out = p.n_channels - p.n_channels // 2
    if p.fan_R > 0:
        th = out * p.fan_delta
        inner = (p.fan_R - z) * math.tan(th)
        return inner, inner + p.plate_t / math.cos(th)
    return out * p.pitch, out * p.pitch + p.plate_t


def bar_length(p: Params, at: Point) -> float:
    """Shaft length of the tie bar at this position (the fan makes lower bars longer)."""
    return 2 * wall_faces(p, at[1])[1] + p.tail


def build_bar(p: Params, at: Point = (0.0, 0.0)):
    """Tie bar: head behind the back wall, slotted tail in front of the front wall."""
    c = p.depth / 2
    reach = max(wall_faces(p, at[1] + s * p.bar / 2)[1] for s in (-1, 1)) + 0.1
    back, front = c - reach, c + reach
    bar = _prism(_square(at, p.bar), back, front + p.tail)
    head = _box(at[0] - p.bar / 2 - 2, at[0] + p.bar / 2 + 2, at[1] - p.bar / 2, at[1] + p.bar / 2,
                back - p.head_t, back)
    slot = _box(at[0] - p.slot_w / 2, at[0] + p.slot_w / 2, at[1] - p.bar, at[1] + p.bar,
                front - 1.5, front - 1.5 + p.slot_len)
    return bar.union(head).cut(slot)


def build_wedge(p: Params, at: Point = (0.0, 0.0)):
    """Tapered key, drawn driven home through the bar at `at`."""
    import cadquery as cq
    f = 0.55                                 # how far along its length it seats
    z_narrow = at[1] - f * p.wedge_len       # narrow end points down
    z_wide = z_narrow + p.wedge_len
    face = lambda z: p.depth / 2 + wall_faces(p, z)[1] + 0.1     # it lies against the (leaning) wall
    prof = [(face(z_narrow), z_narrow), (face(z_narrow) + p.wedge_narrow, z_narrow),
            (face(z_wide) + p.wedge_wide, z_wide), (face(z_wide), z_wide)]
    # profile is in (w, z); extrude along x
    return (cq.Workplane("YZ").workplane(offset=at[0] - p.wedge_t / 2)
            .polyline([(z, w) for w, z in prof]).close().extrude(p.wedge_t))


def build_foot(p: Params, side: str):
    """Outrigger foot.  If machine_tilt_deg is set its underside is cut at that angle."""
    import cadquery as cq
    sg = -1 if side == "L" else 1
    fx, c = sg * p.foot_x, p.depth / 2
    top = p.z_base + p.foot_h
    reach = wall_faces(p, p.z_base)[1] + p.foot_out
    w0, w1 = c - reach, c + reach
    rise = (w1 - w0) * math.tan(math.radians(p.machine_tilt_deg))     # the front stands this much taller
    prof = [(w0, top), (w1, top), (w1, p.z_base - rise), (w0, p.z_base)]
    foot = (cq.Workplane("YZ").workplane(offset=fx - p.foot_w / 2)
            .polyline([(z, w) for w, z in prof]).close().extrude(p.foot_w))
    a = wall_faces(p, top)[0] - p.fit            # the walls lean, so the slots are a little wider
    b = wall_faces(p, p.z_base)[1] + p.fit
    for lo, hi in ((c - b, c - a), (c + a, c + b)):
        foot = foot.cut(_box(fx - p.foot_w, fx + p.foot_w, p.z_base + p.foot_h / 2, top + 1, lo, hi))
    return foot


def build_jam_key(p: Params):
    """A flat stick for pushing a stuck card down its channel from the top of the hopper."""
    reach = p.hopper_h - p.z_hi + 15          # hopper rim to just past the top of the ramps
    w, t = 14.0, 1.6
    pts = [(-w / 2, 0), (w / 2, 0), (w / 2, reach), (22, reach), (22, reach + 18),
           (-22, reach + 18), (-22, reach), (-w / 2, reach)]
    return _prism(pts, 0.0, t)


def bar_positions(p: Params) -> list[Point]:
    bb = p.bin_bar
    return p.bar_holes() + [bb, (-bb[0], bb[1])]


BAR_KINDS = ("bar_ear", "bar_ear", "bar_low", "bar_low", "bar_bin", "bar_bin")


def build_parts(p: Params) -> dict:
    """Every part, in its assembled position."""
    parts = {f"slice_{i:02d}": build_slice(p, i) for i in range(p.n_channels)}
    for side in "LR":
        parts[f"back_{side}"] = build_shell(p, side, front=False)
        parts[f"front_{side}"] = build_shell(p, side, front=True)
        parts[f"foot_{side}"] = build_foot(p, side)
    parts["upper_front"] = build_upper(p, front=True)
    parts["upper_back"] = build_upper(p, front=False)
    parts["hopper"] = build_hopper(p)
    for k, at in enumerate(bar_positions(p)):
        parts[f"bar_{k}"] = build_bar(p, at)
        parts[f"wedge_{k}"] = build_wedge(p, at)
    return parts


def resting_pile(p: Params, side: str, n_cards: int = 30):
    """A pile of cards sitting in a bin (for clearance checks and pictures)."""
    t = n_cards * p.card_pitch
    w0 = (p.depth - t) / 2
    return _prism(p.resting_card(side), w0, w0 + t)


# How each kind of part lies on the print bed: (axis, degrees) applied to the
# model frame, in which Z is depth.  Flat parts already have depth pointing up.
PRINT_ROTATION = {
    "slice": None, "back": None, "front": None,
    "bar": ((1, 0, 0), 90),     # lie the bar down, slot vertical
    "wedge": ((0, 1, 0), 90),   # flat on its 2 mm face
    "foot": ((0, 1, 0), 90),    # on its side so the lap slots need no bridging
    "hopper": ((1, 0, 0), -90),  # upside down: throat on the bed, lugs on top
    "jam": None, "upper": None,
    "flipped": ((1, 0, 0), 180),  # back-half slices and front walls: turn over so the plate is on the bed
}


def as_printed(name: str, solid, p: Params = Params()):
    """The part as it lies on the print bed, sitting at the origin."""
    kind = name.split("_")[0]
    out = p.n_channels - p.n_channels // 2
    if kind == "slice":
        i = int(name.split("_")[1])
        solid = _unplace(p, solid, slice_steps(p, i))
        if p.blade_in_front(i):
            kind = "flipped"
    elif kind in ("back", "front"):
        solid = _unplace(p, solid, out if kind == "front" else -out)
        if kind == "front":
            kind = "flipped"
    elif kind == "upper":
        is_front = name.endswith("front")
        solid = _unplace(p, solid, out if is_front else -out)
        kind = "upper" if is_front else "flipped"
    rot = PRINT_ROTATION[kind]
    if rot:
        solid = solid.rotate((0, 0, 0), rot[0], rot[1])
    bb = solid.val().BoundingBox()
    return solid.translate((-bb.xmin, -bb.ymin, -bb.zmin))


def print_list(p: Params) -> dict[str, int]:
    """Distinct files to print and how many of each."""
    files = {f"slice_{i:02d}": 1 for i in range(p.n_channels)}
    files.update({"back_L": 1, "back_R": 1, "front_L": 1, "front_R": 1, "upper_front": 1, "upper_back": 1,
                  "bar_ear": 2, "bar_low": 2, "bar_bin": 2, "wedge": 6, "foot": 2, "hopper": 1,
                  "jam_key": 1})
    return files


CANONICAL = {"bar_ear": "bar_0", "bar_low": "bar_2", "bar_bin": "bar_4", "wedge": "wedge_0", "foot": "foot_L"}


def export(p: Params, out_dir: str) -> None:
    import os
    import cadquery as cq
    os.makedirs(out_dir, exist_ok=True)
    parts = build_parts(p)
    parts["jam_key"] = build_jam_key(p)
    for fname in print_list(p):
        solid = as_printed(fname, parts[CANONICAL.get(fname, fname)], p)
        cq.exporters.export(solid, os.path.join(out_dir, fname + ".stl"), tolerance=0.02)
    asm = cq.Assembly()
    del parts["jam_key"]
    for name, solid in parts.items():
        asm.add(solid.rotate((0, 0, 0), (1, 0, 0), 90), name=name)   # stand it upright: Z = up
    asm.save(os.path.join(out_dir, "assembly.step"))


if __name__ == "__main__":
    import sys
    P = Params()
    print(f"size {P.width:.0f} wide x {P.depth_at_base + 2 * P.plate_t:.0f} deep at the base x "
          f"{P.height + P.hopper_h:.0f} tall mm (tower {P.height:.0f}, hopper {P.hopper_h:.0f})")
    print(f"collar opening {2 * P.cx:.0f} x {P.depth:.0f} mm, throat {P.throat:.0f} mm, for a {P.deck_t:.0f} mm deck")
    export(P, sys.argv[1] if len(sys.argv) > 1 else "out")
