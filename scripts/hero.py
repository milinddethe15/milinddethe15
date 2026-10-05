#!/usr/bin/env python3
"""Render the profile hero: a black hole with matter streaming around it forever.

A thin disk of glowing gas orbits a black sphere, seen almost edge-on, and the
whole sky of stars slowly wheels around it. Gravity
bends the light from the far side of the disk up over the top of the hole and
under the bottom, which is what gives the picture its halo. The side of the
disk moving towards the viewer is brighter than the side moving away.

    python3 scripts/hero.py            # writes assets/hero.svg

The SVG is a static file animated with CSS only (no scripts, no network, no
filters), so nothing has to run on a schedule. Every streak of gas is a dashed
ellipse whose dashes slide round at its own orbital speed, faster near the
hole; each pattern repeats exactly, so the motion never jumps.
"""

import argparse
import math
import pathlib
import random

W, H = 960, 540  # 16:9
R = 84  # radius of the shadow; everything else is measured in these
TILT = 0.15  # how flattened the disk looks: 0 is edge-on, 1 is face-on
INNER, OUTER = 1.4, 5.3  # where the disk starts and ends
ORBIT = 3.4  # seconds for gas at radius 1 to go round once; further out is slower
STAR_RINGS = 9  # the sky turns in this many rings
STAR_ORBIT = 26  # seconds for a star at radius 1 to circle the hole; further out is much slower
STAR_DENSITY = 0.00042  # stars per square pixel
SEED = 3

# Gas colour from the side rushing towards the viewer (left) to the side receding (right).
HOT = ("#fffaf0", "#ffe3ad", "#ffb65c", "#f07a1f", "#a3360b")
BACKGROUND = "#03040a"


def num(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def dashes(rng, pieces, broad=False):
    """A random dash pattern that adds up to exactly 100, so it wraps without a seam."""
    dash, gap = ((18, 40), (2, 7)) if broad else ((1.5, 14), (1.5, 9))
    parts = [rng.uniform(*dash) if k % 2 == 0 else rng.uniform(*gap) for k in range(2 * pieces)]
    total = sum(parts)
    return " ".join(num(p * 100 / total) for p in parts[:-1]) + " " + num(100 - sum(float(num(p * 100 / total)) for p in parts[:-1]))


def streak(rng, rx, ry, cy, width, opacity, period, broad=False):
    """One ring of gas. Broad rings are soft bands with square ends; fine ones are grain."""
    pattern = dashes(rng, 3, True) if broad else dashes(rng, rng.randint(4, 7))
    return (f'<ellipse{' class="b"' if broad else ""} cy="{num(cy)}" rx="{num(rx)}" ry="{num(ry)}" pathLength="100" stroke-width="{num(width)}" '
            f'stroke-opacity="{num(opacity)}" stroke-dasharray="{pattern}" '
            f'style="animation-duration:{num(period)}s;animation-delay:{num(-rng.uniform(0, period))}s"/>')


def stars(rng, shift):
    """The sky, slowly wheeling around the hole: stars nearer to it circle faster, like the gas.

    Stars are grouped into rings by distance and each ring turns as one piece, so the whole sky
    costs a handful of animations.
    """
    reach = math.hypot(W, H) / 2 + 10
    edges = [R * 1.3 * (reach / (R * 1.3)) ** (k / STAR_RINGS) for k in range(STAR_RINGS + 1)]
    out = []
    for inner, outer in zip(edges, edges[1:]):
        period = STAR_ORBIT * ((inner + outer) / 2 / R) ** 1.5
        dots = []
        for _ in range(round(STAR_DENSITY * math.pi * (outer ** 2 - inner ** 2))):
            r, a = math.sqrt(rng.uniform(inner ** 2, outer ** 2)), rng.uniform(0, 2 * math.pi)
            size = rng.choice((0.35, 0.45, 0.45, 0.6, 0.6, 0.8, 1.1, 1.5))
            tint = rng.choice(("#ffffff", "#ffffff", "#dbe7ff", "#ffe9cf"))
            glow = rng.uniform(0.3, 0.95)
            twinkle = f' class="tw" style="animation-delay:{num(-rng.uniform(0, 6))}s"' if rng.random() < 0.08 else ""
            dots.append(f'<circle cx="{num(r * math.cos(a))}" cy="{num(r * math.sin(a))}" r="{size}" fill="{tint}" opacity="{num(glow)}"{twinkle}/>')
        out.append(f'<g class="sky" style="animation-duration:{num(period)}s;animation-delay:{num(-shift)}s">{"".join(dots)}</g>')
    return "".join(out)


def render(at_time=None):
    """The whole SVG. With `at_time`, a frozen frame from that many seconds in."""
    rng = random.Random(SEED)
    shift = at_time or 0
    sky = stars(random.Random(SEED + 1), shift)

    def period(r):
        return ORBIT * r ** 1.5

    # The flat disk: many fine streaks, denser and brighter towards the hole.
    disk = []
    for i in range(16):  # wide, faint bands give the gas its body
        f = (i / 15) ** 1.1
        r = INNER + 0.05 + (OUTER - INNER - 0.3) * f
        disk.append(streak(rng, r * R, r * R * TILT, 0, rng.uniform(6, 11) * (1 + f), (0.26 - 0.2 * f) * rng.uniform(0.6, 1), period(r), True))
    for i in range(56):  # fine streaks give it grain
        f = (i / 55) ** 1.3
        r = INNER + (OUTER - INNER) * f
        disk.append(streak(rng, r * R, r * R * TILT, 0, rng.uniform(0.4, 1.3), (0.8 - 0.68 * f) * rng.uniform(0.45, 1), period(r)))
    # Light from the far side of the disk, bent over the top of the hole and, more faintly, under it.
    over = [streak(rng, r * R, r * R * 0.94, -0.02 * R, rng.uniform(5, 9), 0.26 * (1 - (r - 1.05) / 0.95) * rng.uniform(0.6, 1), period(r), True)
            for r in (1.1 + 0.8 * i / 5 for i in range(6))]
    over += [streak(rng, r * R, r * R * 0.94, -0.02 * R, rng.uniform(0.4, 1.2), 0.75 * (1 - (r - 1.05) / 1.0) * rng.uniform(0.45, 1), period(r))
             for r in (1.06 + 0.86 * (i / 17) ** 1.2 for i in range(18))]
    under = [streak(rng, r * R, r * R * 0.985, 0, rng.uniform(0.5, 1.1), (0.7 - (r - 1.05) * 1.5) * rng.uniform(0.6, 1), period(r))
             for r in (1.05 + 0.3 * i / 5 for i in range(6))]

    def ring_glow(name, inner, peak_colour, reach=1.0, strength=1.0):
        """A soft ring: dark inside `inner` (a fraction of the radius), brightest just outside it."""
        return (f'<radialGradient id="{name}"><stop offset="{num(inner - 0.02)}" stop-color="{peak_colour}" stop-opacity="0"/>'
                f'<stop offset="{num(inner + 0.015)}" stop-color="#fff6e5" stop-opacity="{num(0.95 * strength)}"/>'
                f'<stop offset="{num(inner + (reach - inner) * 0.16)}" stop-color="{peak_colour}" stop-opacity="{num(0.72 * strength)}"/>'
                f'<stop offset="{num(inner + (reach - inner) * 0.5)}" stop-color="#f07a1f" stop-opacity="{num(0.3 * strength)}"/>'
                f'<stop offset="{num(reach)}" stop-color="#a3360b" stop-opacity="0"/></radialGradient>')

    gas = "".join(f'<stop offset="{num(k / (len(HOT) - 1))}" stop-color="{c}"/>' for k, c in enumerate(HOT))
    x0, y0 = -W / 2, -H / 2
    defs = (
        f'<clipPath id="card"><rect x="{x0}" y="{y0}" width="{W}" height="{H}" rx="20"/></clipPath>'
        # The disk passes in front of the lower half of the hole and behind the upper half.
        f'<clipPath id="disk"><path clip-rule="evenodd" d="M{x0} {y0}H{W / 2}V{H / 2}H{x0}ZM{-R} 0A{R} {R} 0 0 1 {R} 0Z"/></clipPath>'
        f'<clipPath id="lap"><path d="M{-R} 0A{R} {R} 0 0 0 {R} 0Z"/></clipPath>'
        f'<clipPath id="up"><rect x="{x0}" y="{y0}" width="{W}" height="{H / 2 + 0.6}"/></clipPath>'
        f'<clipPath id="down"><rect x="{x0}" y="-0.6" width="{W}" height="{H / 2 + 0.6}"/></clipPath>'
        f'<linearGradient id="gas" gradientUnits="userSpaceOnUse" x1="{num(-OUTER * R)}" x2="{num(OUTER * R)}">{gas}</linearGradient>'
        f'<radialGradient id="sky" r=".8"><stop offset="0" stop-color="#150d22"/><stop offset=".55" stop-color="#080712"/><stop offset="1" stop-color="{BACKGROUND}"/></radialGradient>'
        '<radialGradient id="haze"><stop offset="0" stop-color="#ff9a3c" stop-opacity=".2"/><stop offset=".5" stop-color="#d9480f" stop-opacity=".08"/><stop offset="1" stop-color="#d9480f" stop-opacity="0"/></radialGradient>'
        + ring_glow("flat", INNER / OUTER, "#ffc876")
        + ring_glow("core", INNER / 2.7, "#ffe3ad")
        + ring_glow("arc", 1.03 / 2.0, "#ffd08a")
        + ring_glow("low", 1.03 / 1.4, "#ffb65c", strength=0.6)
        + '<radialGradient id="near"><stop offset="0" stop-color="#fff3d6" stop-opacity=".5"/><stop offset="1" stop-color="#ffb65c" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="far"><stop offset="0" stop-color="#03040a" stop-opacity=".5"/><stop offset="1" stop-color="#03040a" stop-opacity="0"/></radialGradient>'
    )
    style = (
        "ellipse[pathLength]{fill:none;stroke:url(#gas);stroke-linecap:round;animation:orbit linear infinite}.b{stroke-linecap:butt}"
        "@keyframes orbit{to{stroke-dashoffset:100}}"
        ".sky{animation:sky linear infinite}@keyframes sky{to{transform:rotate(-360deg)}}"
        ".tw{animation:tw 6s ease-in-out infinite}@keyframes tw{50%{opacity:.15}}"
        + (f"*{{animation-play-state:paused!important}}ellipse[pathLength]{{animation-delay:{-shift}s!important}}" if at_time is not None else "")
        + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    )
    flat_rx, flat_ry = OUTER * R, OUTER * R * TILT
    body = (
        f'<rect x="{x0}" y="{y0}" width="{W}" height="{H}" fill="url(#sky)"/>{sky}'
        f'<ellipse rx="{num(OUTER * R * 1.25)}" ry="{num(R * 2.6)}" fill="url(#haze)"/>'
        # Bent light: the big arc over the top, the thin one underneath.
        f'<g clip-path="url(#up)"><ellipse cy="{num(-0.02 * R)}" rx="{2.0 * R}" ry="{num(2.0 * R * 0.94)}" fill="url(#arc)"/>{"".join(over)}</g>'
        f'<g clip-path="url(#down)"><ellipse rx="{num(1.4 * R)}" ry="{num(1.4 * R * 0.985)}" fill="url(#low)"/>{"".join(under)}</g>'
        f'<circle r="{R}" fill="#000"/>'
        # The ring of light that grazes the hole.
        f'<circle r="{num(R * 1.025)}" fill="none" stroke="#ffe9c7" stroke-width="3.2" stroke-opacity=".28"/>'
        f'<circle r="{num(R * 1.02)}" fill="none" stroke="#fff6e5" stroke-width="1.1" stroke-opacity=".95"/>'
        f'<g clip-path="url(#disk)"><ellipse rx="{num(flat_rx)}" ry="{num(flat_ry)}" fill="url(#flat)"/>'
        f'<ellipse rx="{num(2.7 * R)}" ry="{num(2.7 * R * TILT)}" fill="url(#core)"/>'
        # Against the black of the hole the gas has nothing behind it to add to, so it gets a second coat there.
        f'<g clip-path="url(#lap)" opacity=".85"><ellipse rx="{num(flat_rx)}" ry="{num(flat_ry)}" fill="url(#flat)"/>'
        f'<ellipse rx="{num(2.7 * R)}" ry="{num(2.7 * R * TILT)}" fill="url(#core)"/></g>'
        f'<ellipse cx="{num(-2.1 * R)}" rx="{num(2.6 * R)}" ry="{num(0.36 * R)}" fill="url(#near)"/>'
        f'{"".join(disk)}'
        f'<ellipse cx="{num(3.2 * R)}" rx="{num(2.6 * R)}" ry="{num(0.7 * R)}" fill="url(#far)"/></g>'
    )
    label = "A black hole: a disk of glowing gas streams around a dark sphere, its light bent into a halo over the top"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {y0} {W} {H}" width="{W}" height="{H}" role="img" aria-label="{label}">'
            f'<title>{label}</title><style>{style}</style><defs>{defs}</defs><g clip-path="url(#card)">{body}</g></svg>\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", help="write the SVG here instead of assets/")
    ap.add_argument("--at", type=float, help="write a frozen frame from this many seconds in")
    args = ap.parse_args()

    out = pathlib.Path(args.out) if args.out else pathlib.Path(__file__).resolve().parent.parent / "assets"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "hero.svg"
    path.write_text(render(args.at))
    print(f"wrote {path} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
