"""
analyze_drone_data.py
=====================

Analyze the drone flight data (DJI Mavic Pro 2 telemetry and iMET sonde
soundings) and produce per-flight plots plus cross-flight comparisons.

All plots are saved in the dedicated folder 04_plots/drone/.

Data sources (03_data_analysis/data/drone/):
    - DJI telemetry CSVs:
        columns "Flight time, Altitude, Home Distance, Wind Direction,
        Wind Speed" (1 s resolution, altitude relative to takeoff)
    - iMET sonde CSVs (raw "XQ" records, 1 s resolution):
        pressure, temperature, humidity and humidity temp are scaled by
        1/100, lon/lat by 1e-7, GPS altitude by 1/1000 (scaling of the
        altitude field is approximate, see README).
        Vertical profiles use PRESSURE-based altitude anchored at each
        flight segment (repo convention: altitude is pressure based).

Flight metadata (flight id, UTC windows, site) is read from
03_data_analysis/data/flights.csv; iMET records are split into flights
by the flight UTC windows.

Usage:
    python3 analyze_drone_data.py [file1.csv file2.csv ...]

If no file is given, all drone CSVs in the data/drone folder are processed.

Dependencies:
    numpy, matplotlib
"""

import argparse
import csv
import datetime as dt
import os
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
DRONE_DIR = os.path.join(DATA_DIR, "drone")
FLIGHTS_CSV = os.path.join(DATA_DIR, "flights.csv")
PLOT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "04_plots", "drone"))
OUTPUT_DPI = 150

# standard atmosphere constants for pressure-based altitude
T0_STD = 288.15     # K
LAPSE = 0.0065      # K/m
EXP = LAPSE * 287.05 / 9.80665  # ~0.190263


# ---------------------------------------------------------------------------
# Flight metadata
# ---------------------------------------------------------------------------
def load_flights():
    """Read flights.csv into a list of dicts with parsed date/times."""
    flights = []
    with open(FLIGHTS_CSV, newline="") as fh:
        for row in csv.DictReader(fh):
            if not row.get("date") or row["date"] == "tbd":
                continue
            try:
                start = dt.datetime.strptime(row["date"] + " " + row["start_utc"],
                                             "%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                continue
            end = None
            if row.get("end_utc"):
                try:
                    end = dt.datetime.strptime(row["date"] + " " + row["end_utc"],
                                               "%Y-%m-%d %H:%M")
                except ValueError:
                    pass
            flights.append({
                "flight_id": row["flight_id"] or "",
                "start": start, "end": end,
                "site": row["site"], "location_id": row["location_id"],
                "instrument_id": row["instrument_id"] or "",
                "data_file": row["data_file"],
                "notes": row["notes"] or "",
            })
    return flights


# ---------------------------------------------------------------------------
# iMET sonde parsing
# ---------------------------------------------------------------------------
def parse_imet(path):
    """Parse an iMET XQ record file into (timestamps, columns dict)."""
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}

    times = []
    cols = {k: [] for k in ("pressure", "air_temperature", "rel_humidity",
                            "humidity_temp", "lon", "lat", "gps_alt")}
    for row in rows[1:]:
        if len(row) < len(header) or row[idx.get("ID", 0)] != "XQ":
            continue
        try:
            ts = dt.datetime.strptime(row[idx["Date"]] + " " + row[idx["Time"]],
                                      "%Y/%m/%d %H:%M:%S")
        except (ValueError, KeyError):
            continue
        try:
            cols["pressure"].append(int(row[idx["XQ-iMet-XQ Pressure"]]) / 100.0)
            cols["air_temperature"].append(
                int(row[idx["XQ-iMet-XQ Air Temperature"]]) / 100.0)
            cols["rel_humidity"].append(
                int(row[idx["XQ-iMet-XQ Humidity"]]) / 10.0)
            cols["humidity_temp"].append(
                int(row[idx["XQ-iMet-XQ Humidity Temp"]]) / 100.0)
            cols["lon"].append(int(row[idx["XQ-iMet-XQ Longitude"]]) / 1e7)
            cols["lat"].append(int(row[idx["XQ-iMet-XQ Latitude"]]) / 1e7)
            cols["gps_alt"].append(int(row[idx["XQ-iMet-XQ Altitude"]]) / 1000.0)
        except (ValueError, KeyError, IndexError):
            continue
        times.append(ts)

    arr = {k: np.asarray(v, dtype=float) for k, v in cols.items()}
    times = np.asarray(times, dtype="datetime64[s]")
    return times, arr


def pressure_altitude(pressure_hpa, p0_hpa):
    """Pressure-based altitude (m) above the reference level p0."""
    return (T0_STD / LAPSE) * (1.0 - (pressure_hpa / p0_hpa) ** EXP)


def sonde_id_from_filename(basename):
    match = re.search(r"imet_(sn\d+)", basename)
    return match.group(1) if match else None


def imet_flight_segments(basename, sonde, flights, times):
    """Match flight_meta rows to one iMET record file.

    Returns a list of (flight_meta, index_slice). A missing end time is
    filled with the next flight's start (or the file end).
    """
    file_day = basename[:8]  # YYYYMMDD
    day = dt.datetime.strptime(basename[:4] + "-" + basename[4:6]
                               + "-" + basename[6:8], "%Y-%m-%d").date()
    candidates = [f for f in flights
                  if f"imet_{sonde}" in f["instrument_id"].replace(" ", "")
                  and any(d.strftime("%Y%m%d") == file_day
                          for d in [f["start"]])
                  and f["start"] >= times.min().astype(dt.datetime)
                                        - dt.timedelta(minutes=5)
                  and f["start"] <= times.max().astype(dt.datetime)
                                        + dt.timedelta(hours=1)]
    candidates.sort(key=lambda f: f["start"])
    segments = []
    n = len(times)
    t0 = times.min().astype(dt.datetime) - dt.timedelta(minutes=2)
    t1 = times.max().astype(dt.datetime) + dt.timedelta(minutes=2)

    for i, f in enumerate(candidates):
        end = f["end"]
        if end is None:
            end = (candidates[i + 1]["start"] if i + 1 < len(candidates) else t1)
        mask = ((times >= np.datetime64(f["start"] - dt.timedelta(seconds=30)))
                & (times <= np.datetime64(end + dt.timedelta(seconds=30))))
        if mask.any():
            segments.append((f, mask))
    _ = t0, day  # context only
    return segments


# ---------------------------------------------------------------------------
# DJI telemetry parsing
# ---------------------------------------------------------------------------
def parse_dji(path):
    """Parse a DJI telemetry CSV into (elapsed seconds, columns dict)."""
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    header = [h.strip() for h in rows[0]]
    idx = {name: i for i, name in enumerate(header)}

    def parse_flight_time(text):
        m = re.match(r"(?:(\d+)m)?\s*(?:(\d+)s)", text.strip())
        if not m:
            return None
        return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)

    seconds, cols = [], {k: [] for k in ("altitude", "home_distance",
                                         "wind_direction", "wind_speed")}
    for row in rows[1:]:
        if len(row) < len(header):
            continue
        s = parse_flight_time(row[idx["Flight time"]])
        if s is None:
            continue
        seconds.append(s)
        for key, col_name in (("altitude", "Altitude"),
                              ("home_distance", "Home Distance"),
                              ("wind_direction", "Wind Direction"),
                              ("wind_speed", "Wind Speed")):
            try:
                cols[key].append(float(row[idx[col_name]]))
            except (ValueError, IndexError):
                cols[key].append(np.nan)
    return (np.asarray(seconds, dtype=float),
            {k: np.asarray(v, dtype=float) for k, v in cols.items()})


# ---------------------------------------------------------------------------
# Plotting: per-flight iMET profile
# ---------------------------------------------------------------------------
def plot_imet_profile(flight, times, cols, mask):
    """T / RH profile vs pressure altitude for one flight segment."""
    name = flight["flight_id"] or "flight"
    date = flight["start"].strftime("%Y%m%d")
    p = cols["pressure"][mask]
    t = cols["air_temperature"][mask]
    rh = cols["rel_humidity"][mask]
    z = pressure_altitude(p, p.max())
    valid = np.isfinite(z) & np.isfinite(t)

    fig, ax = plt.subplots(figsize=(8, 7))
    ax.plot(t[valid], z[valid], color="tab:red", linewidth=1.5)
    ax.set_xlabel("Air temperature (degC)", color="tab:red")
    ax.tick_params(axis="x", labelcolor="tab:red")
    ax.grid(True, alpha=0.3)

    ax2 = ax.twiny()
    ax2.plot(rh[valid], z[valid], color="tab:blue", linewidth=1.5)
    ax2.set_xlabel("Relative humidity (%)", color="tab:blue")
    ax2.tick_params(axis="x", labelcolor="tab:blue")

    ax.set_ylabel("Pressure altitude above launch (m)")
    ax.set_title(f"{name} - iMET profile, {flight['start'].strftime('%Y-%m-%d %H:%M')} UTC\n"
                 f"site {flight['site']} (L{flight['location_id']}) ",
                 fontsize=12, fontweight="bold")
    stats = (f"n={valid.sum()}\n"
             f"T: {np.nanmin(t):.2f} .. {np.nanmax(t):.2f} degC\n"
             f"RH: {np.nanmin(rh):.1f} .. {np.nanmax(rh):.1f} %\n"
             f"p: {p.min():.1f} .. {p.max():.1f} hPa\n"
             f"z max: {z.max():.0f} m")
    ax.text(0.02, 0.02, stats, transform=ax.transAxes, va="bottom", ha="left",
            fontsize=9, family="monospace",
            bbox=dict(boxstyle="round", fc="whitesmoke", ec="gray"))
    fig.tight_layout()
    out = os.path.join(PLOT_DIR, f"{name}_profile_{date}.png")
    fig.savefig(out, dpi=OUTPUT_DPI)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Plotting: per-flight DJI wind profile
# ---------------------------------------------------------------------------
def plot_dji_wind(name, date, seconds, cols, subtitle=""):
    """Wind speed / direction vs altitude and vs flight time."""
    ws, wd = cols["wind_speed"], cols["wind_direction"]
    alt = cols["altitude"]
    valid = np.isfinite(ws) & np.isfinite(alt)
    if valid.sum() < 5:
        return None

    fig, axes = plt.subplots(1, 2, figsize=(12, 6), sharey=True)
    fig.suptitle(f"{name} - DJI wind, {date}\n{subtitle}",
                 fontsize=12, fontweight="bold")

    common = axes[0].scatter(ws[valid], alt[valid], c=wd[valid], cmap="hsv",
                             vmin=0, vmax=360, s=12, alpha=0.8)
    axes[1].plot(seconds[valid] / 60.0, alt[valid], color="gray",
                 linewidth=1, alpha=0.7, label="Altitude")
    ax_dir = axes[1].twinx()
    ax_dir.plot(seconds[valid] / 60.0, wd[valid], color="tab:olive",
                linewidth=1, drawstyle="steps-mid", label="Wind dir")
    ax_dir.set_ylabel("Wind direction (deg)", color="tab:olive")
    ax_dir.tick_params(axis="y", labelcolor="tab:olive")
    ax_dir.set_ylim(0, 360)

    axes[0].set_xlabel("Wind speed (m/s)")
    axes[0].set_ylabel("Altitude above takeoff (m)")
    axes[1].set_xlabel("Flight time (min)")
    for ax in axes:
        ax.grid(True, alpha=0.3)
    cbar = fig.colorbar(common, ax=axes[0], pad=0.02)
    cbar.set_label("Wind direction (deg)")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = os.path.join(PLOT_DIR, f"{name}_wind_{date}.png")
    fig.savefig(out, dpi=OUTPUT_DPI)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Plotting: per-file iMET overview
# ---------------------------------------------------------------------------
def plot_imet_overview(basename, times, cols, segments):
    """Time series overview of one iMET record with flight boundaries."""
    sonde = sonde_id_from_filename(basename)
    date = basename[:8]
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    fig.suptitle(f"iMET {sonde} overview - {basename} (UTC)",
                 fontsize=13, fontweight="bold")

    def seg_plot(ax, values, label, color, mask_all):
        for i, (f, mask) in enumerate(segments):
            v = values[mask]
            t = times[mask]
            ok = np.isfinite(v)
            ax.plot(t[ok], v[ok], color=color, linewidth=0.8,
                    label=label if i == 0 else None)
        ax.set_ylabel(label)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right")

    seg_plot(axes[0], cols["gps_alt"], "GPS altitude (m, raw/1000)",
             "tab:green", segments)
    seg_plot(axes[1], cols["air_temperature"], "Air temperature (degC)",
             "tab:red", segments)
    seg_plot(axes[2], cols["rel_humidity"], "Relative humidity (%)",
             "tab:blue", segments)
    for f, mask in segments:
        start = times[mask][0]
        for ax in axes:
            ax.axvline(start, color="gray", linewidth=0.8, linestyle="--",
                       alpha=0.6)
        axes[0].text(start, axes[0].get_ylim()[1],
                     f" {f['flight_id'] or '?'}",
                     fontsize=9, color="dimgray", va="top")

    axes[2].set_xlabel("Time (UTC)")
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = os.path.join(PLOT_DIR, f"{basename[:-4]}_overview.png")
    fig.savefig(out, dpi=OUTPUT_DPI)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Plotting: cross-flight comparisons
# ---------------------------------------------------------------------------
def plot_profile_comparison(segment_profiles):
    """Overlay all Endalen T/RH profiles from one day (transect)."""
    if len(segment_profiles) < 2:
        return None
    colors = plt.get_cmap("tab10").colors
    fig, axes = plt.subplots(1, 2, figsize=(13, 7), sharey=True)
    fig.suptitle("Endalen vertical profiles - iMET, 2026-10-08 "
                 "(transect along the valley, F01b-F06)",
                 fontsize=13, fontweight="bold")
    tmin, tmax, zmax = 1e9, -1e9, 0
    for (flight, z, t, rh), color in zip(segment_profiles,
                                         colors * 3):
        axes[0].plot(t, z, color=color, linewidth=1.5,
                     label=f"{flight['flight_id']} "
                           f"{flight['start'].strftime('%H:%M')}")
        axes[1].plot(rh, z, color=color, linewidth=1.5)
        tmin = min(tmin, np.nanmin(t)); tmax = max(tmax, np.nanmax(t))
        zmax = max(zmax, np.nanmax(z))
    axes[0].set_xlim(tmin - 0.5, tmax + 0.5)
    axes[0].set_xlabel("Air temperature (degC)")
    axes[1].set_xlabel("Relative humidity (%)")
    axes[0].set_ylabel("Pressure altitude above launch (m)")
    for ax in axes:
        ax.grid(True, alpha=0.3)
    axes[0].legend(loc="lower left", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out = os.path.join(PLOT_DIR, "endalen_profiles_comparison_20261008.png")
    fig.savefig(out, dpi=OUTPUT_DPI)
    plt.close(fig)
    return out


def plot_wind_profile_comparison(wind_profiles):
    """Overlay DJI wind speed profiles from flights flown the same day."""
    if len(wind_profiles) < 2:
        return None
    colors = plt.get_cmap("tab10").colors
    fig, ax = plt.subplots(figsize=(8, 7))
    ids = []
    for (label, alt, ws), color in zip(wind_profiles, colors * 3):
        valid = np.isfinite(alt) & np.isfinite(ws)
        if valid.sum() < 5:
            continue
        ax.plot(ws[valid], alt[valid], color=color, linewidth=1.2, label=label)
        ids.append(label)
    ax.set_xlabel("Wind speed (m/s)")
    ax.set_ylabel("Altitude above takeoff (m)")
    ax.set_title("DJI wind speed profiles - 2026-10-08",
                 fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    out = os.path.join(PLOT_DIR, "dji_wind_profiles_comparison_20261008.png")
    fig.savefig(out, dpi=OUTPUT_DPI)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------
def print_segment_summary(flight, times, cols, mask):
    name = flight["flight_id"] or "?"
    p = cols["pressure"][mask]
    t = cols["air_temperature"][mask]
    rh = cols["rel_humidity"][mask]
    valid = np.isfinite(p)
    z = pressure_altitude(p[valid], p[valid].max())
    t_valid = t[valid]
    rh_valid = rh[valid]
    print(f"  {name:<6} {flight['start'].strftime('%H:%M')}-"
          f"{flight['end'].strftime('%H:%M') if flight['end'] else '   '} UTC"
          f"  site {flight['site'] or 'tbd'}"
          f"  n={valid.sum():<5}"
          f"  T {np.nanmin(t_valid):6.2f}..{np.nanmax(t_valid):6.2f} degC"
          f"  RH {np.nanmin(rh_valid):5.1f}..{np.nanmax(rh_valid):5.1f} %"
          f"  zmax {np.nanmax(z):6.1f} m")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def process_imet_file(path, flights, profiles_for_comparison):
    basename = os.path.basename(path)
    sonde = sonde_id_from_filename(basename)
    times, cols = parse_imet(path)
    print("=" * 72)
    print(f"iMET file : {basename} (sonde {sonde})")
    if len(times) == 0:
        print("  No valid records.")
        return
    print(f"  {len(times)} records, {times.min()} -> {times.max()}")

    segments = imet_flight_segments(basename, sonde, flights, times)
    outputs = []
    for f, mask in segments:
        plot_imet_profile(f, times, cols, mask)
        outputs.append(f"{f['flight_id']}_profile")
        print_segment_summary(f, times, cols, mask)
        if f["site"] == "Endalen":
            p = cols["pressure"][mask]
            valid = np.isfinite(p) & np.isfinite(cols["air_temperature"][mask])
            if valid.sum() > 30:
                z = pressure_altitude(p[valid], p[valid].max())
                profiles_for_comparison.append(
                    (f, z, cols["air_temperature"][mask][valid],
                     cols["rel_humidity"][mask][valid]))
    ov = plot_imet_overview(basename, times, cols, segments)
    outputs.append(os.path.basename(ov))
    print(f"  Saved: {', '.join(outputs)}")


def process_dji_file(path, flights, winds_for_comparison):
    basename = os.path.basename(path)
    seconds, cols = parse_dji(path)
    print("=" * 72)
    print(f"DJI file  : {basename}")
    if len(seconds) == 0:
        print("  No valid records.")
        return
    print(f"  {len(seconds)} records, {seconds[0]:.0f}s -> "
          f"{seconds[-1]:.0f}s elapsed")

    date = basename[:8]
    matched = None
    rel = os.path.join("drone", basename)
    for f in flights:
        if f["data_file"] == rel:
            matched = f
            break
    name_from_flight = matched["flight_id"] if matched else None

    subtitle = ""
    if matched:
        name = name_from_flight or basename[:-4]
        subtitle = (f"site {matched['site']} (L{matched['location_id']}) "
                    f"{matched['start'].strftime('%H:%M')} UTC"
                    + (" - " + matched["notes"] if matched["notes"] else ""))
    else:
        name = basename[:-4]
        subtitle = "site / flight attribution tbd"

    ws = cols["wind_speed"]
    alt = cols["altitude"]
    valid = np.isfinite(ws) & np.isfinite(alt)
    print(f"  wind speed {np.nanmin(ws):.2f}..{np.nanmax(ws):.2f} m/s"
          f"  alt 0..{np.nanmax(alt):.1f} m")

    out = plot_dji_wind(name, date, seconds, cols, subtitle)
    if out:
        print(f"  Saved: {os.path.basename(out)}")
    if matched and valid.sum() > 30:
        winds_for_comparison.append((name, alt[valid], ws[valid]))


def main():
    parser = argparse.ArgumentParser(
        description="Analyze drone flight data (DJI + iMET) and write plots "
                    "to 04_plots/drone/.")
    parser.add_argument("files", nargs="*",
                        help="drone CSV files (default: all in data/drone/)")
    args = parser.parse_args()

    if args.files:
        files = [f if os.path.isabs(f) else os.path.abspath(f)
                 for f in args.files]
    else:
        files = sorted(os.path.join(DRONE_DIR, f)
                       for f in os.listdir(DRONE_DIR) if f.endswith(".csv"))
    if not files:
        print(f"No CSV files found in {DRONE_DIR}")
        sys.exit(1)

    os.makedirs(PLOT_DIR, exist_ok=True)
    flights = load_flights()

    imet_files = [f for f in files if "imet" in os.path.basename(f)]
    dji_files = [f for f in files if "dji" in os.path.basename(f)]

    profiles_for_comparison = []
    winds_for_comparison = []
    for path in imet_files:
        try:
            process_imet_file(path, flights, profiles_for_comparison)
        except Exception as exc:
            print(f"ERROR processing {path}: {exc}", file=sys.stderr)

    for path in dji_files:
        try:
            process_dji_file(path, flights, winds_for_comparison)
        except Exception as exc:
            print(f"ERROR processing {path}: {exc}", file=sys.stderr)

    print("=" * 72)
    comp1 = plot_profile_comparison(profiles_for_comparison)
    if comp1:
        print(f"Comparison plots: {os.path.basename(comp1)}")
    comp2 = plot_wind_profile_comparison(winds_for_comparison)
    if comp2:
        print(f"                  {os.path.basename(comp2)}")


if __name__ == "__main__":
    main()
