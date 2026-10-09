"""
plot_valley_map.py
==================

Zoom map of the three AWS stations in Endalen on a topographic
background (hill shading and contour lines, in the style of
toposvalbard.npolar.no).

Background sources, tried in order:
1. Kartverket / Norge WMTS "topo" layer, TileMatrixSet utm33n
   (the service behind toposvalbard) — https://cache.kartverket.no/v1/wmts
2. OpenTopoMap tiles (Web Mercator) — relief + contour lines
3. OpenStreetMap tiles (Web Mercator) — plain fallback

Station positions:
- Rosanne: notebook GPS 2026-10-08 (78.18177 N, 15.75970 E).
- Bobby McGee / Mrs Robinson: estimated from iMET sonde GPS during
  flights F03 / F05 on 2026-10-08 (see locations.csv).

Distances between stations are computed with the haversine formula and
drawn on the map.

Usage:
    python3 plot_valley_map.py

Output:
    04_plots/station_map_endalen.png

Dependencies:
    matplotlib, numpy, PIL (Pillow); internet access for map tiles.
"""

import csv
import io
import math
import os
import urllib.request
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
PLOT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "04_plots"))
OUTPUT_DPI = 200
USER_AGENT = {"User-Agent": "AE-342 field campaign map/1.0 (UNIS course project)"}
TILE_SIZE = 256
MAX_TILES = 120

# area of interest: Endalen around the three stations
LAT_MIN, LAT_MAX = 78.1780, 78.1895
LON_MIN, LON_MAX = 15.7400, 15.7670

STATIONS = [
    ("Bobby McGee", 78.18431, 15.75312),
    ("Mrs Robinson", 78.18655, 15.74720),
    ("Rosanne", 78.18177, 15.75970),
]

IMET_FILES = [
    ("20261008_imet_sn657_endalen_0849utc.csv", "tab:orange"),
    ("20261008_imet_sn611_adventdalen_0807utc.csv", "tab:blue"),
    ("20261008_imet_sn611_adventdalen_1137utc.csv", "tab:green"),
]


# ---------------------------------------------------------------------------
# Coordinate conversions
# ---------------------------------------------------------------------------
# WGS84 / UTM zone 33N (EPSG:25833), central meridian 15 E, k0 = 0.9996
_A = 6378137.0
_F = 1.0 / 298.257223563
_K0 = 0.9996
_LON0 = math.radians(15.0)
_FAKE_E = 500000.0


def to_utm33n(lon, lat):
    """Geodetic (WGS84) to UTM 33N easting/northing in metres."""
    phi, lam = math.radians(lat), math.radians(lon)
    e2 = _F * (2 - _F)
    n = _A / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = e2 / (1 - e2) * math.cos(phi) ** 2
    aa = math.cos(phi) * (lam - _LON0)
    m = _A * ((1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * phi
              - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * phi)
              + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * phi)
              - (35 * e2**3 / 3072) * math.sin(6 * phi))
    east = (_K0 * n * (aa + (1 - t + c) * aa**3 / 6
                       + (5 - 18 * t + t**2 + 72 * c - 58 * e2 / (1 - e2)) * aa**5 / 120)
            + _FAKE_E)
    north = (_K0 * (m + n * math.tan(phi) * (aa**2 / 2
                    + (5 - t + 9 * c + 4 * c**2) * aa**4 / 24
                    + (61 - 58 * t + t**2 + 600 * c - 330 * e2 / (1 - e2)) * aa**6 / 720)))
    return east, north


def mercator_x(lon):
    return math.radians(lon)


def mercator_y(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Tile fetching
# ---------------------------------------------------------------------------
def _fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=USER_AGENT), timeout=15) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def fetch_npi_wmts():
    """NPI 'Basisdata_NP_Basiskart_Svalbard_WMTS_25833' (toposvalbard basemap).

    EPSG:25833 (ETRS89 / UTM 33N), standard 256px tile grid.
    """
    caps_url = ("https://geodata.npolar.no/arcgis/rest/services/Basisdata/"
                "NP_Basiskart_Svalbard_WMTS_25833/MapServer/WMTS/1.0.0/"
                "WMTSCapabilities.xml")
    base_url = ("https://geodata.npolar.no/arcgis/rest/services/Basisdata/"
                "NP_Basiskart_Svalbard_WMTS_25833/MapServer/WMTS/tile/1.0.0/"
                "Basisdata_NP_Basiskart_Svalbard_WMTS_25833/default/default028mm")
    ns = {"wmts": "http://www.opengis.net/wmts/1.0",
          "ows": "http://www.opengis.net/ows/1.1"}
    caps = ET.fromstring(_fetch_bytes(caps_url))
    matrices = {}
    for ms in caps.findall(".//wmts:TileMatrixSet", ns):
        if ms.findtext("ows:Identifier", namespaces=ns) != "default028mm":
            continue
        for tm in ms.findall("wmts:TileMatrix", ns):
            mid = tm.findtext("ows:Identifier", namespaces=ns)
            scale = float(tm.findtext("wmts:ScaleDenominator", namespaces=ns))
            tw = int(tm.findtext("wmts:MatrixWidth", namespaces=ns))
            th = int(tm.findtext("wmts:MatrixHeight", namespaces=ns))
            tl = tm.find("wmts:TopLeftCorner", ns).text.split()
            matrices[mid] = dict(res=scale * 2.8e-4, tw=tw, th=th,
                                 x0=float(tl[0]), y0=float(tl[1]))
    if not matrices:
        raise RuntimeError("default028mm TileMatrixSet not found")
    # pick the matrix closest to ~0.8 m/px (0.28 mm * denominator)
    mid = min(matrices, key=lambda k: abs(matrices[k]["res"] - 0.8))
    m = matrices[mid]
    e0, n0 = to_utm33n(LON_MIN, LAT_MAX)  # top-left of AOI
    e1, n1 = to_utm33n(LON_MAX, LAT_MIN)  # bottom-right of AOI
    tx0 = int((e0 - m["x0"]) // (m["res"] * TILE_SIZE))
    tx1 = int((e1 - m["x0"]) // (m["res"] * TILE_SIZE))
    ty0 = int((m["y0"] - n0) // (m["res"] * TILE_SIZE))
    ty1 = int((m["y0"] - n1) // (m["res"] * TILE_SIZE))
    count = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
    if count > MAX_TILES:
        raise RuntimeError(f"too many tiles at {mid} ({count})")
    canvas = np.zeros(((ty1 - ty0 + 1) * TILE_SIZE, (tx1 - tx0 + 1) * TILE_SIZE, 3), np.uint8)
    n_ok = _download_grid(canvas, base_url, mid, tx0, tx1, ty0, ty1)
    if n_ok == 0:
        raise RuntimeError("no tiles downloaded")
    print(f"NPI WMTS: Basiskart_Svalbard, matrix {mid} ({m['res']:.2f} m/px), tiles {n_ok}/{count}")
    tile_span = m["res"] * TILE_SIZE
    extent = (m["x0"] + tx0 * tile_span,                 # xmin
              m["x0"] + (tx1 + 1) * tile_span,           # xmax
              m["y0"] - (ty1 + 1) * tile_span,           # ymin
              m["y0"] - ty0 * tile_span)                 # ymax
    return canvas, extent, "utm"


def _fetch_bytes(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=USER_AGENT), timeout=15) as r:
        return r.read()


def _download_grid(canvas, base, mid, tx0, tx1, ty0, ty1):
    ok = 0
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            try:
                img = _fetch(f"{base}/{mid}/{ty}/{tx}.png")
                y = (ty - ty0) * TILE_SIZE
                x = (tx - tx0) * TILE_SIZE
                canvas[y:y + TILE_SIZE, x:x + TILE_SIZE] = np.asarray(img)
                ok += 1
            except Exception as exc:
                print(f"  tile {mid}/{ty}/{tx} skipped: {exc}")
    return ok


def fetch_mercator_tiles(zoom, host_fmt):
    """Generic XYZ tiles in Web Mercator; returns (canvas, extent)."""
    n = 2 ** zoom
    xt0 = (LON_MIN + 180) / 360 * n
    xt1 = (LON_MAX + 180) / 360 * n
    y0f = (1 - math.asinh(math.tan(math.radians(LAT_MAX))) / math.pi) / 2 * n
    y1f = (1 - math.asinh(math.tan(math.radians(LAT_MIN))) / math.pi) / 2 * n
    tx0, tx1 = int(xt0), int(xt1)
    ty0, ty1 = int(y0f), int(y1f)
    if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) > MAX_TILES:
        raise RuntimeError(f"too many tiles at zoom {zoom}")
    canvas = np.zeros(((ty1 - ty0 + 1) * TILE_SIZE, (tx1 - tx0 + 1) * TILE_SIZE, 3), np.uint8)
    ok = 0
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            try:
                img = _fetch(host_fmt.format(z=zoom, x=tx, y=ty))
                y = (ty - ty0) * TILE_SIZE
                x = (tx - tx0) * TILE_SIZE
                canvas[y:y + TILE_SIZE, x:x + TILE_SIZE] = np.asarray(img)
                ok += 1
            except Exception as exc:
                print(f"  tile z{zoom}/{tx}/{ty} skipped: {exc}")
    if ok == 0:
        raise RuntimeError("no tiles downloaded")
    # pixel corners of the AOI
    pl, pr = (xt0 - tx0) * TILE_SIZE, (xt1 - tx0) * TILE_SIZE
    pt, pb = (y0f - ty0) * TILE_SIZE, (y1f - ty0) * TILE_SIZE
    img = np.asarray(Image.fromarray(canvas.astype(np.uint8)).crop(
        (int(pl), int(pt), int(pr + 1), int(pb + 1))))
    return (img,
            (mercator_x(LON_MIN), mercator_x(LON_MAX),
             mercator_y(LAT_MIN), mercator_y(LAT_MAX)), "merc")


def fetch_background():
    """Try toposvalbard (NPI), then OpenTopoMap, then plain OSM."""
    try:
        return fetch_npi_wmts() + ("NPI Basiskart Svalbard (toposvalbard, EPSG:25833)",)
    except Exception as exc:
        print(f"NPI WMTS unavailable: {exc}")
    for zoom, host, name in [
        (15, "https://a.tile.opentopomap.org/{z}/{x}/{y}.png", "OpenTopoMap"),
        (15, "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "OpenStreetMap"),
    ]:
        try:
            print(f"Trying {name}...")
            return fetch_mercator_tiles(zoom, host) + (name,)
        except Exception as exc:
            print(f"{name} unavailable: {exc}")
    return None


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def load_imet_track(name):
    lons, lats = [], []
    with open(os.path.join(DATA_DIR, "drone", name)) as f:
        for row in csv.reader(f):
            if len(row) > 9 and row[0] == "XQ":
                lons.append(float(row[7]) / 1e7)
                lats.append(float(row[8]) / 1e7)
    return lons, lats


def main():
    background = fetch_background()
    fig, ax = plt.subplots(figsize=(7, 10))
    proj = "merc"
    background_name = "none"
    if background is not None:
        img, extent, proj, background_name = background
        ax.imshow(img, extent=extent, aspect="auto", interpolation="bilinear", zorder=0)
        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim(extent[2], extent[3])
    if proj == "utm":
        ax.set_aspect(1.0)  # metres on both axes -> undistorted top-down view
    if proj == "utm":
        def tx(lon, lat):
            return to_utm33n(lon, lat)
    else:
        def tx(lon, lat):
            return mercator_x(lon), mercator_y(lat)

    # station-to-station distances (haversine, drawn as dashed lines)
    for (n1, la1, lo1), (n2, la2, lo2) in zip(STATIONS, STATIONS[1:] + STATIONS[:1]):
        d = haversine_m(la1, lo1, la2, lo2)
        (x1, y1), (x2, y2) = tx(lo1, la1), tx(lo2, la2)
        ax.plot([x1, x2], [y1, y2], linestyle="--", color="black",
                linewidth=1.0, alpha=0.6, zorder=3)
        ax.annotate(f"{d:.0f} m", ((x1 + x2) / 2, (y1 + y2) / 2),
                    fontsize=8, ha="center", va="bottom",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none",
                              alpha=0.75), zorder=5)

    for name, color in IMET_FILES:
        lons, lats = load_imet_track(name)
        xs, ys = zip(*[tx(lo, la) for lo, la in zip(lons, lats)])
        ax.plot(xs, ys, color=color, linewidth=1.2, alpha=0.85, zorder=4,
                label=f"iMET track: {name.replace('.csv', '')}")

    offsets = {"Bobby McGee": (8, 5), "Mrs Robinson": (8, 5), "Rosanne": (8, -11)}
    for name, lat, lon in STATIONS:
        x, y = tx(lon, lat)
        ax.scatter([x], [y], marker="D", s=90, color="red", edgecolor="black",
                   linewidth=0.9, zorder=6)
        ax.annotate(name, (x, y), textcoords="offset points",
                    xytext=offsets[name], fontsize=10, fontweight="bold",
                    color="red", zorder=6)

    ax.set_title("AWS stations in Endalen with drone GPS tracks\n"
                 f"(background: {background_name})", fontsize=12)
    ax.set_xlabel("Easting, UTM 33N (m)" if proj == "utm" else "Longitude (deg)")
    ax.set_ylabel("Northing, UTM 33N (m)" if proj == "utm" else "Latitude (deg)")
    if proj == "utm":
        ax.grid(True, linestyle=":", alpha=0.5, zorder=5)
        ax.ticklabel_format(style="plain", useOffset=False)
    else:
        la_ticks = np.arange(78.178, 78.1905, 0.002)
        lo_ticks = np.arange(15.740, 15.7675, 0.005)
        ax.set_yticks([mercator_y(v) for v in la_ticks])
        ax.set_yticklabels([f"{v:.4f}" for v in la_ticks])
        ax.set_xticks([mercator_x(v) for v in lo_ticks])
        ax.set_xticklabels([f"{v:.3f}" for v in lo_ticks])
        ax.grid(True, linestyle=":", alpha=0.5, zorder=5)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)

    out = os.path.join(PLOT_DIR, "station_map_endalen.png")
    fig.tight_layout()
    fig.savefig(out, dpi=OUTPUT_DPI)
    print(f"Saved map: {out}")


if __name__ == "__main__":
    main()
