#!/usr/bin/env python3
"""
normalize_icons.py  -  Normalize aircraft SVG icon sizes and stroke widths.

Adjusts the viewBox of every aircraft SVG so each icon occupies a share of
the canvas proportional to the aircraft's real-world size (1 mm = 1 m in the
drawings).  Stroke widths are then scaled to a constant fraction (per-mille)
of the viewBox size so every icon has the same rendered line thickness.

The script is safe to re-run at any time; running it twice with the same
settings produces no further changes.

Requirements:  Python 3.6+  (no third-party packages needed)

Usage:
    python normalize_icons.py [options]

Options:
    --min-size-percent N      Smallest aircraft fills N % of canvas
                              (default: 42.5)
    --max-size-percent N      Largest aircraft fills N % of canvas
                              (default: 95)
    --stroke-width-percent N  Stroke width relative to the 4.15 per-mille
                              baseline; 100 = standard, 120 = 20 % thicker
                              (default: 100)
    --dry-run                 Print the calculated values without writing files
    --help / -h               Show this message and exit

Examples:
    python normalize_icons.py
    python normalize_icons.py --max-size-percent 90
    python normalize_icons.py --stroke-width-percent 120
    python normalize_icons.py --min-size-percent 35 --max-size-percent 95 --dry-run
"""

import math
import os
import re
import sys
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

SVG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Shapes SVG")

# Aircraft excluded from normalization (non-standard canvas size)
EXCLUDE = {"CVN-65.svg"}

# 4.15 per-mille: the established stroke-width baseline
# stroke-width [px] = viewBox_size * STROKE_BASELINE * (stroke_width_percent / 100)
STROKE_BASELINE = 0.00415

SVG_NS = "http://www.w3.org/2000/svg"
INK_NS = "http://www.inkscape.org/namespaces/inkscape"


# ---------------------------------------------------------------------------
# SVG path bounding-box calculator
# Handles M L H V C S Q T A Z (absolute and relative), including Bezier extrema
# ---------------------------------------------------------------------------

def _tokenize(d):
    return re.findall(
        r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?",
        d,
    )


def _cubic_extrema(p0, p1, p2, p3):
    """Points at the extrema of a cubic Bezier (needed for exact bbox)."""
    pts = [p0, p3]
    for axis in range(2):
        a = 3 * (-p0[axis] + 3*p1[axis] - 3*p2[axis] + p3[axis])
        b = 6 * ( p0[axis] - 2*p1[axis] +   p2[axis])
        c = 3 * ( p1[axis] -   p0[axis])
        disc = b*b - 4*a*c
        if abs(a) > 1e-9:
            if disc >= 0:
                sq = math.sqrt(disc)
                for t in [(-b + sq) / (2*a), (-b - sq) / (2*a)]:
                    if 0 < t < 1:
                        u = 1 - t
                        x = u**3*p0[0]+3*u**2*t*p1[0]+3*u*t**2*p2[0]+t**3*p3[0]
                        y = u**3*p0[1]+3*u**2*t*p1[1]+3*u*t**2*p2[1]+t**3*p3[1]
                        pts.append((x, y))
        elif abs(b) > 1e-9:
            t = -c / b
            if 0 < t < 1:
                u = 1 - t
                x = u**3*p0[0]+3*u**2*t*p1[0]+3*u*t**2*p2[0]+t**3*p3[0]
                y = u**3*p0[1]+3*u**2*t*p1[1]+3*u*t**2*p2[1]+t**3*p3[1]
                pts.append((x, y))
    return pts


def _path_bbox(d):
    """Return (xmin, ymin, xmax, ymax) for an SVG path d-attribute string."""
    tokens = _tokenize(d)
    if not tokens:
        return None

    pts = []
    cur = [0.0, 0.0]
    start = [0.0, 0.0]
    last_cp = None
    cmd = "M"
    idx = 0

    def nf():
        nonlocal idx
        v = float(tokens[idx]); idx += 1; return v

    while idx < len(tokens):
        tok = tokens[idx]
        if tok.isalpha():
            cmd = tok; idx += 1; continue

        if cmd in ("M", "m"):
            x, y = nf(), nf()
            cur = [x, y] if cmd == "M" else [cur[0]+x, cur[1]+y]
            start = cur[:]; pts.append(tuple(cur))
            cmd = "L" if cmd == "M" else "l"; last_cp = None

        elif cmd in ("L", "l"):
            x, y = nf(), nf()
            cur = [x, y] if cmd == "L" else [cur[0]+x, cur[1]+y]
            pts.append(tuple(cur)); last_cp = None

        elif cmd in ("H", "h"):
            x = nf()
            cur[0] = x if cmd == "H" else cur[0]+x
            pts.append(tuple(cur)); last_cp = None

        elif cmd in ("V", "v"):
            y = nf()
            cur[1] = y if cmd == "V" else cur[1]+y
            pts.append(tuple(cur)); last_cp = None

        elif cmd in ("C", "c"):
            x1,y1,x2,y2,x,y = nf(),nf(),nf(),nf(),nf(),nf()
            if cmd == "C":
                p1,p2,p3 = (x1,y1),(x2,y2),(x,y)
            else:
                p1=(cur[0]+x1,cur[1]+y1); p2=(cur[0]+x2,cur[1]+y2)
                p3=(cur[0]+x, cur[1]+y)
            pts.extend(_cubic_extrema(tuple(cur), p1, p2, p3))
            last_cp = p2; cur = list(p3)

        elif cmd in ("S", "s"):
            x2,y2,x,y = nf(),nf(),nf(),nf()
            p1 = (2*cur[0]-last_cp[0], 2*cur[1]-last_cp[1]) if last_cp else tuple(cur)
            if cmd == "S": p2,p3 = (x2,y2),(x,y)
            else:          p2=(cur[0]+x2,cur[1]+y2); p3=(cur[0]+x,cur[1]+y)
            pts.extend(_cubic_extrema(tuple(cur), p1, p2, p3))
            last_cp = p2; cur = list(p3)

        elif cmd in ("Q", "q"):
            x1,y1,x,y = nf(),nf(),nf(),nf()
            if cmd == "Q": p1,p2 = (x1,y1),(x,y)
            else:          p1=(cur[0]+x1,cur[1]+y1); p2=(cur[0]+x,cur[1]+y)
            pts.extend([p1, p2]); last_cp = p1; cur = list(p2)

        elif cmd in ("T", "t"):
            x,y = nf(),nf()
            p1 = (2*cur[0]-last_cp[0], 2*cur[1]-last_cp[1]) if last_cp else tuple(cur)
            p2 = (x,y) if cmd == "T" else (cur[0]+x, cur[1]+y)
            pts.extend([p1, p2]); last_cp = p1; cur = list(p2)

        elif cmd in ("A", "a"):
            _rx,_ry,_r,_la,_sw,x,y = nf(),nf(),nf(),nf(),nf(),nf(),nf()
            cur = [x,y] if cmd == "A" else [cur[0]+x, cur[1]+y]
            pts.append(tuple(cur)); last_cp = None

        elif cmd in ("Z", "z"):
            cur = start[:]; last_cp = None; continue

        else:
            idx += 1; continue

    if not pts:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _aircraft_bbox(svg_path):
    """Return bounding box of the 'Pfade' (outline) layer in an SVG file."""
    root = ET.parse(svg_path).getroot()
    combined = None

    def merge(b):
        nonlocal combined
        if b is None: return
        if combined is None: combined = list(b)
        else:
            combined[0] = min(combined[0], b[0]); combined[1] = min(combined[1], b[1])
            combined[2] = max(combined[2], b[2]); combined[3] = max(combined[3], b[3])

    pfade_found = False
    for g in root.iter(f"{{{SVG_NS}}}g"):
        if g.get(f"{{{INK_NS}}}label", "") == "Pfade":
            pfade_found = True
            for path in g.iter(f"{{{SVG_NS}}}path"):
                merge(_path_bbox(path.get("d", "")))
            break
    if not pfade_found:
        for path in root.iter(f"{{{SVG_NS}}}path"):
            merge(_path_bbox(path.get("d", "")))

    return tuple(combined) if combined else None


# ---------------------------------------------------------------------------
# Main normalization routine
# ---------------------------------------------------------------------------

def normalize(fill_min, fill_max, stroke_permille, dry_run=False):
    svg_files = sorted(
        f for f in os.listdir(SVG_DIR)
        if f.endswith(".svg") and f not in EXCLUDE
    )

    label = "DRY RUN - no files written" if dry_run else "LIVE"
    print(f"normalize_icons.py  [{label}]")
    print(f"  min-size    : {fill_min*100:.1f} %")
    print(f"  max-size    : {fill_max*100:.1f} %")
    print(f"  stroke-width: {stroke_permille*1000:.4f} per-mille  "
          f"({stroke_permille/STROKE_BASELINE*100:.1f} % of baseline)")
    print(f"  SVG folder  : {SVG_DIR}")
    print(f"  Aircraft    : {len(svg_files)}  (+ {len(EXCLUDE)} excluded)\n")

    # --- Phase 1: collect bounding boxes ---
    bboxes = {}
    for fname in svg_files:
        try:
            bb = _aircraft_bbox(os.path.join(SVG_DIR, fname))
            if bb:
                bboxes[fname] = bb
            else:
                print(f"  WARN  {fname}: no paths found", file=sys.stderr)
        except Exception as exc:
            print(f"  ERROR {fname}: {exc}", file=sys.stderr)

    if not bboxes:
        print("No bounding boxes found - aborting.", file=sys.stderr)
        sys.exit(1)

    sizes = {f: max(bb[2]-bb[0], bb[3]-bb[1]) for f, bb in bboxes.items()}
    s_min = min(sizes.values())
    s_max = max(sizes.values())
    print(f"Bounding-box size range:")
    print(f"  Smallest : {min(sizes, key=sizes.get):<30} {s_min:.2f} mm")
    print(f"  Largest  : {max(sizes, key=sizes.get):<30} {s_max:.2f} mm\n")

    # --- Phase 2: compute new viewBox + stroke, apply ---
    print(f"{'Aircraft file':<32} {'size':>6}  {'fill':>6}  {'viewBox size':>12}  {'stroke-width':>12}")
    print("-" * 76)

    updated_vb = updated_sw = 0

    for fname in sorted(bboxes, key=lambda f: sizes[f], reverse=True):
        bb  = bboxes[fname]
        cx  = (bb[0] + bb[2]) / 2
        cy  = (bb[1] + bb[3]) / 2
        s   = sizes[fname]

        t    = (s - s_min) / (s_max - s_min) if s_max > s_min else 1.0
        fill = fill_min + t * (fill_max - fill_min)

        vb_sz  = s / fill
        vb_x   = cx - vb_sz / 2
        vb_y   = cy - vb_sz / 2
        vb_str = f"{vb_x:.4f} {vb_y:.4f} {vb_sz:.4f} {vb_sz:.4f}"

        target_sw = vb_sz * stroke_permille

        print(f"{fname:<32} {s:>6.1f}  {fill:>5.1%}  {vb_sz:>12.4f}  {target_sw:>12.6f} px")

        if dry_run:
            continue

        path = os.path.join(SVG_DIR, fname)
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()

        # Update viewBox
        new_content = re.sub(r'viewBox="[^"]*"', f'viewBox="{vb_str}"', content, count=1)
        if new_content != content:
            updated_vb += 1
            content = new_content

        # Update stroke-widths: find anchor (closest value to target), scale all proportionally
        sw_pat = r"(stroke-width\s*[=:]\s*)([0-9.eE+-]+)(\s*px)?"
        raw_sw = sorted({float(m[1]) for m in re.findall(sw_pat, content)})
        if raw_sw:
            anchor = min(raw_sw, key=lambda v: abs(v - target_sw))
            scale  = target_sw / anchor
            if abs(scale - 1.0) > 1e-6:
                def _repl(m, _scale=scale):
                    v = float(m.group(2)) * _scale
                    u = m.group(3) if m.group(3) else ""
                    return f"{m.group(1)}{v:.6f}{u}"
                new_content = re.sub(sw_pat, _repl, content)
                if new_content != content:
                    updated_sw += 1
                    content = new_content

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)

    if not dry_run:
        print(f"\nDone.  viewBox updated: {updated_vb}   stroke-width updated: {updated_sw}")


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def _parse_args():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__); sys.exit(0)

    def get_float(flag, default):
        if flag in args:
            i = args.index(flag)
            try:
                return float(args[i + 1])
            except (IndexError, ValueError):
                print(f"Error: {flag} requires a numeric value.", file=sys.stderr)
                sys.exit(1)
        return default

    return dict(
        fill_min        = get_float("--min-size-percent",    42.5) / 100.0,
        fill_max        = get_float("--max-size-percent",    95.0) / 100.0,
        stroke_permille = get_float("--stroke-width-percent", 100.0) / 100.0 * STROKE_BASELINE,
        dry_run         = "--dry-run" in args,
    )


if __name__ == "__main__":
    normalize(**_parse_args())
