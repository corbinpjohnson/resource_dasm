"""Rigid-body test of the shuffler in MuJoCo.

Builds the machine's card-facing surfaces straight from `Params` (blades with
tapered tips, ramps, collar walls, end walls, bin floors, stops), drops a deck
of thin rigid cards into it and reports where every card ends up.

What this can and cannot tell you:

* It tests the geometry: does a deck split on the chevron, does a packet tip
  over and slide out, do the bins hold the cards, does anything wedge.
* Cards are rigid 0.6 mm plates.  Real sleeved cards bend, trap air and have
  soft edges, so this is harsher on jams and blind to anything that depends
  on flex.  Friction values are guesses.

MuJoCo frame: X = x, Y = depth (w), Z = up.  Built in mm, emitted in metres.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace

import numpy as np

from shuffler_design import Params

MM = 1e-3
CARD_T = 0.6          # rigid thickness of one sleeved card
CARD_MASS = 0.0023    # kg


# --------------------------------------------------------------- geometry
def _box(x0, x1, w0, w1, z0, z1) -> str:
    c = ((x0 + x1) / 2 * MM, (w0 + w1) / 2 * MM, (z0 + z1) / 2 * MM)
    h = (abs(x1 - x0) / 2 * MM, abs(w1 - w0) / 2 * MM, abs(z1 - z0) / 2 * MM)
    return f'<geom type="box" pos="{c[0]} {c[1]} {c[2]}" size="{h[0]} {h[1]} {h[2]}"/>'


def _bin_box(p: Params, side: str, s0, s1, n0, n1, w0, w1) -> str:
    """Box aligned with a bin floor (s along the slope, n square to it)."""
    cx, cz = p.bin_pt((s0 + s1) / 2, (n0 + n1) / 2, side)
    c, s = math.cos(math.radians(p.ramp_deg)), math.sin(math.radians(p.ramp_deg))
    axes = f"{-c} 0 {-s} 0 -1 0" if side == "L" else f"{c} 0 {-s} 0 1 0"
    return (f'<geom type="box" pos="{cx * MM} {(w0 + w1) / 2 * MM} {cz * MM}" xyaxes="{axes}" '
            f'size="{(s1 - s0) / 2 * MM} {(w1 - w0) / 2 * MM} {(n1 - n0) / 2 * MM}"/>')


class _Meshes:
    def __init__(self):
        self.assets: list[str] = []

    def hull(self, verts) -> str:
        """Geom that is the convex hull of points given as (x, w, z) in mm."""
        name = f"m{len(self.assets)}"
        flat = " ".join(f"{v * MM:.7f}" for pt in verts for v in pt)
        self.assets.append(f'<mesh name="{name}" vertex="{flat}"/>')
        return f'<geom type="mesh" mesh="{name}"/>'

    def prism(self, pts_xz, w0, w1) -> str:
        return self.hull([(x, w, z) for x, z in pts_xz for w in (w0, w1)])


def _placed(p: Params, geoms: list[str], steps: float) -> str:
    """Move geoms built at the centre plane out to their place: `steps` blade spacings from the centre.

    Parallel comb: a plain shift.  Fan comb: a rotation about the hinge line above the rim.
    """
    c = p.depth / 2
    if p.fan_R > 0:
        th = steps * p.fan_delta
        py, pz = c * MM, p.fan_R * MM
        ry, rz = py * math.cos(th) - pz * math.sin(th), py * math.sin(th) + pz * math.cos(th)
        return (f'<body pos="0 {py - ry} {pz - rz}" quat="{math.cos(th / 2)} {math.sin(th / 2)} 0 0">'
                + "".join(geoms) + "</body>")
    return f'<body pos="0 {steps * p.pitch * MM} 0">' + "".join(geoms) + "</body>"


def _blade_geoms(p: Params, meshes: _Meshes, W, top, blade_E: float, steps: bool) -> list[str]:
    """One blade, flat back on the plane w = 0 of the local frame `W`."""
    g: list[str] = []
    bottom = p.z_lo - p.rib_d
    wb = p.blade_t
    full = p.bevel_h                      # depth below the top edge where the blade is full thickness
    base = max(min(z for _, z in top) - full, bottom + 1)
    g.append(_box(-p.bx, p.bx, W(0), W(wb), bottom, base))
    # The taper runs the full width of the blade, ears included, so its face is flush.
    edge = [(-p.px, top[0][1]), *top, (p.px, top[-1][1])]
    t_at = lambda z_top, z: p.tip_land + (wb - p.tip_land) * min(1.0, (z_top - z) / full)
    # With blade_E > 0 the thinnest part of each blade (down to where it gains
    # its second layer) is a separate flap on a sprung hinge: a printed
    # one-layer tip is a film, not a rigid knife.
    n_terr = max(1, round((wb - p.tip_land) / p.layer_h))     # one terrace per printed layer
    step = full / n_terr                                      # height of each terrace
    film = max(1, round(p.tip_land / p.layer_h))              # terraces thinner than two tip thicknesses flex
    flap_len = film * step if blade_E > 0 else 0.0
    flap: list[str] = []
    for (xa, za), (xb, zb) in zip(edge, edge[1:]):
        lo_a, lo_b = max(za - full, base), max(zb - full, base)
        hinged = flap_len > 0 and abs(xa) <= p.cx + 1e-9 and abs(xb) <= p.cx + 1e-9
        if steps:
            # As printed: the blade gains one 0.2 mm layer at a time, leaving
            # a small ledge on one face at each step.
            for k in range(n_terr):
                t = p.tip_land + k * p.layer_h
                pts = [(xx, W(w), max(zz - d, base)) for w in (0, t)
                       for d in (k * step, (k + 1) * step) for xx, zz in ((xa, za), (xb, zb))]
                (flap if hinged and k < film else g).append(meshes.hull(pts))
            if min(lo_a, lo_b) > base + 0.5:
                g.append(meshes.hull([(xx, W(w), zz) for w in (0, wb)
                                      for xx, zz in ((xa, lo_a), (xb, lo_b), (xa, base), (xb, base))]))
            continue
        ca, cb = (za - flap_len, zb - flap_len) if hinged else (za, zb)      # top of the rigid part
        g.append(meshes.hull([(xx, W(w), zz) for w in (0, wb) for xx, zz in ((xa, base), (xb, base))]
                             + [(xa, W(w), lo_a) for w in (0, t_at(za, lo_a))]
                             + [(xb, W(w), lo_b) for w in (0, t_at(zb, lo_b))]
                             + [(xa, W(w), ca) for w in (0, t_at(za, ca))]
                             + [(xb, W(w), cb) for w in (0, t_at(zb, cb))]))
        if hinged:
            flap.append(meshes.hull([(xa, W(w), ca) for w in (0, t_at(za, ca))]
                                    + [(xb, W(w), cb) for w in (0, t_at(zb, cb))]
                                    + [(xx, W(w), zz) for w in (0, p.tip_land) for xx, zz in ((xa, za), (xb, zb))]))
    if flap:
        inertia = 2 * p.cx * p.tip_land ** 3 / 12                    # mm^4, of the one-layer film
        k = 3 * blade_E * inertia / flap_len * 1e-3                  # N.m/rad: same tip deflection as a cantilever
        hinge_z = sum(z for _, z in top) / len(top) - flap_len
        g.append(f'<body><joint type="hinge" axis="1 0 0" pos="0 {W(p.tip_land / 2) * MM} {hinge_z * MM}" '
                 f'stiffness="{k}" damping="{0.02 * k}" armature="1e-7" range="-0.5 0.5" limited="true"/>'
                 + "".join(flap) + "</body>")
    for sg in (-1, 1):
        a, b = sorted((sg * p.cx, sg * p.px))
        g.append(_box(a, b, W(0), W(p.tip_land), edge[0 if sg < 0 else -1][1], 0))   # blade ear, one layer
    return g


def machine_xml(p: Params, meshes: _Meshes, blade_E: float = 0.0, steps: bool = True) -> list[str]:
    out: list[str] = []
    c = p.depth / 2
    mid = p.n_channels // 2
    for i in range(p.n_channels):
        # Each slice is built on the centre plane (blade first, then everything
        # that fills its channel) and then moved out to its own plane.
        plane, direction = p.slice_plane(i)
        W = (lambda w: c + w) if direction > 0 else (lambda w: c - w)
        # the channel ends at the next plane, or at the middle divider's face
        shy = p.blade_t if p.blade_outside and plane + direction == 0 and direction < 0 else 0.0
        far = lambda z, shy=shy: p.pitch * p.spread(z) - shy
        side = p.side(i)
        other = "R" if side == "L" else "L"
        exit_sign = -1 if side == "L" else 1
        g = _blade_geoms(p, meshes, W, p.blade_top(i), blade_E, steps)
        for sg in (-1, 1):
            a, b = sorted((sg * p.cx, sg * p.px))
            h = p.collar_h if sg == -exit_sign else p.boss_short
            g.append(meshes.hull([(x, W(w), z) for x in (a, b) for z in (0.0, -h) for w in (0.0, far(z))]))  # collar wall
        x_far = -exit_sign * p.bar_x
        for pts in (p.rib_outline(side), p.rib_outline(other, x_far - 8, x_far + 8)):
            g.append(meshes.hull([(x, W(w), z) for x, z in pts for w in (0.0, far(z))]))
        out.append(_placed(p, g, plane))
    if p.blade_outside:                                   # the extra blade in the middle
        out.append(_placed(p, _blade_geoms(p, meshes, lambda w: c + w, p.divider_top(), blade_E, steps), 0))

    if p.hopper_h > 0:
        t = p.hopper_t
        for front in (False, True):
            for piece in p.hopper_end_pieces(front):
                out.append(meshes.hull([(x, w, z) for w, z in piece for x in (-p.cx - t, p.cx + t)]))
        slot_z = p.hopper_h - p.finger_slot
        for sg in (-1, 1):
            a, b = sorted((sg * p.cx, sg * (p.cx + t)))
            out.append(_box(a, b, p.hopper_shear(slot_z) - t, p.depth, 0, slot_z))          # below the finger slot
            for w0 in (0.0, p.depth - p.post_w) if p.finger_slot > 0 else ():                # corner posts
                out.append(meshes.hull([(x, w0 + dw + p.hopper_shear(z), z) for x in (a, b)
                                        for z in (slot_z, p.hopper_h) for dw in (0.0, p.post_w)]))

    end = p.bin_len + p.stop_t
    notch = p.bin_len / 2 + 2
    for sign in (-1, 1):                               # end walls lie on the outermost blade planes
        wa, wb_ = sorted((c, c + sign * p.plate_t))
        g = [_box(-p.px, p.px, wa, wb_, p.z_base - 20, 0)]                    # tower wall
        for side in "LR":                                                    # bin wall with finger notch
            g.append(_bin_box(p, side, -15, notch - p.notch_w / 2, -p.floor_t - 20, p.wall_h, wa, wb_))
            g.append(_bin_box(p, side, notch + p.notch_w / 2, end, -p.floor_t - 20, p.wall_h, wa, wb_))
            g.append(_bin_box(p, side, notch - p.notch_w / 2, notch + p.notch_w / 2, -p.floor_t - 20, p.notch_floor, wa, wb_))
        out.append(_placed(p, g, sign * (p.n_channels - mid)))
    half = p.depth * p.spread(p.z_base) / 2 + 5
    for side in "LR":
        out.append(_bin_box(p, side, p.floor_t * p.tan_ramp, end, -p.floor_t, 0, c - half, c + half))
        out.append(_bin_box(p, side, p.bin_len, end, 0, p.stop_h, c - half, c + half))
        out.append(_bin_box(p, side, p.bin_len, p.bin_len + p.fence_t, 0, p.fence_h, c - half, c + half))
    return out


@dataclass(frozen=True)
class Conditions:
    """Everything about a drop that is not the machine: the cards and how they are released."""

    card_bottom: str = "round"     # "round": sleeve bottom modelled as a rounded edge (realistic)
                                   # "flat":  a square-cut rigid plate (pessimistic: perches on tips)
    card_t: float = CARD_T
    mu_card: float = 0.22          # card on card
    mu_machine: float = 0.35       # card on printed plastic
    release_height: float = 2.0    # bottom of the deck above the highest blade tip at release
    lean_deg: float = 0.0          # deck leaning by this much more (or less) than the hopper does
    x_jitter: float = 0.5          # cards are not perfectly squared up, +/- this
    blade_steps: bool = True       # blades thicken in one-layer steps, as printed (False: a smooth taper)
    tilt_deg: float = 0.0          # the table is off level: tipped back by this much more than the feet give
    blade_E: float = 2000.0        # Young's modulus of the blades, MPa (PETG).  The one-layer blade
                                   # tips then flex as a printed film would.  0: perfectly rigid
                                   # blades, which is pessimistic for tight decks


def build_xml(p: Params, n_cards: int, timestep: float, c: Conditions = Conditions()) -> str:
    meshes = _Meshes()
    static = machine_xml(p, meshes, c.blade_E, c.blade_steps)
    hx, hy, hz = p.sleeve_w / 2 * MM, c.card_t / 2 * MM, p.sleeve_h / 2 * MM
    if c.card_bottom == "round":
        r = hy
        geoms = (f'<geom class="card" type="box" pos="0 0 {r / 2}" size="{hx} {hy} {hz - r / 2}" mass="{CARD_MASS}"/>'
                 f'<geom class="card" type="capsule" fromto="{-hx + r} 0 {-hz + r} {hx - r} 0 {-hz + r}" '
                 f'size="{r}" mass="1e-6"/>')
    else:
        geoms = f'<geom class="card" type="box" size="{hx} {hy} {hz}" mass="{CARD_MASS}"/>'
    cards = "\n".join(f'<body name="c{k}"><freejoint/>{geoms}</body>' for k in range(n_cards))
    tc = 4 * timestep
    tilt = math.radians(p.machine_tilt_deg + c.tilt_deg)     # the machine leans back: gravity is tilted in its frame
    return f"""
<mujoco>
  <option timestep="{timestep}" gravity="0 {-9.81 * math.sin(tilt)} {-9.81 * math.cos(tilt)}" cone="elliptic">
    <flag multiccd="enable"/>
  </option>
  <size memory="400M"/>
  <default>
    <geom solref="{tc} 1" solimp="0.95 0.99 0.0001" friction="{c.mu_machine} 0.001 0.0001" condim="3" rgba="0.6 0.7 0.9 1"/>
    <default class="card"><geom friction="{c.mu_card} 0.001 0.0001" rgba="1 0.82 0.5 1"/></default>
  </default>
  <asset>{''.join(meshes.assets)}</asset>
  <worldbody>
    <geom type="plane" pos="0 0 {p.z_base * MM}" size="1 1 0.01"/>
    {''.join(static)}
    {cards}
  </worldbody>
</mujoco>"""


# ------------------------------------------------------------------- drop
# Where a card that did not reach a bin ended up.  These are the jam types.
PERCHED = "perched"      # one or two cards standing on blade tips in the hopper
COMB = "comb jam"        # a group of cards wedged in the top of the comb
FLOP = "ramp jam"        # fell through the comb but stuck on the ramps
ESCAPED = "escaped"      # left the machine


@dataclass
class DropResult:
    left: list[int] = field(default_factory=list)     # card ids, back to front
    right: list[int] = field(default_factory=list)
    stuck: list[int] = field(default_factory=list)    # still inside the comb
    escaped: list[int] = field(default_factory=list)  # anywhere else
    lane: dict[int, int] = field(default_factory=dict)  # channel each card went down
    where: dict[int, str] = field(default_factory=dict)  # jam type for each undelivered card
    unseated: list[int] = field(default_factory=list)  # in a bin but not down against the stop
    settle_time: float = 0.0
    final_pos: np.ndarray | None = None

    @property
    def ok(self) -> bool:
        return not self.stuck and not self.escaped

    @property
    def delivered(self) -> int:
        return len(self.left) + len(self.right)

    def jam_types(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for kind in self.where.values():
            out[kind] = out.get(kind, 0) + 1
        return out


class Rig:
    """Compiled model, reusable for many drops."""

    def __init__(self, p: Params = Params(), n_cards: int | None = None, timestep: float = 1e-4,
                 conditions: Conditions = Conditions()):
        import mujoco
        self.mj = mujoco
        self.p = p
        self.c = conditions
        self.n = n_cards or p.n_cards
        self.model = mujoco.MjModel.from_xml_string(build_xml(p, self.n, timestep, conditions))
        self.data = mujoco.MjData(self.model)
        self.q0 = self.model.nq - 7 * self.n          # cards come after any blade-tip hinges
        self.v0 = self.model.nv - 6 * self.n

    def drop(self, deck: list[int], rng: random.Random, max_time: float = 3.0,
             offset: float | None = None) -> DropResult:
        """Release `deck` (deck[0] at the back) into the hopper and wait for it to settle."""
        p, c, mj, d = self.p, self.c, self.mj, self.data
        mj.mj_resetData(self.model, d)
        throat = p.throat if p.hopper_h > 0 else p.depth
        thickness = len(deck) * p.card_pitch
        slack = max(throat - thickness, 0.7)
        lo = (p.depth - throat) / 2
        # The throat ring positions the TOP of the deck.  A leaning deck has its
        # bottom edges shifted from there (still level, still inside the hopper).
        z_top = max(p.tip_z(i) for i in range(p.n_channels)) + c.release_height + p.sleeve_h
        ring = p.hopper_shear(min(z_top, p.hopper_h)) if p.hopper_h > 0 else 0.0   # the hopper leans, and so does the deck
        top_start = lo + ring + (rng.uniform(0.3, slack - 0.3) if offset is None else offset) + p.card_pitch / 2
        lean = math.radians(c.lean_deg + (p.hopper_lean_deg if p.hopper_h > 0 else 0.0))
        shift = math.sin(lean) * p.sleeve_h                 # bottom relative to top
        room = p.tube_inset if p.hopper_h > 0 else 0.0     # the hopper walls limit the lean
        shift = max(room + 0.5 - top_start, min(shift, p.depth - room - thickness - top_start - 0.5))
        lean = math.asin(shift / p.sleeve_h)
        z0 = max(p.tip_z(i) for i in range(p.n_channels)) + c.release_height + p.sleeve_h / 2
        quat = [math.cos(lean / 2), math.sin(lean / 2), 0, 0]           # rotation about x
        for k, card in enumerate(deck):
            w_top = top_start + k * p.card_pitch
            q = d.qpos[self.q0 + 7 * card: self.q0 + 7 * card + 7]
            q[:] = [rng.uniform(-c.x_jitter, c.x_jitter) * MM,
                    (w_top + shift / 2) * MM,
                    (z0 - (1 - math.cos(lean)) * p.sleeve_h / 2) * MM, *quat]
        for card in set(range(self.n)) - set(deck):                      # unused cards: park them far away
            d.qpos[self.q0 + 7 * card: self.q0 + 7 * card + 3] = [0.5 + 0.01 * card, 0.5, p.z_base * MM + 0.05]
        res = DropResult()
        z_gate = (p.z_hi + p.sleeve_h / 2) * MM      # card centre height as it reaches the ramps
        steps_per_check = int(0.01 / self.model.opt.timestep)
        t_quiet = 0.0
        active = np.array(sorted(deck))
        while d.time < max_time:
            mj.mj_step(self.model, d, steps_per_check)
            pos = d.qpos[self.q0:].reshape(self.n, 7)[:, :3]
            for card in deck:
                if card not in res.lane and pos[card, 2] < z_gate + 0.02:
                    res.lane[card] = p.lane_of(pos[card, 1] / MM, pos[card, 2] / MM)
            speed = np.abs(d.qvel[self.v0:].reshape(self.n, 6)[active, :3]).max()
            t_quiet = t_quiet + 0.01 if speed < 0.01 else 0.0
            if t_quiet > 0.15:
                break
        res.settle_time = d.time
        pos = d.qpos[self.q0:].reshape(self.n, 7)[:, :3] / MM
        res.final_pos = pos.copy()
        floor_z = min(z for _, z in p.bin_floor_outline()) - 2
        in_collar: list[int] = []
        a = math.radians(p.ramp_deg)
        ox, oz = p.bin_origin
        for card in sorted(deck, key=lambda k: pos[k, 1]):
            x, w, z = pos[card]
            inside = abs(w - p.depth / 2) < p.depth * p.spread(z) / 2 + 2 and z > floor_z
            if inside and abs(x) > p.bx:
                (res.left if x < 0 else res.right).append(card)
                s = (ox + abs(x)) * math.cos(a) + (oz - z) * math.sin(a)   # distance down the bin floor
                if s < p.bin_len - p.sleeve_w / 2 - 8:
                    res.unseated.append(card)
            elif abs(x) <= p.bx and z > floor_z:
                res.stuck.append(card)
                if z - p.sleeve_h / 2 > -p.collar_h - 5:
                    in_collar.append(card)
                else:
                    res.where[card] = FLOP
            else:
                res.escaped.append(card)
                res.where[card] = ESCAPED
        for card in in_collar:
            res.where[card] = PERCHED if len(in_collar) <= 2 else COMB
        return res


# ------------------------------------------------------------- evaluation
@dataclass
class Score:
    """Outcome of many independent drops of a fresh deck."""

    drops: int = 0
    cards: int = 0
    delivered: int = 0
    clean: int = 0                       # drops in which every card reached a bin
    jams: dict[str, int] = field(default_factory=dict)        # cards, by jam type
    jam_drops: dict[str, int] = field(default_factory=dict)   # drops affected, by jam type
    unseated: int = 0
    seeds_by_jam: dict[str, list[int]] = field(default_factory=dict)

    def add(self, seed: int, n: int, r: DropResult) -> None:
        self.drops += 1
        self.cards += n
        self.delivered += r.delivered
        self.clean += r.ok
        self.unseated += len(r.unseated)
        for kind, k in r.jam_types().items():
            self.jams[kind] = self.jams.get(kind, 0) + k
            self.jam_drops[kind] = self.jam_drops.get(kind, 0) + 1
            self.seeds_by_jam.setdefault(kind, []).append(seed)

    def merge(self, other: "Score") -> "Score":
        self.drops += other.drops
        self.cards += other.cards
        self.delivered += other.delivered
        self.clean += other.clean
        self.unseated += other.unseated
        for src, dst in ((other.jams, self.jams), (other.jam_drops, self.jam_drops)):
            for k, v in src.items():
                dst[k] = dst.get(k, 0) + v
        for k, v in other.seeds_by_jam.items():
            self.seeds_by_jam.setdefault(k, []).extend(v)
        return self

    @property
    def delivered_frac(self) -> float:
        return self.delivered / max(self.cards, 1)

    @property
    def clean_frac(self) -> float:
        return self.clean / max(self.drops, 1)

    def __str__(self) -> str:
        jams = ", ".join(f"{k}: {self.jams[k]} cards in {self.jam_drops[k]} drops" for k in sorted(self.jams)) or "none"
        return (f"{self.clean}/{self.drops} clean drops, {100 * self.delivered_frac:.1f}% delivered, "
                f"unseated {self.unseated}; jams: {jams}")


def _score_chunk(args) -> Score:
    p, c, n_cards, seeds = args
    rig = Rig(p, n_cards=n_cards, conditions=c)
    score = Score()
    for seed in seeds:
        score.add(seed, rig.n, rig.drop(list(range(rig.n)), random.Random(seed)))
    return score


def evaluate(p: Params = Params(), c: Conditions = Conditions(), seeds=range(1, 17),
             n_cards: int | None = None, workers: int = 4) -> Score:
    """Drop a fresh deck once per seed, in parallel, and tally what happened."""
    import multiprocessing as mp
    seeds = list(seeds)
    chunks = [seeds[k::workers] for k in range(workers) if seeds[k::workers]]
    total = Score()
    if len(chunks) == 1:
        return _score_chunk((p, c, n_cards, chunks[0]))
    with mp.get_context("fork").Pool(len(chunks)) as pool:
        for part in pool.map(_score_chunk, [(p, c, n_cards, ch) for ch in chunks]):
            total.merge(part)
    return total


def packets(deck: list[int], res: DropResult) -> list[tuple[int, int]]:
    """(channel, cards) for each packet, in deck order."""
    out: list[tuple[int, int]] = []
    for card in deck:
        lane = res.lane.get(card, -1)
        if out and out[-1][0] == lane:
            out[-1] = (lane, out[-1][1] + 1)
        else:
            out.append((lane, 1))
    return out


def repeated_drops(rig: Rig, passes: int, seed: int = 0, verbose: bool = False):
    """Drop, stack left on right, drop again.  Yields (deck_after, result) per pass."""
    rng = random.Random(seed)
    deck = list(range(rig.n))
    for k in range(passes):
        res = rig.drop(deck, rng)
        if verbose:
            sizes = [n for _, n in packets(deck, res)]
            print(f"pass {k + 1}: left {len(res.left)} right {len(res.right)} stuck {len(res.stuck)} "
                  f"escaped {len(res.escaped)} settle {res.settle_time:.2f}s packets {sizes}", flush=True)
        deck = res.left + res.right + res.stuck + res.escaped
        yield deck, res


if __name__ == "__main__":
    import sys
    import time
    from shuffle_sim import neighbours_kept
    passes = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    t = time.time()
    rig = Rig()
    print(f"model: {rig.model.ngeom} geoms, built in {time.time() - t:.1f}s", flush=True)
    for k, (deck, res) in enumerate(repeated_drops(rig, passes, seed=1, verbose=True)):
        print(f"   neighbours kept {neighbours_kept(deck):.2f}   wall {time.time() - t:.0f}s", flush=True)
