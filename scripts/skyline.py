#!/usr/bin/env python3
"""Build the contribution skyline: the last year of GitHub contributions as a small city.

Every day is a lot on a 53 by 7 grid, one column per week with Sunday at the
back, the same way round as the chart on the profile. A day with contributions
gets a tower, taller the more there were; busier days step in as they rise, and
the busiest day of the year carries a mast.

    python3 scripts/skyline.py            # rewrites the model inside README.md

The model is an ASCII STL in a fenced `stl` block, which GitHub draws as a 3D
viewer that anyone can drag around. The viewer shows one flat colour, so the
shapes have to do all the work: kerbs mark out the empty lots, and the towers
are told apart only by their outline.

The token comes from GITHUB_TOKEN or GH_TOKEN, or from the gh CLI if neither is set.
"""

import argparse
import json
import math
import os
import pathlib
import re
import subprocess
import urllib.request

USER = "milinddethe15"
LOT = 10  # one day's plot of land; everything else is measured against this
GAP = 1  # the strip left clear on each side of a tower, which makes the streets
STEP = 1  # how far each tier steps in from the one below
FLOOR, RISE = 3, 8  # a tower is FLOOR + RISE * sqrt(contributions) tall, so one huge day can't flatten the rest
TIERS = (4, 10)  # contributions in a day at which a tower gains a second and a third tier
SPLITS = {1: (1,), 2: (0.7, 1), 3: (0.5, 0.82, 1)}  # where each tier stops, as a share of the full height
MAST = 9  # the mast on the busiest day
KERB_WIDTH, KERB_HEIGHT = 1, 0.6
SLAB, APRON = 3, 4  # the ground: how thick, and how far it reaches past the lots

START, END = "<!-- skyline:start -->", "<!-- skyline:end -->"
QUERY = ("query($login:String!){user(login:$login){contributionsCollection{contributionCalendar"
         "{weeks{contributionDays{contributionCount weekday}}}}}}")


def num(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def calendar(user):
    """The year as a list of weeks, each a list of (weekday, contributions) with Sunday as 0."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "skyline"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        reply = json.load(response)
    if reply.get("errors"):
        raise SystemExit(f"GitHub refused the query: {reply['errors'][0]['message']}")
    weeks = reply["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [[(day["weekday"], day["contributionCount"]) for day in week["contributionDays"]] for week in weeks]


def box(x0, y0, x1, y1, z0, z1, bottom=False):
    """The faces of a box as (normal, three corners), wound anticlockwise seen from outside.

    The underside is left off unless asked for: everything here stands on something.
    """
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [((0, 0, 1), (4, 5, 6, 7)), ((0, -1, 0), (0, 1, 5, 4)), ((1, 0, 0), (1, 2, 6, 5)),
             ((0, 1, 0), (2, 3, 7, 6)), ((-1, 0, 0), (3, 0, 4, 7))]
    if bottom:
        faces.append(((0, 0, -1), (3, 2, 1, 0)))
    for normal, (p, q, r, s) in faces:
        yield normal, (c[p], c[q], c[r])
        yield normal, (c[p], c[r], c[s])


def tower(x, y, count, mast):
    """One day's building on the lot whose near left corner is (x, y)."""
    height = FLOOR + RISE * math.sqrt(count)
    tiers = 1 + sum(count >= t for t in TIERS)
    bottom = 0
    for k, split in enumerate(SPLITS[tiers]):
        inset = GAP + k * STEP
        top = round(height * split, 1)
        yield from box(x + inset, y + inset, x + LOT - inset, y + LOT - inset, bottom, top)
        bottom = top
    if mast:
        yield from box(x + LOT / 2 - 0.5, y + LOT / 2 - 0.5, x + LOT / 2 + 0.5, y + LOT / 2 + 0.5, bottom, bottom + MAST)


def render(weeks):
    """The whole city as ASCII STL, standing on z = 0 with the weeks running along x."""
    width, depth = len(weeks) * LOT, 7 * LOT
    peak = max(count for week in weeks for _, count in week)
    half = KERB_WIDTH / 2

    mesh = list(box(-APRON, -APRON, width + APRON, depth + APRON, -SLAB, 0, bottom=True))
    for k in range(len(weeks) + 1):
        mesh += box(k * LOT - half, -half, k * LOT + half, depth + half, 0, KERB_HEIGHT)
    for k in range(8):
        mesh += box(-half, k * LOT - half, width + half, k * LOT + half, 0, KERB_HEIGHT)
    crowned = False
    for column, week in enumerate(weeks):
        for weekday, count in week:
            if count:
                mesh += tower(column * LOT, (6 - weekday) * LOT, count, count == peak and not crowned)
                crowned = crowned or count == peak

    point = lambda p: " ".join(num(v) for v in p)
    facets = "".join(f"facet normal {point(normal)}\nouter loop\n" + "".join(f"vertex {point(p)}\n" for p in corners) + "endloop\nendfacet\n"
                     for normal, corners in mesh)
    return f"solid skyline\n{facets}endsolid skyline\n", len(mesh)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--user", default=USER, help="whose contributions to build")
    ap.add_argument("--stl", help="write a standalone .stl file here and leave the README alone")
    args = ap.parse_args()

    model, triangles = render(calendar(args.user))
    if args.stl:
        path = pathlib.Path(args.stl)
        path.write_text(model)
    else:
        path = pathlib.Path(__file__).resolve().parent.parent / "README.md"
        readme = path.read_text()
        block = f"{START}\n```stl\n{model}```\n{END}"
        updated, found = re.subn(f"{re.escape(START)}.*?{re.escape(END)}", lambda _: block, readme, flags=re.S)
        if not found:
            raise SystemExit(f"{path} has no {START} ... {END} pair to put the model between")
        path.write_text(updated)
    print(f"wrote {path} ({triangles} triangles, {len(model) // 1024} KB)")


if __name__ == "__main__":
    main()
