#!/usr/bin/env python3
"""Render the profile hero: a black hole with matter streaming around it forever.

A thin disk of glowing gas orbits a black sphere, seen almost edge-on, and the
whole sky of stars slowly wheels around it. Gravity
bends the light from the far side of the disk up over the top of the hole and
under the bottom, which is what gives the picture its halo. The side of the
disk moving towards the viewer is brighter than the side moving away.

Behind the hole hangs the past year of GitHub contributions, drawn as GitHub
draws it: a square for each day, a column for each week, greener for busier
days. The year is split into two halves, one above the disk and one below. The
hole bends the picture of the squares nearest to it into arcs, and one after
another those squares let go, are drawn out into streaks and spiral in; each
grows back a little later, so the chart is forever being eaten.

    python3 scripts/hero.py            # writes assets/hero.svg
    python3 scripts/hero.py --fetch    # first refreshes scripts/year.json (needs GITHUB_TOKEN)

The SVG is a static file animated with CSS only (no scripts, no network, no
filters). Every streak of gas is a dashed ellipse whose dashes slide round at
its own orbital speed, faster near the hole; each pattern repeats exactly, so
the motion never jumps.
"""

import argparse
import datetime
import json
import math
import os
import pathlib
import random
import urllib.request

W, H = 960, 540  # 16:9
R = 84  # radius of the shadow; everything else is measured in these
TILT = 0.15  # how flattened the disk looks: 0 is edge-on, 1 is face-on
INNER, OUTER = 1.4, 5.3  # where the disk starts and ends
ORBIT = 3.4  # seconds for gas at radius 1 to go round once; further out is slower
STAR_RINGS = 9  # the sky turns in this many rings
STAR_ORBIT = 26  # seconds for a star at radius 1 to circle the hole; further out is much slower
STAR_DENSITY = 0.00042  # stars per square pixel
PITCH, TILE, ROUND = 27, 22, 4  # the chart: distance between squares, their size, how rounded their corners are
TOP_WEEKS = 27  # weeks in the half of the year above the disk; the rest go below
BAND_GAP = 96  # the space between the two halves, where the disk lies
LENS, LENS_REACH = 150, 200  # how far out the hole pushes the picture of what is right behind it, and how soon that fades
CAPTURE = 330  # squares whose picture is nearer than this fall in
FALL = 8  # seconds a square takes to spiral in once it lets go
SWIRL = 450  # degrees it turns on the way
REST = ((185, 14), (230, 22), (280, 36), (CAPTURE, 60))  # (distance, seconds from one fall to the next): nearer squares fall more often
GREENS = ("#0e4429", "#006d32", "#26a641", "#39d353")  # GitHub's four shades, quietest first
SEED = 3

USER = "milinddethe15"
DATA = pathlib.Path(__file__).resolve().parent / "year.json"

# Gas colour from the side rushing towards the viewer (left) to the side receding (right).
HOT = ("#fffaf0", "#ffe3ad", "#ffb65c", "#f07a1f", "#a3360b")
SKY = "#150d22"  # the faint tint of the sky behind the hole
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


def fetch():
    """Save the past year of contributions as {"from": first day, "levels": a digit 0-4 for each day}."""
    query = "{user(login:\"%s\"){contributionsCollection{contributionCalendar{weeks{contributionDays{date contributionLevel}}}}}}" % USER
    token = os.environ.get("GITHUB_TOKEN") or os.environ["GH_TOKEN"]
    request = urllib.request.Request("https://api.github.com/graphql", json.dumps({"query": query}).encode(),
                                     {"Authorization": f"bearer {token}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        weeks = json.load(response)["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [day for week in weeks for day in week["contributionDays"]]
    scale = ("NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE")
    DATA.write_text(json.dumps({"from": days[0]["date"], "levels": "".join(str(scale.index(day["contributionLevel"])) for day in days)}) + "\n")


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


def lens(x, y):
    """Where a point behind the hole appears to be: pushed outwards, so nothing shows inside a ring around the hole."""
    r = math.hypot(x, y) or 1e-9
    k = math.sqrt(r * r + LENS ** 2 * math.exp(-(r / LENS_REACH) ** 2)) / r
    return x * k, y * k


def falls():
    """Keyframes for a square's life, one set for each resting time: let go, spiral in, stay away a moment, grow back, rest.

    A square is drawn lying on the x axis of its own turned frame, so squeezing x carries it to the hole
    and thins it, while stretching y draws it out along its path.
    """
    out = []
    for n, (_, cycle) in enumerate(REST):
        frames = ["0%{transform:rotate(0deg) scale(1,1);opacity:1}"]
        for k in range(1, 21):
            u = k / 20
            look = ";opacity:1" if k == 19 else ";opacity:0" if k == 20 else ""
            frames.append(f"{100 * FALL * u / cycle:.3f}%{{transform:rotate({num(-SWIRL * u ** 2.5)}deg) "
                          f"scale({num(1 - u ** 2.2)},{num((1 + 1.6 * u ** 1.5) * (1 - u ** 8))}){look}}}")
        back = 100 * (FALL + 1) / cycle
        frames.append(f"{back:.3f}%{{transform:rotate(0deg) scale(1,1);opacity:0}}")
        frames.append(f"{back + 100 * 2.5 / cycle:.3f}%,100%{{transform:rotate(0deg) scale(1,1);opacity:1}}")
        out.append(f".c{n}{{animation:f{n} {cycle}s linear infinite}}@keyframes f{n}{{{''.join(frames)}}}")
    return "".join(out)


def chart(rng, shift):
    """The year of contributions, bent round the hole. Far squares are still; near ones are set up to fall."""
    year = json.loads(DATA.read_text())
    first = datetime.date.fromisoformat(year["from"])
    lead = (first.weekday() + 1) % 7  # GitHub's weeks start on Sunday
    left, half = -TOP_WEEKS * PITCH / 2, TILE / 2 - ROUND
    still, near, words = {}, {}, []

    def place(week, weekday):
        band, column = (0, week) if week < TOP_WEEKS else (1, week - TOP_WEEKS)
        top = BAND_GAP / 2 if band else -BAND_GAP / 2 - 7 * PITCH
        return left + (column + 0.5) * PITCH, top + (weekday + 0.5) * PITCH

    for day, level in enumerate(year["levels"]):
        x, y = place(*divmod(day + lead, 7))
        cx, cy = lens(x, y)
        r = math.hypot(cx, cy)
        if r >= CAPTURE:
            still.setdefault(level, []).append(f"M{num(cx - half)} {num(cy - half)}h{num(2 * half)}v{num(2 * half)}h{num(-2 * half)}z")
            continue
        # Drawn in a frame turned so that the square lies on the x axis, with its edges bent the way the lens bends them.
        cos, sin = cx / r, cy / r
        def seen(px, py):
            px, py = lens(px, py)
            return px * cos + py * sin, py * cos - px * sin
        corners = [(x - half, y - half), (x + half, y - half), (x + half, y + half), (x - half, y + half)]
        d = "M{} {}".format(*map(num, seen(*corners[0])))
        for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
            (px, py), (qx, qy), (mx, my) = seen(ax, ay), seen(bx, by), seen((ax + bx) / 2, (ay + by) / 2)
            kx, ky = 2 * mx - (px + qx) / 2, 2 * my - (py + qy) / 2  # the curve's handle, placed so it passes through the bent midpoint
            bend = math.hypot(kx - (px + qx) / 2, ky - (py + qy) / 2)
            d += f"Q{num(kx)} {num(ky)} {num(qx)} {num(qy)}" if bend > 0.3 else f"L{num(qx)} {num(qy)}"
        rest = next(n for n, (reach, _) in enumerate(REST) if r < reach)
        near.setdefault(level, []).append(f'<g transform="rotate({num(math.degrees(math.atan2(cy, cx)))})"><path class="c{rest}" d="{d}z" '
                                          f'style="animation-delay:{num(-rng.uniform(0, REST[rest][1]) - shift)}s"/></g>')

    weeks = (len(year["levels"]) + lead + 6) // 7
    for week in range(weeks):
        monday = first + datetime.timedelta(days=7 * week - lead)
        starts_band = week in (0, TOP_WEEKS)
        if starts_band or monday.month != (monday - datetime.timedelta(days=7)).month:
            if starts_band and (monday + datetime.timedelta(days=14)).month != monday.month:
                continue  # no room before the next month's name
            x, y = place(week, 0)
            x, y = lens(x - TILE / 2, y - PITCH / 2 - 5 if week < TOP_WEEKS else y + 6.5 * PITCH + 11)
            words.append(f'<text x="{num(x)}" y="{num(y)}">{monday.strftime("%b")}</text>')
    for band in (0, TOP_WEEKS):
        for weekday, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
            x, y = place(band, weekday)
            words.append(f'<text x="{num(x - PITCH / 2 - 6)}" y="{num(y + 3.5)}" text-anchor="end">{name}</text>')
    tiles = "".join(f'<g class="l{level}"><path d="{"".join(still.get(level, []))}"/>{"".join(near.get(level, []))}</g>' for level in "01234")
    return f'<g class="chart">{tiles}{"".join(words)}</g>'


def render(at_time=None):
    """The whole SVG. With `at_time`, a frozen frame from that many seconds in."""
    rng = random.Random(SEED)
    shift = at_time or 0
    sky = stars(random.Random(SEED + 1), shift)
    year = chart(random.Random(SEED + 2), shift)

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
                f'<stop offset="{num(inner + 0.015)}" stop-color="{HOT[0]}" stop-opacity="{num(0.95 * strength)}"/>'
                f'<stop offset="{num(inner + (reach - inner) * 0.16)}" stop-color="{peak_colour}" stop-opacity="{num(0.72 * strength)}"/>'
                f'<stop offset="{num(inner + (reach - inner) * 0.5)}" stop-color="{HOT[3]}" stop-opacity="{num(0.3 * strength)}"/>'
                f'<stop offset="{num(reach)}" stop-color="{HOT[4]}" stop-opacity="0"/></radialGradient>')

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
        f'<radialGradient id="sky" r=".8"><stop offset="0" stop-color="{SKY}"/><stop offset=".55" stop-color="#080712"/><stop offset="1" stop-color="{BACKGROUND}"/></radialGradient>'
        f'<radialGradient id="haze"><stop offset="0" stop-color="{HOT[2]}" stop-opacity=".2"/><stop offset=".5" stop-color="{HOT[3]}" stop-opacity=".08"/><stop offset="1" stop-color="{HOT[3]}" stop-opacity="0"/></radialGradient>'
        + ring_glow("flat", INNER / OUTER, HOT[2])
        + ring_glow("core", INNER / 2.7, HOT[1])
        + ring_glow("arc", 1.03 / 2.0, HOT[1])
        + ring_glow("low", 1.03 / 1.4, HOT[2], strength=0.6)
        + f'<radialGradient id="near"><stop offset="0" stop-color="{HOT[0]}" stop-opacity=".5"/><stop offset="1" stop-color="{HOT[2]}" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="far"><stop offset="0" stop-color="#03040a" stop-opacity=".5"/><stop offset="1" stop-color="#03040a" stop-opacity="0"/></radialGradient>'
    )
    style = (
        "ellipse[pathLength]{fill:none;stroke:url(#gas);stroke-linecap:round;animation:orbit linear infinite}.b{stroke-linecap:butt}"
        "@keyframes orbit{to{stroke-dashoffset:100}}"
        ".sky{animation:sky linear infinite}@keyframes sky{to{transform:rotate(-360deg)}}"
        f".chart path{{stroke-width:{2 * ROUND};stroke-linejoin:round}}.l0{{fill:#fff;stroke:#fff;opacity:.07}}"
        + "".join(f".l{k + 1}{{fill:{c};stroke:{c}}}" for k, c in enumerate(GREENS))
        + ".chart text{font:10px -apple-system,'Segoe UI',Helvetica,Arial,sans-serif;fill:#9198a1;fill-opacity:.85}" + falls() +
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
        f'<circle r="{num(R * 1.025)}" fill="none" stroke="{HOT[1]}" stroke-width="3.2" stroke-opacity=".28"/>'
        f'<circle r="{num(R * 1.02)}" fill="none" stroke="{HOT[0]}" stroke-width="1.1" stroke-opacity=".95"/>'
        # The chart hangs behind the disk, but its squares fall in front of the hole and its halo.
        f'{year}'
        f'<g clip-path="url(#disk)"><ellipse rx="{num(flat_rx)}" ry="{num(flat_ry)}" fill="url(#flat)"/>'
        f'<ellipse rx="{num(2.7 * R)}" ry="{num(2.7 * R * TILT)}" fill="url(#core)"/>'
        # Against the black of the hole the gas has nothing behind it to add to, so it gets a second coat there.
        f'<g clip-path="url(#lap)" opacity=".85"><ellipse rx="{num(flat_rx)}" ry="{num(flat_ry)}" fill="url(#flat)"/>'
        f'<ellipse rx="{num(2.7 * R)}" ry="{num(2.7 * R * TILT)}" fill="url(#core)"/></g>'
        f'<ellipse cx="{num(-2.1 * R)}" rx="{num(2.6 * R)}" ry="{num(0.36 * R)}" fill="url(#near)"/>'
        f'{"".join(disk)}'
        f'<ellipse cx="{num(3.2 * R)}" rx="{num(2.6 * R)}" ry="{num(0.7 * R)}" fill="url(#far)"/></g>'
    )
    label = ("A black hole: a disk of glowing gas streams around a dark sphere, its light bent into a halo over the top. "
             "Behind it hangs a year of GitHub contributions, whose squares bend round the hole, break away and spiral in")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {y0} {W} {H}" width="{W}" height="{H}" role="img" aria-label="{label}">'
            f'<title>{label}</title><style>{style}</style><defs>{defs}</defs><g clip-path="url(#card)">{body}</g></svg>\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", help="write the SVG here instead of assets/")
    ap.add_argument("--at", type=float, help="write a frozen frame from this many seconds in")
    ap.add_argument("--fetch", action="store_true", help="refresh the saved year of contributions from GitHub first")
    args = ap.parse_args()
    if args.fetch:
        fetch()

    out = pathlib.Path(args.out) if args.out else pathlib.Path(__file__).resolve().parent.parent / "assets"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "hero.svg"
    path.write_text(render(args.at))
    print(f"wrote {path} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
