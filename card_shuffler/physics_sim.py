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
from dataclasses import dataclass, field

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


def machine_xml(p: Params, meshes: _Meshes) -> list[str]:
    g: list[str] = []
    bottom = p.z_lo - p.rib_d
    for i in range(p.n_channels):
        # Local cell: blade occupies 0..blade_t, channel the rest.  Back-half
        # slices are mirrored, exactly as in shuffler_design.build_slice.
        if p.blade_in_front(i):
            W = lambda w, i=i: (i + 1) * p.pitch - w
        else:
            W = lambda w, i=i: i * p.pitch + w
        wb, w1 = p.blade_t, p.pitch
        side = p.side(i)
        other = "R" if side == "L" else "L"
        exit_sign = -1 if side == "L" else 1
        peak = p.tip_z(i)
        eave = peak - p.roof_drop
        full = p.bevel_h                      # depth below the roof line where the blade is full thickness
        g.append(_box(-p.bx, p.bx, W(0), W(wb), bottom, eave - full))
        for sg in (-1, 1):
            x = sg * p.cx
            # body under the roof line, then the taper to the tip
            g.append(meshes.hull([(xx, W(w), zz) for w in (0, wb)
                                  for xx, zz in ((0, eave - full), (x, eave - full), (0, peak - full))]))
            g.append(meshes.hull([(xx, W(w), zz - full) for w in (0, wb) for xx, zz in ((0, peak), (x, eave))]
                                 + [(xx, W(w), zz) for w in (0, p.tip_land) for xx, zz in ((0, peak), (x, eave))]))
            a, b = sorted((sg * p.cx, sg * p.px))
            g.append(_box(a, b, W(0), W(wb), -p.collar_h, 0))                 # blade ear
            h = p.collar_h if sg == -exit_sign else p.boss_short
            g.append(_box(a, b, W(wb), W(w1), -h, 0))                         # collar wall
        g.append(meshes.prism(p.rib_outline(side), W(wb), W(w1)))
        x_far = -exit_sign * p.bar_x
        g.append(meshes.prism(p.rib_outline(other, x_far - 8, x_far + 8), W(wb), W(w1)))

    if p.hopper_h > 0:
        t = p.hopper_t
        for front in (False, True):
            pts = p.hopper_end_wz(front)
            wall, ring = pts[:3] + [(pts[0][0], pts[2][1])], pts[2:] + [(pts[0][0], pts[2][1])]
            for piece in (wall, ring):                 # each piece is convex
                g.append(meshes.hull([(x, w, z) for w, z in piece for x in (-p.cx - t, p.cx + t)]))
        for sg in (-1, 1):
            a, b = sorted((sg * p.cx, sg * (p.cx + t)))
            g.append(_box(a, b, -p.plate_t, p.depth + p.plate_t, 0, p.hopper_h))

    end = p.bin_len + p.stop_t
    mid = p.bin_len / 2 + 2
    for wa, wb_ in ((-p.plate_t, 0.0), (p.depth, p.depth + p.plate_t)):
        g.append(_box(-p.px, p.px, wa, wb_, p.z_base, 0))                     # tower wall
        for side in "LR":                                                    # bin wall with finger notch
            g.append(_bin_box(p, side, -15, mid - p.notch_w / 2, -p.floor_t, p.wall_h, wa, wb_))
            g.append(_bin_box(p, side, mid + p.notch_w / 2, end, -p.floor_t, p.wall_h, wa, wb_))
            g.append(_bin_box(p, side, mid - p.notch_w / 2, mid + p.notch_w / 2, -p.floor_t, p.notch_floor, wa, wb_))
    for side in "LR":
        g.append(_bin_box(p, side, p.floor_t * p.tan_ramp, end, -p.floor_t, 0, 0, p.depth))
        g.append(_bin_box(p, side, p.bin_len, end, 0, p.stop_h, 0, p.depth))
    return g


def build_xml(p: Params, n_cards: int, timestep: float) -> str:
    meshes = _Meshes()
    static = machine_xml(p, meshes)
    hx, hy, hz = p.sleeve_w / 2 * MM, CARD_T / 2 * MM, p.sleeve_h / 2 * MM
    cards = "\n".join(
        f'<body name="c{k}"><freejoint/><geom class="card" type="box" size="{hx} {hy} {hz}" '
        f'mass="{CARD_MASS}"/></body>' for k in range(n_cards))
    tc = 4 * timestep
    return f"""
<mujoco>
  <option timestep="{timestep}" gravity="0 0 -9.81" cone="elliptic">
    <flag multiccd="enable"/>
  </option>
  <size memory="400M"/>
  <default>
    <geom solref="{tc} 1" solimp="0.95 0.99 0.0001" friction="0.35 0.001 0.0001" condim="3" rgba="0.6 0.7 0.9 1"/>
    <default class="card"><geom friction="0.22 0.001 0.0001" rgba="1 0.82 0.5 1"/></default>
  </default>
  <asset>{''.join(meshes.assets)}</asset>
  <worldbody>
    <geom type="plane" pos="0 0 {p.z_base * MM}" size="1 1 0.01"/>
    {''.join(static)}
    {cards}
  </worldbody>
</mujoco>"""


# ------------------------------------------------------------------- drop
@dataclass
class DropResult:
    left: list[int] = field(default_factory=list)     # card ids, back to front
    right: list[int] = field(default_factory=list)
    stuck: list[int] = field(default_factory=list)    # still inside the comb
    escaped: list[int] = field(default_factory=list)  # anywhere else
    lane: dict[int, int] = field(default_factory=dict)  # channel each card went down
    settle_time: float = 0.0
    final_pos: np.ndarray | None = None

    @property
    def ok(self) -> bool:
        return not self.stuck and not self.escaped


class Rig:
    """Compiled model, reusable for many drops."""

    def __init__(self, p: Params = Params(), n_cards: int | None = None, timestep: float = 1e-4):
        import mujoco
        self.mj = mujoco
        self.p = p
        self.n = n_cards or p.n_cards
        self.model = mujoco.MjModel.from_xml_string(build_xml(p, self.n, timestep))
        self.data = mujoco.MjData(self.model)

    def drop(self, deck: list[int], rng: random.Random, max_time: float = 3.0,
             offset: float | None = None) -> DropResult:
        """Release `deck` (deck[0] at the back) into the collar and wait for it to settle."""
        p, mj, d = self.p, self.mj, self.data
        mj.mj_resetData(self.model, d)
        # The deck starts in the hopper throat, resting just above the centre tips.
        throat = p.throat if p.hopper_h > 0 else p.depth
        slack = throat - p.deck_t
        lo = (p.depth - throat) / 2
        w_start = lo + (rng.uniform(0.3, slack - 0.3) if offset is None else offset) + p.card_pitch / 2
        z0 = (-p.tip_guard + 2.0 + p.sleeve_h / 2) * MM
        for k, card in enumerate(deck):
            q = d.qpos[7 * card: 7 * card + 7]
            q[:] = [rng.uniform(-0.5, 0.5) * MM, (w_start + k * p.card_pitch) * MM, z0, 1, 0, 0, 0]
        res = DropResult()
        z_gate = (p.z_hi + p.sleeve_h / 2) * MM      # card centre height as it reaches the ramps
        steps_per_check = int(0.01 / self.model.opt.timestep)
        t_quiet = 0.0
        while d.time < max_time:
            mj.mj_step(self.model, d, steps_per_check)
            pos = d.qpos.reshape(self.n, 7)[:, :3]
            for c in range(self.n):
                if c not in res.lane and pos[c, 2] < z_gate + 0.02:
                    res.lane[c] = int(pos[c, 1] / MM // p.pitch)
            speed = np.abs(d.qvel.reshape(self.n, 6)[:, :3]).max()
            t_quiet = t_quiet + 0.01 if speed < 0.01 else 0.0
            if t_quiet > 0.15:
                break
        res.settle_time = d.time
        pos = d.qpos.reshape(self.n, 7)[:, :3] / MM
        res.final_pos = pos.copy()
        floor_z = min(z for _, z in p.bin_floor_outline()) - 2
        for c in sorted(range(self.n), key=lambda c: pos[c, 1]):
            x, w, z = pos[c]
            inside = -1 < w < p.depth + 1 and z > floor_z
            if inside and x < -p.bx:
                res.left.append(c)
            elif inside and x > p.bx:
                res.right.append(c)
            elif abs(x) <= p.bx and z > floor_z:
                res.stuck.append(c)
            else:
                res.escaped.append(c)
        return res


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
