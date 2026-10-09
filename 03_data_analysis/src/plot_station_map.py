"""
plot_station_map.py
===================

Plot the AWS stations and drone measurement points around
Longyearbyen (Endalen / Adventdalen) on an OpenStreetMap background.

Station positions:
- Rosanne: notebook (2026-10-08), 78.18177 N, 15.75970 E.
- Bobby McGee and Mrs Robinson: estimated from the iMET sonde GPS
  recorded during drone flights F03 (Bobby McGee, 09:23-09:27 UTC) and
  F05 (Mrs Robinson, 10:04-10:08 UTC) on 2026-10-08.
- Old Aurora station (Adventdalen): notebook, 78.20133 N, 15.82968 E.

iMET GPS tracks are overlaid as context for where the drone profiles
were flown.

Usage:
    python3 plot_station_map.py

Output:
    04_plots/station_map.png

Dependencies:
    matplotlib, numpy, PIL (Pillow); OpenStreetMap tiles are fetched
    over the network when available (falls back to a plain map).
"""

import csv
import datetime as dt
import io
import math
import os
import urllib.request

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
PLOT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "04_plots"))
OUTPUT_DPI = 200

ZOOM = 13
TILE_SIZE = 256
# area of interest: Endalen + Adventdalen around Longyearbyen
LAT_MIN, LAT_MAX = 78.170, 78.212
LON_MIN, LON_MAX = 15.725, 15.855

STATIONS = [
    # name, lat, lon, source
    ("Bobby McGee (AWS)", 78.18431, 15.75312, "estimated from iMET GPS (flight F03)"),
    ("Mrs Robinson (AWS)", 78.18655, 15.74720, "estimated from iMET GPS (flight F05)"),
    ("Rosanne (AWS)", 78.18177, 15.75970, "notebook GPS 2026-10-08"),
    ("Old Aurora station (Adventdalen)", 78.20133, 15.82968, "notebook GPS 2026-10-08"),
]

WAYPOINTS = [
    ("F02 midpoint", 78.18304, 15.75617),
    ("F04 midpoint", 78.18537, 15.74907),
    ("Notebook flight #8", 78.18550, 15.74992),
]

IMET_FILES = [
    ("20261008_imet_sn657_endalen_0849utc.csv", "tab:orange"),
    ("20261008_imet_sn611_adventdalen_0807utc.csv", "tab:blue"),
    ("20261008_imet_sn611_adventdalen_1137utc.csv", "tab:green"),
    ("20261007_imet_sn657_adventdalen_1002utc.csv", "tab:red"),
]


def mercator_x(lon):
    return math.radians(lon)


def mercator_y(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def deg2num(lat, lon, zoom):
    n = 2 ** zoom
    xt = (lon + 180.0) / 360.0 * n
    yt = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return xt, yt


def fetch_tiles(zoom):
    """Download and stitch the OSM tiles covering the area of interest."""
    x0f, y1f = deg2num(LAT_MIN, LON_MIN, zoom)
    x1f, y0f = deg2num(LAT_MAX, LON_MAX, zoom)
    x0, x1 = int(x0f), int(x1f)
    y0, y1 = int(y0f), int(y1f)
    nx, ny = x1 - x0 + 1, y1 - y0 + 1
    canvas = np.zeros((ny * TILE_SIZE, nx * TILE_SIZE, 3), dtype=np.uint8)
    req_headers = {"User-Agent": "AE-342 field campaign map/1.0 (UNIS course project)"}
    fetched = 0
    for xi in range(x0, x1 + 1):
        for yi in range(y0, y1 + 1):
            url = f"https://tile.openstreetmap.org/{zoom}/{xi}/{yi}.png"
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(url, headers=req_headers), timeout=10
                ) as resp:
                    img = Image.open(io.BytesIO(resp.read())).convert("RGB")
                canvas[
                    (yi - y0) * TILE_SIZE:(yi - y0 + 1) * TILE_SIZE,
                    (xi - x0) * TILE_SIZE:(xi - x0 + 1) * TILE_SIZE,
                ] = np.asarray(img)
                fetched += 1
            except Exception as exc:
                print(f"  tile {zoom}/{xi}/{yi} skipped: {exc}")
    if fetched == 0:
        return None
    # pixel extents of the area of interest inside the canvas
    px_left = int(round((x0f - x0) * TILE_SIZE))
    px_right = int(round((x1f - x0) * TILE_SIZE))
    px_top = int(round((y0f - y0) * TILE_SIZE))
    px_bottom = int(round((y1f - y0) * TILE_SIZE))
    extent = (
        mercator_x(LON_MIN), mercator_x(LON_MAX),
        mercator_y(LAT_MIN), mercator_y(LAT_MAX),
    )
    return canvas[px_top:px_bottom, px_left:px_right], extent


def load_imet_track(path):
    lons, lats = [], []
    with open(os.path.join(DATA_DIR, "drone", path)) as f:
        for row in csv.reader(f):
            if len(row) > 9 and row[0] == "XQ":
                lons.append(float(row[7]) / 1e7)
                lats.append(float(row[8]) / 1e7)
    return lons, lats


def main():
    fig, ax = plt.subplots(figsize=(9, 11))

    background = fetch_tiles(ZOOM)
    if background is not None:
        img, extent = background
        ax.imshow(img, extent=extent, aspect="auto", interpolation="bilinear", zorder=0)
    else:
        print("No tile background available, plotting plain map.")
    ax.set_xlim(mercator_x(LON_MIN), mercator_x(LON_MAX))
    ax.set_ylim(mercator_y(LAT_MIN), mercator_y(LAT_MAX))
    ax.set_aspect(1.0)  # Web Mercator keeps shapes recognizable at this scale

    for path, color in IMET_FILES:
        lons, lats = load_imet_track(path)
        if lons:
            ax.plot(
                [mercator_x(x) for x in lons], [mercator_y(y) for y in lats],
                color=color, linewidth=1.0, alpha=0.8, zorder=2,
            )

    for name, lat, lon, _source in STATIONS:
        x, y = mercator_x(lon), mercator_y(lat)
        ax.scatter([x], [y], marker="D", s=70, color="red", edgecolor="black",
                   linewidth=0.8, zorder=4)
        ax.annotate(name, (x, y), textcoords="offset points", xytext=(7, 5),
                    fontsize=9, fontweight="bold", color="red", zorder=5)

    for name, lat, lon in WAYPOINTS:
        x, y = mercator_x(lon), mercator_y(lat)
        ax.scatter([x], [y], marker="x", s=45, color="black", zorder=4)
        ax.annotate(name, (x, y), textcoords="offset points", xytext=(6, -9),
                    fontsize=8, color="black", zorder=5)

    handles = [Line2D([], [], marker="D", linestyle="", markersize=8, color="red",
                      markeredgecolor="black", label="AWS station")]
    handles.append(Line2D([], [], marker="x", linestyle="", markersize=7,
                          color="black", label="drone waypoint (mid / notebook)"))
    for path, color in IMET_FILES:
        handles.append(Line2D([], [], color=color, linewidth=1.2,
                              label=f"iMET track: {path.replace('.csv', '')}"))
    ax.legend(handles=handles, loc="lower right", fontsize=7.5, framealpha=0.9)

    ax.set_title("AWS stations and drone operations - Endalen / Adventdalen\n"
                 "(background: OpenStreetMap)", fontsize=11)
    ax.set_xlabel("Longitude (deg)")
    ax.set_ylabel("Latitude (deg)")

    # Web Mercator y-axis is non-linear: relabel ticks with real latitudes
    lat_ticks = np.arange(78.17, 78.215, 0.01)
    ax.set_yticks([mercator_y(v) for v in lat_ticks])
    ax.set_yticklabels([f"{v:.3f}" for v in lat_ticks])
    lon_ticks = np.arange(15.72, 15.86, 0.03)
    ax.set_xticks([mercator_x(v) for v in lon_ticks])
    ax.set_xticklabels([f"{v:.2f}" for v in lon_ticks])
    ax.grid(True, linestyle=":", alpha=0.5, zorder=3)

    out = os.path.join(PLOT_DIR, "station_map.png")
    fig.tight_layout()
    fig.savefig(out, dpi=OUTPUT_DPI)
    print(f"Saved map: {out}")


if __name__ == "__main__":
    main()
