#!/usr/bin/env python3
"""Build the contribution chart as a 3D model that anyone can drag around in the README.

It is the chart scripts/contributions.py draws, laid out the same way: one column
per week with Sunday at the back, a bar for every day with contributions, the
month names along the front and Mon, Wed and Fri down the left.

    python3 scripts/skyline.py            # rewrites the model inside README.md

The model is an ASCII STL in a fenced `stl` block, which GitHub shows in a viewer
of its own. That viewer has one flat colour with barely any shading, and lays a
pale grid under the model, so the greens are gone and outlines do all the work:
an empty day is a flat square just above the grid, and the names are flat strokes
of the same kind, a few straight lines to a letter.
"""

import argparse
import calendar
import math
import pathlib
import re

import contributions as chart

FLOAT = 0.4  # how far the flat parts sit above the viewer's grid, so the two don't flicker
LETTER = 5.2  # how tall the names are, against a day's square of 10
STROKE = 0.14  # how thick a letter's lines are, as a share of its height
START, END = "<!-- skyline:start -->", "<!-- skyline:end -->"

# Capital letters as strokes on a grid 4 wide and 6 tall, each stroke a run of straight lines.
STROKES = {
    "A": [[(0, 0), (0, 4), (2, 6), (4, 4), (4, 0)], [(0, 2.4), (4, 2.4)]],
    "B": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(3, 3), (4, 2), (4, 1), (3, 0), (0, 0)]],
    "C": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1)]],
    "D": [[(0, 0), (0, 6), (2.5, 6), (4, 4.5), (4, 1.5), (2.5, 0), (0, 0)]],
    "E": [[(4, 6), (0, 6), (0, 0), (4, 0)], [(0, 3), (3, 3)]],
    "F": [[(4, 6), (0, 6), (0, 0)], [(0, 3), (3, 3)]],
    "G": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (2.2, 3)]],
    "I": [[(1, 0), (3, 0)], [(2, 0), (2, 6)], [(1, 6), (3, 6)]],
    "J": [[(0, 1.2), (1, 0), (3, 0), (4, 1), (4, 6)]],
    "L": [[(0, 6), (0, 0), (4, 0)]],
    "M": [[(0, 0), (0, 6), (2, 3), (4, 6), (4, 0)]],
    "N": [[(0, 0), (0, 6), (4, 0), (4, 6)]],
    "O": [[(1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)]],
    "P": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)]],
    "R": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(2, 3), (4, 0)]],
    "S": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3), (3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "T": [[(0, 6), (4, 6)], [(2, 6), (2, 0)]],
    "U": [[(0, 6), (0, 1), (1, 0), (3, 0), (4, 1), (4, 6)]],
    "V": [[(0, 6), (2, 0), (4, 6)]],
    "W": [[(0, 6), (1, 0), (2, 4), (3, 0), (4, 6)]],
    "Y": [[(0, 6), (2, 3), (4, 6)], [(2, 3), (2, 0)]],
}
ADVANCE = 5.5  # from the start of one letter to the start of the next, on the same grid


def num(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def box(x0, y0, x1, y1, z0, z1):
    """All six faces of a box as (normal, three corners), wound anticlockwise seen from outside."""
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [((0, 0, 1), (4, 5, 6, 7)), ((0, -1, 0), (0, 1, 5, 4)), ((1, 0, 0), (1, 2, 6, 5)),
             ((0, 1, 0), (2, 3, 7, 6)), ((-1, 0, 0), (3, 0, 4, 7)), ((0, 0, -1), (3, 2, 1, 0))]
    for normal, (p, q, r, s) in faces:
        yield normal, (c[p], c[q], c[r])
        yield normal, (c[p], c[r], c[s])


def patch(corners):
    """A flat four-cornered piece facing up, floating just above the grid. The corners go round anticlockwise seen from above."""
    p, q, r, s = ((x, y, FLOAT) for x, y in corners)
    yield (0, 0, 1), (p, q, r)
    yield (0, 0, 1), (p, r, s)


def lettering(word, x, y, right=False):
    """A word as flat strokes, its baseline starting at (x, y), or ending there if `right`."""
    size, half = LETTER / 6, LETTER * STROKE / 2
    if right:
        x -= ((len(word) - 1) * ADVANCE + 4) * size
    for place, letter in enumerate(word.upper()):
        for stroke in STROKES[letter]:
            points = [(x + (place * ADVANCE + px) * size, y + py * size) for px, py in stroke]
            for (ax, ay), (bx, by) in zip(points, points[1:]):
                length = math.hypot(bx - ax, by - ay)
                dx, dy = (bx - ax) / length * half, (by - ay) / length * half  # half a stroke's width along the line; (-dy, dx) is the same across it
                yield from patch([(ax - dx + dy, ay - dy - dx), (bx + dx + dy, by + dy - dx), (bx + dx - dy, by + dy + dx), (ax - dx - dy, ay - dy + dx)])


def render(weeks):
    """The whole chart as ASCII STL, standing on z = 0 with the weeks running along x and Sunday at the back."""
    cell, gap = chart.CELL, chart.GAP
    peak = max(count for week in weeks for _, _, count, _ in week) or 1
    mesh = []
    for column, week in enumerate(weeks):
        for _, weekday, count, _ in week:
            x0, y0 = column * cell + gap, (6 - weekday) * cell + gap
            x1, y1 = x0 + cell - 2 * gap, y0 + cell - 2 * gap
            mesh += box(x0, y0, x1, y1, 0, chart.height(count, peak)) if count else patch([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    for column, name in chart.months(weeks):
        mesh += lettering(name, column * cell + gap, -3 - LETTER)
    for weekday in (1, 3, 5):
        mesh += lettering(calendar.day_abbr[weekday - 1], -3, (6 - weekday + 0.5) * cell - LETTER / 2, right=True)

    point = lambda p: " ".join(num(v) for v in p)
    facets = "".join(f"facet normal {point(normal)}\nouter loop\n" + "".join(f"vertex {point(p)}\n" for p in corners) + "endloop\nendfacet\n"
                     for normal, corners in mesh)
    return f"solid contributions\n{facets}endsolid contributions\n", len(mesh)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--user", default=chart.USER, help="whose contributions to build")
    ap.add_argument("--stl", help="write a standalone .stl file here and leave the README alone")
    args = ap.parse_args()

    model, triangles = render(chart.contributions(args.user))
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
