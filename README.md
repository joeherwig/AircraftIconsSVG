# AircraftShapesSVG

Aircraft shapes (Top View) for ADSB-Viewers in SVG-Format

amnesica and me created an own ADSB application [BelugaProject](https://github.com/amnesica/BelugaProject). In our app we use a lot of the concepts of [tar1090](https://github.com/wiedehopf/tar1090/tree/master/html) by wiedehopf and [dump1090](https://github.com/flightaware/dump1090) by flightaware. Maybe there are far more contributors. Ein ganz großes Dankeschön ( a lot of thanks) to all of you.

Time to give something back. We created new aircraft shapes or redesigned some existing ones and would like to share them here. After download/cloning repository open [svgCatalog.html](svgCatalog.html) file and resize browser window to change size of shapes and get a description. 

Besides you find a [Tutorial](./Tutorial/) for "Creating aircraft shapes in svg format". It describes our workflow and hopefully may help to increase the amount of aircraft shapes for tar1090, dump1090 (and BelugaProject).

## Icon Size Normalization

The script **`normalize_icons.py`** (project root, requires Python 3.6+) adjusts the `viewBox` of every SVG so that aircraft icons are sized proportionally to real-world dimensions, and scales stroke widths to stay visually consistent across all icons.

```
python normalize_icons.py [options]
```

| Option | Default | Description |
|---|---|---|
| `--min-size-percent N` | 42.5 | Smallest aircraft fills N % of its canvas |
| `--max-size-percent N` | 95 | Largest aircraft fills N % of its canvas |
| `--stroke-width-percent N` | 100 | Stroke width relative to the 4.15 ‰ baseline |
| `--dry-run` | — | Preview results without writing files |

**Examples**

```
# Apply standard settings
python normalize_icons.py

# Preview without changes
python normalize_icons.py --dry-run

# Reduce maximum size to 90 % with 20 % thicker strokes
python normalize_icons.py --max-size-percent 90 --stroke-width-percent 120
```

Re-run normalization after adding any new SVG to the collection. See the [Tutorial](./Tutorial/) for the full technical description of the normalization rules.

![Catalogue](Catalogue.png)
