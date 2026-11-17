"""Pictures of the design: an annotated section and a 3-D view."""

from __future__ import annotations

import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon

from shuffler_design import Params, build_parts, resting_pile


def section(p: Params, path: str) -> None:
    """Front wall removed, looking along the stacking direction."""
    fig, ax = plt.subplots(figsize=(11, 9))
    for side in "LR":
        for pts in p.wall_outlines(side):
            ax.add_patch(Polygon(pts, fc="#e9e9e9", ec="none"))
        ax.add_patch(Polygon(p.finger_notch(side), fc="white", ec="none"))
        ax.add_patch(Polygon(p.bin_floor_outline(side), fc="#555", ec="k"))
        ax.add_patch(Polygon(p.resting_card(side), fc="#ffd27f", ec="#b36b00", alpha=0.8))
    mid = p.n_channels // 2
    ax.add_patch(Polygon(p.blade_outline(mid), fc="#bcd4ee", ec="#2a5d9f"))
    ax.add_patch(Polygon(p.blade_outline(1), fc="none", ec="#2a5d9f", ls=":"))
    ax.add_patch(Polygon(p.rib_outline("L"), fc="#d9534f", ec="k", alpha=0.85))
    ax.add_patch(Polygon(p.rib_outline("R"), fc="#3c8d40", ec="k", alpha=0.6))
    for sg in (-1, 1):
        ax.add_patch(Polygon(p.collar_wall(sg, full=(sg == 1)), fc="#777", ec="k"))
        ax.add_patch(Polygon(p.hopper_side_xz(sg), fc="#c9b8e8", ec="k"))
    for c in p.bar_holes() + [p.bin_bar, (-p.bin_bar[0], p.bin_bar[1])]:
        ax.add_patch(plt.Rectangle((c[0] - 3, c[1] - 3), 6, 6, fc="k"))
    # the deck at the moment of release, and a card landing on a left ramp
    ax.add_patch(plt.Rectangle((-p.sleeve_w / 2, -p.tip_guard + 2), p.sleeve_w, p.sleeve_h,
                               fc="#ffd27f", ec="#b36b00", alpha=0.5))
    top = p.landing_card_top()
    ax.add_patch(plt.Rectangle((-p.sleeve_w / 2, top - p.sleeve_h), p.sleeve_w, p.sleeve_h,
                               fc="none", ec="#b36b00", ls="--"))
    notes = [
        ("deck dropped in,\nshort edge down", (0, 60), (110, 75)),
        ("hopper", (p.cx + 1, 50), (110, 45)),
        ("blade tips: chevron,\ncentre blade highest", (0, p.tip_z(mid)), (95, 20)),
        ("collar wall (short on\nthe exit side)", (-p.cx - 6, -8), (-150, 25)),
        ("free fall: one card height,\nso the card can tip over", (-20, top - 40), (-150, -55)),
        ("ramp in a LEFT channel", (10, p.ramp_z(10, "L")), (80, -105)),
        ("ramp in a RIGHT channel\n(next channel along)", (22, p.ramp_z(22, "R") - 8), (70, -215)),
        ("left pile, resting\nagainst the end stop", p.bin_pt(40, 60), (-150, -110)),
        ("tie bars + wedges", p.bin_bar, (-150, -228)),
    ]
    for text, xy, xytext in notes:
        ax.annotate(text, xy, xytext, fontsize=9, ha="center",
                    arrowprops=dict(arrowstyle="->", color="#333"))
    ax.set_xlim(-185, 185)
    ax.set_ylim(p.z_base - 8, 105)
    ax.set_aspect("equal")
    ax.set_xlabel("mm")
    ax.set_title("Section through the comb shuffler (front wall removed)")
    fig.savefig(path, dpi=130, bbox_inches="tight")


def _tris(solid):
    verts, faces = solid.val().tessellate(0.3)
    v = np.array([(a.x, a.y, a.z) for a in verts])
    return v[np.array(faces)]


def _rasterise(tris, cols, view_dir, up, px_per_mm=4.0, margin=10):
    """Tiny orthographic z-buffer renderer (matplotlib cannot depth-sort solids)."""
    f = np.array(view_dir, float); f /= np.linalg.norm(f)
    r = np.cross(f, up); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    sx, sy, sz = tris @ r, tris @ u, tris @ f          # each (n, 3)
    x0, y0 = sx.min() - margin, sy.min() - margin
    W = int((sx.max() + margin - x0) * px_per_mm)
    H = int((sy.max() + margin - y0) * px_per_mm)
    sx, sy = (sx - x0) * px_per_mm, (sy - y0) * px_per_mm
    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    light = -f + 0.5 * u - 0.4 * r
    light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.abs(nrm @ light)
    img = np.ones((H, W, 3))
    zbuf = np.full((H, W), np.inf)
    for k in range(len(tris)):
        ax_, ay_, bx_, by_, cx_, cy_ = sx[k, 0], sy[k, 0], sx[k, 1], sy[k, 1], sx[k, 2], sy[k, 2]
        den = (by_ - cy_) * (ax_ - cx_) + (cx_ - bx_) * (ay_ - cy_)
        if abs(den) < 1e-9:
            continue
        i0, i1 = max(int(min(ax_, bx_, cx_)), 0), min(int(max(ax_, bx_, cx_)) + 1, W - 1)
        j0, j1 = max(int(min(ay_, by_, cy_)), 0), min(int(max(ay_, by_, cy_)) + 1, H - 1)
        X, Y = np.meshgrid(np.arange(i0, i1 + 1) + 0.5, np.arange(j0, j1 + 1) + 0.5)
        l0 = ((by_ - cy_) * (X - cx_) + (cx_ - bx_) * (Y - cy_)) / den
        l1 = ((cy_ - ay_) * (X - cx_) + (ax_ - cx_) * (Y - cy_)) / den
        l2 = 1 - l0 - l1
        z = l0 * sz[k, 0] + l1 * sz[k, 1] + l2 * sz[k, 2]
        sub = zbuf[j0:j1 + 1, i0:i1 + 1]
        hit = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6) & (z < sub)
        sub[hit] = z[hit]
        img[j0:j1 + 1, i0:i1 + 1][hit] = cols[k] * shade[k]
    return img[::-1]


def iso(p: Params, path: str) -> None:
    parts = build_parts(p)
    colours = {"slice": "#9ec1e6", "back": "#dcdcdc", "front": "#dcdcdc",
               "bar": "#555555", "wedge": "#d9534f", "foot": "#777777", "card": "#ffd27f",
               "hopper": "#c9b8e8", "upper": "#cfcfcf"}
    views = [(False, "Assembled", (0.55, -0.35, 0.75)),
             (True, "Front wall removed, a pile in each bin", (0.35, -0.3, 0.9)),
             (True, "From above: the comb", (0.3, -0.8, 0.5))]
    fig, axes = plt.subplots(1, 3, figsize=(20, 7.5))
    for ax, (hide_front, title, view) in zip(axes, views):
        items = [(n, s) for n, s in parts.items() if not (hide_front and n.startswith(("front", "upper_front")))]
        if hide_front and "pile" in title:
            items += [("card_L", resting_pile(p, "L")), ("card_R", resting_pile(p, "R"))]
        tris, cols = [], []
        for name, solid in items:
            t = _tris(solid)
            tris.append(t)
            cols.append(np.tile(matplotlib.colors.to_rgb(colours[name.split("_")[0]]), (len(t), 1)))
        # model frame is (x, up, depth); the viewer stands in front (+depth)
        ax.imshow(_rasterise(np.concatenate(tris), np.concatenate(cols),
                             view_dir=(-view[0], view[1], -view[2]), up=(0, 1, 0)))
        ax.set_axis_off()
        ax.set_title(title)
    fig.savefig(path, dpi=110, bbox_inches="tight")


def physics_frames(p: Params, path: str, seed: int = 1, times=(0.03, 0.10, 0.20, 0.35, 0.60, 1.50)) -> None:
    """Snapshots of one simulated drop: front view above, side view below."""
    import random
    import mujoco
    from physics_sim import MM, Rig
    rig = Rig(p)
    rig.drop(list(range(rig.n)), random.Random(seed), max_time=0.0)     # just places the deck
    d = rig.data
    first = int(rig.card_body[0])                                       # cards are found by name
    hx, hz = p.sleeve_w / 2, p.sleeve_h / 2
    outline = np.array([[-hx, 0, -hz], [hx, 0, -hz], [hx, 0, hz], [-hx, 0, hz], [-hx, 0, -hz]])
    c, mid = p.depth / 2, p.n_channels // 2

    def fan_line(steps, z):
        """Depth of the fan plane `steps` out from the centre, at height z."""
        return c + (p.fan_R - z) * np.tan(steps * p.fan_delta) if p.fan_R > 0 else c + steps * p.pitch

    fig, axes = plt.subplots(2, len(times), figsize=(4.2 * len(times), 10))
    for j, t in enumerate(times):
        while d.time < t:
            mujoco.mj_step(rig.model, d)
        front, side = axes[0][j], axes[1][j]
        for s_ in "LR":
            front.add_patch(Polygon(p.bin_floor_outline(s_), fc="#888"))
            front.add_patch(Polygon(p.rib_outline(s_), fc="none", ec="#d9534f" if s_ == "L" else "#3c8d40"))
        front.add_patch(Polygon(p.blade_outline(mid), fc="none", ec="#2a5d9f"))
        for sg in (-1, 1):
            front.add_patch(Polygon(p.hopper_side_xz(sg), fc="#c9b8e8"))
        for steps in range(-mid, p.n_channels - mid + 1):
            i = min(max(steps + mid - (1 if steps <= 0 else 0), 0), p.n_channels - 1)
            top = 0.0 if abs(steps) == mid else p.tip_z(i)
            zs = np.array([top, p.z_base])
            side.plot(fan_line(steps, zs), zs, color="k" if abs(steps) == mid else "#2a5d9f",
                      lw=0.9 if abs(steps) == mid else 0.5)
        for fr in (False, True):
            side.add_patch(Polygon(p.hopper_end_wz(fr), fc="#c9b8e8"))
        for k in range(rig.n):
            pts = outline @ d.xmat[first + k].reshape(3, 3).T + d.xpos[first + k] / MM
            col = plt.cm.viridis(k / rig.n)
            front.plot(pts[:, 0], pts[:, 2], color=col, lw=0.6)
            side.plot(pts[:, 1], pts[:, 2], color=col, lw=0.6)
        front.set_title(f"t = {t:.2f} s   front")
        side.set_title("side (colour = position in deck)")
        for ax, xl in ((front, (-165, 165)), (side, (c - 85, c + 85))):
            ax.set_xlim(*xl)
            ax.set_ylim(p.z_base - 5, 105)
            ax.set_aspect("equal")
            ax.set_xticks([])
            ax.set_yticks([])
    fig.suptitle("One simulated drop of 60 rigid cards (MuJoCo)")
    fig.savefig(path, dpi=80, bbox_inches="tight")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    section(Params(), f"{out}/section.png")
    iso(Params(), f"{out}/assembly.png")
    physics_frames(Params(), f"{out}/physics.png")
