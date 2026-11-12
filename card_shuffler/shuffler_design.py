"""Gravity comb shuffler for sleeved cards - parametric design.

How it works (see README.md for pictures):

* The deck is dropped, short edge down, into a COLLAR at the top.
* Under the collar is a COMB of thin vertical blades that slices the deck
  into packets of about seven cards.  The blade tips form a chevron (one
  centre tip highest) so the deck is split one blade at a time.
* Each CHANNEL between two blades has a sloping floor (RAMP).  Ramps
  alternate: left, right, left, right...  A packet of cards free-falls one card
  height, lands on its ramp, tips over onto its short edge and slides out
  sideways.
* Two tilted BINS catch the left-going and right-going cards.
* Stack one pile on the other and drop again.

Everything is a flat extrusion so it prints without supports:

    slice_NN   blade + ramp rib + spacers, one per channel (printed flat)
    back_L/R   back wall with bin floor and end stop growing out of it
    front_L/R  front wall
    bar        square tie bar with a slot for ...
    wedge      ... a tapered key that clamps the whole stack (no screws)
    foot       cross-lapped outrigger so the tower cannot tip
    hopper     sits on the rim and holds the deck upright while it is released

Frame used in this file:  x = across the card face, z = up, w = depth (the
direction the cards are stacked in).  2-D outlines are lists of (x, z).
CadQuery is only needed for `build_parts`; all the numbers work without it.
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
    n_cards: int = 60

    # --- the comb --------------------------------------------------------
    n_channels: int = 14          # must be even: half go left, half right
    channel_w: float = 4.2        # gap between blades
    blade_t: float = 0.8          # thin on purpose: the physics test shows thick blades fan the
                                  # deck out until the tilted cards lock in the slots
    tip_land: float = 0.2         # width of the blade tip: a single layer
    bevel_h: float = 2.0          # height over which a blade tapers to its tip
    chevron_step: float = 3.5     # each blade's tip is this much lower than its inner neighbour
    roof_deg: float = 12.0        # blade top slopes away from a central peak
    tip_guard: float = 6.0        # highest tip sits this far below the rim

    # --- the path of a card ----------------------------------------------
    side_clear: float = 1.5       # collar clearance each side of the card
    ear_w: float = 12.0           # width of the collar walls
    exit_clear: float = 3.0       # blades extend this far past the collar
    boss_short: float = 14.0      # collar wall height on the side a card leaves by
    fall_clear: float = 3.0       # extra free fall beyond one card height
    ramp_deg: float = 40.0
    friction_deg: float = 22.0    # pessimistic sleeve-on-PLA friction angle
    rib_d: float = 16.0           # depth of the rib that carries a ramp
    bar_x: float = 18.0           # lower tie bars sit this far off centre

    # --- the bins --------------------------------------------------------
    bin_extra: float = 5.0        # bin length beyond one card width
    bin_gap: float = 0.5          # gap between comb and bin floor
    bin_step: float = 0.6         # bin floor is this much lower than the ramp (no lip)
    floor_t: float = 3.0
    stop_h: float = 60.0          # taller than a card's centre of gravity, or cards vault it
    stop_t: float = 14.0
    wall_h: float = 58.0          # bin side walls, measured square to the floor
    notch_w: float = 28.0         # finger notch
    notch_floor: float = 22.0

    # --- the hopper (sits on top, keeps the deck upright) -----------------
    hopper_h: float = 92.0        # walls all round, with a throat ring at the top
    throat_clear: float = 6.0     # throat depth = deck thickness + this
    throat_h: float = 32.0        # the ring holds the top of the deck upright at release; below
                                  # it the hopper is as deep as the comb so cards can spread
    hopper_t: float = 2.4
    tab_h: float = 10.0

    # --- structure -------------------------------------------------------
    plate_t: float = 3.0
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
    foot_out: float = 30.0        # how far a foot sticks out front and back
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

    def side(self, i: int) -> str:
        """Which bin channel i feeds."""
        return "LR"[i % 2]

    def blade_in_front(self, i: int) -> bool:
        """Slices in the back half carry their blade on the front of the channel.

        Every blade is then on the side of its own channel nearest the centre,
        every bevel faces outwards, and the two middle blades sit back to back.
        """
        return i < self.n_channels // 2

    def blade_w(self, i: int) -> tuple[float, float]:
        """Depth range occupied by blade i."""
        w0 = i * self.pitch
        return (w0 + self.channel_w, w0 + self.pitch) if self.blade_in_front(i) else (w0, w0 + self.blade_t)

    def channel_range(self, i: int) -> tuple[float, float]:
        w0 = i * self.pitch
        return (w0, w0 + self.channel_w) if self.blade_in_front(i) else (w0 + self.blade_t, w0 + self.pitch)

    def tip_z(self, i: int) -> float:
        """Height of the peak of blade i: a chevron with a single highest blade.

        The two middle blades sit back to back.  If they were the same height
        their tips would add up to a flat twice as wide, and the physics test
        shows a card regularly comes to rest on it, so only one of them leads.
        """
        return -self.tip_guard - self.chevron_step * abs(i - self.n_channels // 2)

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

    @property
    def roof_drop(self) -> float:
        return self.cx * math.tan(math.radians(self.roof_deg))

    @property
    def collar_h(self) -> float:
        """Deep enough that every blade edge ends inside the collar."""
        deepest = self.tip_guard + self.chevron_step * (self.n_channels // 2)
        return deepest + self.roof_drop + self.bevel_h + 4.0

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
        return 2 * max(-self.bin_pt(self.bin_len + self.stop_t, self.wall_h)[0], self.px)

    @property
    def bar_len(self) -> float:
        """Shaft length: through both walls and the stack, plus the tail."""
        return self.depth + 2 * self.plate_t + self.tail

    @property
    def wedge_deg(self) -> float:
        return math.degrees(math.atan((self.wedge_wide - self.wedge_narrow) / self.wedge_len))

    # ================= 2-D outlines =====================================
    def blade_outline(self, i: int, lower_by: float = 0.0) -> list[Point]:
        """Blade i seen face-on.  `lower_by` shaves the roof (used for the bevel)."""
        peak = self.tip_z(i) - lower_by
        eave = peak - self.roof_drop
        shoulder = -self.collar_h - (self.px - self.bx)
        bottom = self.z_lo - self.rib_d
        return [
            (-self.px, 0.0), (-self.cx, 0.0), (-self.cx, eave), (0.0, peak),
            (self.cx, eave), (self.cx, 0.0), (self.px, 0.0),
            (self.px, -self.collar_h), (self.bx, shoulder), (self.bx, bottom),
            (0.0, self.z_cross - self.rib_d), (-self.bx, bottom),
            (-self.bx, shoulder), (-self.px, -self.collar_h),
        ]

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
        sn = [(0, 0), (L, 0), (L, self.stop_h), (L + t, self.stop_h), (L + t, -self.floor_t), (plumb, -self.floor_t)]
        return [self.bin_pt(s, n, side) for s, n in sn]

    def tenons(self, side: str = "L", grow: float = 0.0) -> list[list[Point]]:
        """Two tongues on the bin floor that key into the front wall."""
        out = []
        for s0 in (0.25 * self.bin_len, 0.65 * self.bin_len):
            sn = [(s0 - grow, grow), (s0 + 12 + grow, grow),
                  (s0 + 12 + grow, -self.floor_t - grow), (s0 - grow, -self.floor_t - grow)]
            out.append([self.bin_pt(s, n, side) for s, n in sn])
        return out

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

    def hopper_end_wz(self, front: bool) -> list[Point]:
        """Front/back wall of the hopper with the throat ring on top, as (w, z)."""
        inset = (self.depth - self.throat) / 2
        top, lo = self.hopper_h, self.hopper_h - self.throat_h
        pts = [(-self.hopper_t, 0.0), (0.0, 0.0), (0.0, lo), (inset, lo),
               (inset, top - 2.0), (inset - 2.0, top), (-self.hopper_t, top)]
        return [(self.depth - w, z) for w, z in pts] if front else pts

    def hopper_return(self, x_sign: int, front: bool) -> tuple[list[Point], float, float]:
        """Small hook outside an end wall that locates the hopper front-to-back.

        Returns its (x, z) outline and depth range.  It is a 45 degree wedge so
        it prints without support, and sits outboard of the tie-bar wedges.
        """
        out, reach = self.px + self.fit, 3.2
        pts = [(out + self.hopper_t, 6.0), (out + self.hopper_t, -reach), (out - reach, -reach), (out, 0.0), (out, 6.0)]
        a, b = self.plate_t + self.fit, self.plate_t + self.fit + self.hopper_t
        w0, w1 = (self.depth + self.plate_t, self.depth + b) if front else (-b, -self.plate_t)
        return [(x_sign * x, z) for x, z in pts], w0, w1

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


def build_slice(p: Params, i: int):
    """Blade i plus everything that fills channel i."""
    side = p.side(i)
    other = "R" if side == "L" else "L"
    exit_sign = -1 if side == "L" else 1
    wb, w1 = p.blade_t, p.pitch          # local cell: blade first, channel after

    # Blade, tapering to its tip in terraces of one 0.2 mm layer each.
    steps = max(2, round(p.blade_t / p.tip_land))
    body = None
    for k in range(steps):
        a = k * p.blade_t / steps
        lam = _prism(p.blade_outline(i, lower_by=k * p.bevel_h / (steps - 1)), a, a + p.blade_t / steps)
        body = lam if body is None else body.union(lam)

    body = body.union(_prism(p.rib_outline(side), wb, w1))
    # A short piece of the opposite rib: spacer around the far tie bar.
    x_far = -exit_sign * p.bar_x
    body = body.union(_prism(p.rib_outline(other, x_far - 8, x_far + 8), wb, w1))
    body = body.union(_prism(p.collar_wall(-exit_sign, full=True), wb, w1))
    body = body.union(_prism(p.collar_wall(exit_sign, full=False), wb, w1))

    for c in p.bar_holes():
        body = body.cut(_prism(_square(c, p.hole), -1, w1 + 1))
    # Index mark: when stacked in order the marks form one diagonal line.
    zm = -p.collar_h - 20 - 2.5 * i
    body = body.cut(_box(p.bx - 1.5, p.bx + 1, zm - 1, zm + 1, -1, w1 + 1))
    if p.blade_in_front(i):
        body = body.mirror("XY", (0, 0, p.pitch / 2))
    return body.translate((0, 0, i * p.pitch))


def build_hopper(p: Params):
    """Four walls and a throat ring; sits on the rim, keeps the deck upright at release."""
    import cadquery as cq
    body = None
    for sg in (-1, 1):
        side = _prism(p.hopper_side_xz(sg), -p.plate_t, p.depth + p.plate_t)
        body = side if body is None else body.union(side)
        for front in (False, True):
            pts, w0, w1 = p.hopper_return(sg, front)
            body = body.union(_prism(pts, w0, w1))
    reach = p.cx + p.hopper_t
    for front in (False, True):
        end = (cq.Workplane("YZ").workplane(offset=-reach)
               .polyline([(z, w) for w, z in p.hopper_end_wz(front)]).close().extrude(2 * reach))
        body = body.union(end)
    return body


def _wall_half(p: Params, side: str, w0: float, w1: float):
    wall = None
    for pts in p.wall_outlines(side):
        piece = _prism(pts, w0, w1)
        wall = piece if wall is None else wall.union(piece)
    wall = wall.cut(_prism(p.finger_notch(side), w0 - 1, w1 + 1))
    sg = -1 if side == "L" else 1
    holes = [c for c in p.bar_holes() if c[0] * sg > 0]
    bb = p.bin_bar
    holes.append((bb[0] if side == "L" else -bb[0], bb[1]))
    for c in holes:
        wall = wall.cut(_prism(_square(c, p.hole), w0 - 1, w1 + 1))
    fx = sg * p.foot_x
    half = p.foot_w / 2 + p.fit
    wall = wall.cut(_box(fx - half, fx + half, p.z_base - 1, p.z_base + p.foot_h / 2, w0 - 1, w1 + 1))
    return wall


def build_back(p: Params, side: str):
    """Back wall half with the bin floor and end stop standing on it."""
    body = _wall_half(p, side, -p.plate_t, 0.0)
    body = body.union(_prism(p.bin_floor_outline(side), 0.0, p.depth))
    for t in p.tenons(side):
        body = body.union(_prism(t, p.depth, p.depth + p.plate_t))
    bb = p.bin_bar
    c = (bb[0] if side == "L" else -bb[0], bb[1])
    return body.cut(_prism(_square(c, p.hole), -p.plate_t - 1, p.depth + 1))


def build_front(p: Params, side: str):
    body = _wall_half(p, side, p.depth, p.depth + p.plate_t)
    for t in p.tenons(side, grow=p.fit):
        body = body.cut(_prism(t, p.depth - 1, p.depth + p.plate_t + 1))
    return body


def build_bar(p: Params, at: Point = (0.0, 0.0)):
    """Tie bar: head behind the back wall, slotted tail in front of the front wall."""
    front = p.depth + p.plate_t
    bar = _prism(_square(at, p.bar), -p.plate_t, front + p.tail)
    head = _box(at[0] - p.bar / 2 - 2, at[0] + p.bar / 2 + 2, at[1] - p.bar / 2, at[1] + p.bar / 2,
                -p.plate_t - p.head_t, -p.plate_t)
    slot = _box(at[0] - p.slot_w / 2, at[0] + p.slot_w / 2, at[1] - p.bar, at[1] + p.bar,
                front - 1.0, front - 1.0 + p.slot_len)
    return bar.union(head).cut(slot)


def build_wedge(p: Params, at: Point = (0.0, 0.0)):
    """Tapered key, drawn driven home through the bar at `at`."""
    import cadquery as cq
    front = p.depth + p.plate_t
    seat = p.slot_len - 1.0 - 0.4           # width where it crosses the bar
    f = (seat - p.wedge_narrow) / (p.wedge_wide - p.wedge_narrow)
    z_narrow = at[1] - f * p.wedge_len      # narrow end points down
    prof = [(front, z_narrow), (front + p.wedge_narrow, z_narrow),
            (front + p.wedge_wide, z_narrow + p.wedge_len), (front, z_narrow + p.wedge_len)]
    # profile is in (w, z); extrude along x
    return (cq.Workplane("YZ").workplane(offset=at[0] - p.wedge_t / 2)
            .polyline([(z, w) for w, z in prof]).close().extrude(p.wedge_t))


def build_foot(p: Params, side: str):
    sg = -1 if side == "L" else 1
    fx = sg * p.foot_x
    w0, w1 = -p.plate_t - p.foot_out, p.depth + p.plate_t + p.foot_out
    foot = _box(fx - p.foot_w / 2, fx + p.foot_w / 2, p.z_base, p.z_base + p.foot_h, w0, w1)
    for a, b in ((-p.plate_t, 0.0), (p.depth, p.depth + p.plate_t)):
        foot = foot.cut(_box(fx - p.foot_w, fx + p.foot_w, p.z_base + p.foot_h / 2, p.z_base + p.foot_h + 1,
                             a - p.fit, b + p.fit))
    return foot


def bar_positions(p: Params) -> list[Point]:
    bb = p.bin_bar
    return p.bar_holes() + [bb, (-bb[0], bb[1])]


def build_parts(p: Params) -> dict:
    """Every part, in its assembled position."""
    parts = {f"slice_{i:02d}": build_slice(p, i) for i in range(p.n_channels)}
    for side in "LR":
        parts[f"back_{side}"] = build_back(p, side)
        parts[f"front_{side}"] = build_front(p, side)
        parts[f"foot_{side}"] = build_foot(p, side)
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
    "slice_flipped": ((1, 0, 0), 180),  # back-half slices: turn over so the blade is on the bed
}


def as_printed(name: str, solid, p: Params = Params()):
    kind = name.split("_")[0]
    if kind == "slice" and p.blade_in_front(int(name.split("_")[1])):
        kind = "slice_flipped"
    rot = PRINT_ROTATION[kind]
    if rot:
        solid = solid.rotate((0, 0, 0), rot[0], rot[1])
    bb = solid.val().BoundingBox()
    return solid.translate((-bb.xmin, -bb.ymin, -bb.zmin))


def print_list(p: Params) -> dict[str, int]:
    """Distinct files to print and how many of each."""
    files = {f"slice_{i:02d}": 1 for i in range(p.n_channels)}
    files.update({"back_L": 1, "back_R": 1, "front_L": 1, "front_R": 1,
                  "bar": 6, "wedge": 6, "foot": 2, "hopper": 1})
    return files


def export(p: Params, out_dir: str) -> None:
    import os
    import cadquery as cq
    os.makedirs(out_dir, exist_ok=True)
    parts = build_parts(p)
    canonical = {"bar": "bar_0", "wedge": "wedge_0", "foot": "foot_L"}
    for fname in print_list(p):
        solid = as_printed(fname, parts[canonical.get(fname, fname)], p)
        cq.exporters.export(solid, os.path.join(out_dir, fname + ".stl"), tolerance=0.02)
    asm = cq.Assembly()
    for name, solid in parts.items():
        asm.add(solid.rotate((0, 0, 0), (1, 0, 0), 90), name=name)   # stand it upright: Z = up
    asm.save(os.path.join(out_dir, "assembly.step"))


if __name__ == "__main__":
    import sys
    P = Params()
    print(f"size {P.width:.0f} wide x {P.depth + 2 * P.plate_t:.0f} deep x {P.height:.0f} tall mm")
    print(f"collar opening {2 * P.cx:.0f} x {P.depth:.1f} mm for a {P.deck_t:.0f} mm deck")
    export(P, sys.argv[1] if len(sys.argv) > 1 else "out")
