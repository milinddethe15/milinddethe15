#!/usr/bin/env python3
"""Render the contribution chart in 3D: the last year of GitHub contributions as a field of bars.

It is the chart from the profile page, one column per week with Sunday at the
back, in the same greens and with the same month and weekday names. Every day
with contributions stands up as a bar, taller the more there were, and the whole
chart sways slowly from side to side so the depth can be seen. The weekday names
sit at the right-hand end, not the left as on the profile, because that end is
the one nearest the viewer and bars would hide them at the other.

    python3 scripts/contributions.py            # writes assets/contributions.svg

The SVG is animated with CSS only (no scripts, no network, no filters), and the
swaying is real geometry, not frames:

- The ground is one group, flattened and turned: scaleY(TILT) rotate(angle).
  The names are written on it, so they lie flat and turn with it.
- The top of a bar is a piece of ground slid straight up the screen. Inside the
  turning ground that is: undo the turn, lift, redo the turn.
- The side of a bar is a rectangle lying on the ground, hinged along its foot,
  then sheared and squashed until it stands upright on screen:
  skewX(angle) scaleY(-cos(angle) / TILT).

SVG paints in file order and has no depth, so the bars are written far to near.
That order holds for as long as the chart is seen from between its front and its
right-hand end, which is why it sways and does not spin.

The token comes from GITHUB_TOKEN or GH_TOKEN, or from the gh CLI if neither is set.
"""

import argparse
import calendar
import json
import math
import os
import pathlib
import subprocess
import urllib.request

USER = "milinddethe15"
W, H = 960, 480
MARGIN = 28  # clear space between the chart and the edge of the picture
TILT = 0.56  # how flattened the ground looks: 0 is seen from the side, 1 from straight above
FACING, SWING = 30, 13  # degrees the chart is turned away from square-on, and how far it sways either side of that
SWAY = 18  # seconds to sway there and back
STEPS = 48  # keyframes per sway
CELL, GAP = 10, 1.2  # one day's square of ground, and the strip left clear on each side of it
LOW, HIGH = 3, 56  # a bar is this tall for no contributions at all and for the busiest day; in between it follows the square root
EDGE = {"left": 5, "right": 27, "back": 5, "front": 16}  # how far the slab reaches past the days, leaving room for the names
THICK = 4  # how deep the slab is

SPACE = "#03040a"
SLAB = "#0d1117"
GREENS = ("#161b22", "#0e4429", "#006d32", "#26a641", "#39d353")  # GitHub's own, from no contributions to the top quarter
SHADE = {"front": 0.22, "end": 0.45}  # how much darker than its top a bar's two visible sides are
INK = "#8b949e"
LEVELS = ("NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE")
QUERY = ("query($login:String!){user(login:$login){contributionsCollection{contributionCalendar"
         "{weeks{contributionDays{date weekday contributionCount contributionLevel}}}}}}")

LIFT = math.sqrt(1 - TILT * TILT)  # how far up the screen one unit of height reaches


def num(x, places=2):
    return f"{x:.{places}f}".rstrip("0").rstrip(".")


def mix(a, b, t):
    """Colour `a` moved a share `t` of the way to colour `b`."""
    return "#" + "".join(f"{round(int(a[k:k + 2], 16) * (1 - t) + int(b[k:k + 2], 16) * t):02x}" for k in (1, 3, 5))


def contributions(user):
    """The year as a list of weeks, each a list of (date, weekday, contributions, level) with Sunday as 0 and level 0 to 4."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "contributions"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        reply = json.load(response)
    if reply.get("errors"):
        raise SystemExit(f"GitHub refused the query: {reply['errors'][0]['message']}")
    weeks = reply["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [[(day["date"], day["weekday"], day["contributionCount"], LEVELS.index(day["contributionLevel"])) for day in week["contributionDays"]]
            for week in weeks]


def months(weeks):
    """Which columns carry a month's name: the first week to start in each month, unless the next name would run into it."""
    starts, last = [], None
    for column, week in enumerate(weeks):
        month = int(week[0][0][5:7])
        if month != last:
            starts.append((column, calendar.month_abbr[month]))
            last = month
    return [(column, name) for (column, name), (after, _) in zip(starts, starts[1:] + [(len(weeks) + 3, "")]) if after - column >= 3]


def height(count, peak):
    """How tall the bar is for a day with `count` contributions, when the busiest day had `peak`."""
    return LOW + (HIGH - LOW) * math.sqrt(count / peak)


def angle_at(time):
    return FACING + SWING * math.sin(2 * math.pi * time / SWAY)


def pose(angle):
    """The transform of each kind of part once the chart has turned `angle` degrees: ground, top, and the two ways a side can run."""
    def stand(by):
        return f"skewX({num(by)}deg) scaleY({num(-math.cos(math.radians(by)) / TILT, 4)})"
    return {
        "a": f"scaleY({TILT}) rotate({num(angle)}deg)",
        "r": f"rotate({num(-angle)}deg) translate(0,var(--h)) rotate({num(angle)}deg)",
        "x": f"translate(var(--x),var(--y)) {stand(angle)}",
        "y": f"translate(var(--x),var(--y)) rotate(90deg) {stand(angle + 90)}",
    }


def side(runs, x, y, length, top, fill, bottom=0):
    """An upright face hinged at (x, y) and running along the x or y axis, from `bottom` up to `top`."""
    return (f'<rect class="{runs}" style="--x:{num(x)}px;--y:{num(y)}px" y="{num(bottom * LIFT)}" width="{num(length)}" '
            f'height="{num((top - bottom) * LIFT)}" fill="{fill}"/>')


def box(x0, y0, x1, y1, z0, z1, top, front, end):
    """A box as it is seen from between its front and its right-hand end: those two sides, then the top if it has a colour."""
    parts = side("y", x1, y0, y1 - y0, z1, end, z0) + side("x", x0, y1, x1 - x0, z1, front, z0)
    if top:
        parts += (f'<rect class="r" style="--h:{num(-z1 * LIFT / TILT)}px" x="{num(x0)}" y="{num(y0)}" width="{num(x1 - x0)}" '
                  f'height="{num(y1 - y0)}" fill="{top}"/>')
    return parts


def render(weeks, at_time=None):
    peak = max(count for week in weeks for _, _, count, _ in week) or 1
    x0, y0 = -EDGE["left"], -EDGE["back"]
    x1, y1 = len(weeks) * CELL + EDGE["right"], 7 * CELL + EDGE["front"]

    flat, bars = "", ""
    for column, week in enumerate(weeks):
        for _, weekday, count, level in week:
            x, y = column * CELL + GAP, weekday * CELL + GAP
            if count:
                bars += box(x, y, x + CELL - 2 * GAP, y + CELL - 2 * GAP, 0, height(count, peak), GREENS[level],
                            mix(GREENS[level], "#000000", SHADE["front"]), mix(GREENS[level], "#000000", SHADE["end"]))
            else:
                flat += f"M{num(x)} {num(y)}h{num(CELL - 2 * GAP)}v{num(CELL - 2 * GAP)}h{num(2 * GAP - CELL)}z"
    names = "".join(f'<text x="{column * CELL + GAP}" y="{7 * CELL + 10}">{name}</text>' for column, name in months(weeks))
    names += "".join(f'<text x="{len(weeks) * CELL + 4}" y="{num((weekday + 0.5) * CELL + 3)}">{calendar.day_abbr[weekday - 1]}</text>' for weekday in (1, 3, 5))
    chart = (
        f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="{SLAB}"/><path fill="{GREENS[0]}" d="{flat}"/>'
        f'<g fill="{INK}" font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',Helvetica,Arial,sans-serif" font-size="8.4">{names}</g>'
        + box(x0, y0, x1, y1, -THICK, 0, None, mix(SLAB, SPACE, 0.35), mix(SLAB, SPACE, 0.7)) + bars
    )

    # Fit the picture round everything the chart covers on screen over the whole sway.
    centre = (x0 + x1) / 2, (y0 + y1) / 2
    sway = [angle_at(SWAY * k / STEPS) for k in range(STEPS + 1)]
    corners = [(x - centre[0], y - centre[1], z) for x in (x0, x1) for y in (y0, y1) for z in (-THICK, HIGH)]
    across = [x * math.cos(a) - y * math.sin(a) for a in map(math.radians, sway) for x, y, _ in corners]
    down = [TILT * (x * math.sin(a) + y * math.cos(a)) - z * LIFT for a in map(math.radians, sway) for x, y, z in corners]
    scale = min((W - 2 * MARGIN) / (max(across) - min(across)), (H - 2 * MARGIN) / (max(down) - min(down)))
    shift = -scale * (max(across) + min(across)) / 2, -scale * (max(down) + min(down)) / 2

    frozen = at_time is not None
    style = "".join(f".{part}{{transform:{transform}}}" for part, transform in pose(angle_at(at_time or 0)).items())
    if not frozen:
        style += (
            f".a,.r,.x,.y{{animation:{SWAY}s linear infinite}}.a{{animation-name:a}}.r{{animation-name:r}}.x{{animation-name:x}}.y{{animation-name:y}}"
            + "".join(f"@keyframes {part}{{" + "".join(f"{num(100 * k / STEPS, 4)}%{{transform:{pose(angle)[part]}}}" for k, angle in enumerate(sway)) + "}"
                      for part in "arxy")
            + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
        )

    left, top = -W / 2, -H / 2
    defs = (
        f'<clipPath id="card"><rect x="{left}" y="{top}" width="{W}" height="{H}" rx="20"/></clipPath>'
        f'<radialGradient id="sky" r=".8"><stop offset="0" stop-color="#0c1422"/><stop offset=".55" stop-color="#070a13"/><stop offset="1" stop-color="{SPACE}"/></radialGradient>'
    )
    body = (
        f'<rect x="{left}" y="{top}" width="{W}" height="{H}" fill="url(#sky)"/>'
        f'<g transform="translate({num(shift[0])} {num(shift[1])}) scale({num(scale, 4)})"><g class="a">'
        f'<g transform="translate({num(-centre[0])} {num(-centre[1])})">{chart}</g></g></g>'
    )
    total = sum(count for week in weeks for _, _, count, _ in week)
    label = f"A GitHub contribution chart drawn in 3D: {total} contributions in the last year, each day a green bar as tall as it was busy"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{left} {top} {W} {H}" width="{W}" height="{H}" role="img" aria-label="{label}">'
            f'<title>{label}</title><style>{style}</style><defs>{defs}</defs><g clip-path="url(#card)">{body}</g></svg>\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--user", default=USER, help="whose contributions to draw")
    ap.add_argument("--out", help="write the SVG here instead of assets/")
    ap.add_argument("--at", type=float, help="write a frozen frame from this many seconds in")
    args = ap.parse_args()

    out = pathlib.Path(args.out) if args.out else pathlib.Path(__file__).resolve().parent.parent / "assets"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "contributions.svg"
    path.write_text(render(contributions(args.user), args.at))
    print(f"wrote {path} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
