"""
analyze_aws_data.py
===================

Analyze Campbell Scientific TOA5 logger files (mini AWS stations) and
produce relevant plots.

Only data from October 6 and 7, 2026 are considered. The raw 1-minute
records are resampled into 10-minute bins (change with --minutes) using
aggregations that match the sensor measurement type declared in the file.

Usage:
    python3 analyze_aws_data.py [--minutes 10] [file1.dat file2.dat ...]

If no file is given, all .dat files in the data folder are processed.
When at least two stations are processed in one run, comparison figures
overlaying the stations are also produced.

Output:
    Plots are saved in the 04_plots folder.

Dependencies:
    numpy, matplotlib
"""

import argparse
import csv
import datetime as dt
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
PLOT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "04_plots"))
OUTPUT_DPI = 150
GAP_THRESHOLD_MIN = 30.0  # break time series where the sampling gap exceeds this
DEFAULT_INTERVAL_MIN = 10  # resampling interval applied to the raw 1-min data
SELECT_START = dt.datetime(2026, 10, 6, 0, 0, 0)  # October 6, 00:00
SELECT_END = dt.datetime(2026, 10, 8, 0, 0, 0)    # October 7, 24:00 (exclusive)

SENSOR_GROUPS = {
    "overview": [
        ("temperature", "Air temperature", "degC"),
        ("rel_humidity", "Relative humidity", "%"),
        ("wind_speed", "Wind speed", "m/s"),
        ("wind_direction", "Wind direction", "deg"),
    ],
    "extra": [
        ("air_pressure", "Air pressure", "hPa"),
        ("ground_temperature", "Ground temperature", "degC"),
        ("surface_brightness_temperature", "Surface brightness temperature", "degC"),
        ("IRup_body_temperature", "IR-up body temperature", "degC"),
        ("LWup", "LW-up radiation", "W/m^2"),
    ],
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def parse_toa5(path):
    """Parse a TOA5 CSV file into (timestamps, dict of column arrays)."""
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    if len(rows) < 4 or rows[0][0] != "TOA5":
        raise ValueError(f"Not a TOA5 file: {path}")

    header = rows[1]
    units = rows[2]
    meas_types = rows[3]
    data_rows = rows[4:]

    timestamps = []
    columns = {name: [] for name in header[2:] if name}

    for row in data_rows:
        if len(row) < 2:
            continue
        try:
            ts = dt.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        # Keep only October 6 and 7, 2026
        if not (SELECT_START <= ts < SELECT_END):
            continue
        if hasattr(ts, "tzinfo") is False and ts is None:
            continue
        timestamps.append(ts)
        for name, value in zip(header[2:], row[2:]):
            try:
                columns[name].append(float(value))
            except ValueError:
                columns[name].append(np.nan)

    timestamps = np.asarray(timestamps, dtype="datetime64[s]")
    for name in columns:
        columns[name] = np.asarray(columns[name], dtype=float)
    return (timestamps, columns,
            dict(zip(header[2:], units[2:])),
            dict(zip(header[2:], meas_types[2:])))


def resample_to_bins(times, columns, meas_types, interval_min):
    """Resample irregular raw records onto fixed bins of interval_min.

    Aggregation follows the measurement type declared in the TOA5 header:
    Min -> bin minimum, Max -> bin maximum, Avg/Smp -> bin mean. Wind
    direction is aggregated as a circular mean weighted by wind speed
    (only where wind > 0.05 m/s, i.e. direction is meaningful).

    All stations share the same grid anchored at SELECT_START, which makes
    the outputs directly comparable. Returns:
        (bin_times, bin_columns, samples_per_bin)
    """
    interval_s = interval_min * 60
    start_s = int(SELECT_START.timestamp())
    end_s = int(SELECT_END.timestamp())
    n_bins = (end_s - start_s) // interval_s
    bin_times = (np.arange(n_bins, dtype=np.int64) * interval_s
                 + start_s).astype("datetime64[s]")

    raw_sec = times.astype("datetime64[s]").astype(np.int64)
    idx = np.clip((raw_sec - start_s) // interval_s, 0, n_bins - 1)
    samples_per_bin = np.bincount(idx, minlength=n_bins)

    bin_cols = {}
    for name, values in columns.items():
        out = np.full(n_bins, np.nan)
        meas = meas_types.get(name, "Avg")
        for k in range(n_bins):
            vals = values[idx == k]
            if not len(vals) or not np.isfinite(vals).any():
                continue
            if name == "wind_direction":
                ws = columns["wind_speed"][idx == k]
                use = np.isfinite(vals) & np.isfinite(ws) & (ws > 0.05)
                if not use.any():
                    continue
                x = np.sum(ws[use] * np.sin(np.radians(vals[use])))
                y = np.sum(ws[use] * np.cos(np.radians(vals[use])))
                if x == 0.0 and y == 0.0:
                    continue
                out[k] = (np.degrees(np.arctan2(x, y)) + 360.0) % 360.0
            elif meas == "Min":
                out[k] = np.nanmin(vals)
            elif meas == "Max":
                out[k] = np.nanmax(vals)
            else:
                out[k] = np.nanmean(vals)
        bin_cols[name] = out
    return bin_times, bin_cols, samples_per_bin


def station_name(path):
    """Derive a readable station name from the file name.

    Supports the current naming convention
    `YYYYMMDD_instrument_location_[...].dat` (e.g.
    `20261008_bobbymcgee_endalen_1min.dat`) and the legacy
    `<Station>_Res_data_...` pattern.
    """
    name = os.path.basename(path)
    if "_" in name and name[:8].isdigit():
        return name.split("_")[1]  # instrument field
    name = name.split("_Res_data")[0]
    return name.replace("_", " ").replace(" Series", "").strip() or "Station"


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------
def split_segments(times, values):
    """Split a time series into segments where gaps exceed the threshold."""
    seconds = times.astype("datetime64[s]").astype(np.int64)
    cut = np.where(np.diff(seconds) > GAP_THRESHOLD_MIN * 60)[0] + 1
    segments = np.split(np.arange(len(values)), cut)
    for seg in segments:
        if len(seg) < 2:
            continue
        yield times[seg], values[seg]


def plot_timeseries(ax, times, values, label, color, linewidth=1.0,
                    marker=None, linestyle="-"):
    """Plot a time series, breaking lines at long sampling gaps."""
    for t, v in split_segments(times, values):
        ax.plot(t, v, color=color, linewidth=linewidth, linestyle=linestyle,
                marker=marker, markersize=2, label=label)
    ax.set_xlabel("Time (UTC)")
    ax.grid(True, alpha=0.3)


def format_stats_text(columns):
    """Short min/max/mean summary used in the overview figure."""
    lines = []
    for name, label in [("temperature", "Air temperature (degC)"),
                        ("rel_humidity", "Relative humidity (%)"),
                        ("wind_speed", "Wind speed (m/s)"),
                        ("BattV", "Battery (V)")]:
        values = columns[name][np.isfinite(columns[name])]
        if len(values):
            lines.append(f"{label}\n  min {values.min():7.2f}  "
                         f"max {values.max():7.2f}  mean {values.mean():.2f}")
    return "\n".join(lines)


def make_overview_plot(station, times, columns, interval_min):
    """3x2 overview: temperature, RH, wind, direction, battery, statistics."""
    fig, axes = plt.subplots(3, 2, figsize=(13, 10), sharex=True)
    fig.suptitle(f"{station} - AWS overview, Oct 6-7 2026 "
                 f"({interval_min}-min data)", fontsize=13, fontweight="bold")

    # Row 1: air temperature and relative humidity
    plot_timeseries(axes[0, 0], times, columns["temperature"],
                    "Air temperature", "tab:red")
    axes[0, 0].set_ylabel("degC")
    axes[0, 0].legend(loc="upper right")

    plot_timeseries(axes[0, 1], times, columns["rel_humidity"],
                    "Relative humidity", "tab:blue")
    axes[0, 1].set_ylabel("%")
    axes[0, 1].legend(loc="upper right")

    # Row 2: wind speed with gusts, and battery voltage
    plot_timeseries(axes[1, 0], times, columns["wind_speed"],
                    "Wind speed (avg)", "tab:green")
    plot_timeseries(axes[1, 0], times, columns["gust_speed"],
                    "Gust speed (max)", "tab:orange")
    axes[1, 0].set_ylabel("m/s")
    axes[1, 0].legend(loc="upper right")

    plot_timeseries(axes[1, 1], times, columns["BattV"],
                    "Battery voltage", "tab:purple")
    axes[1, 1].set_ylabel("Volts")
    axes[1, 1].legend(loc="upper right")

    # Row 3: wind direction (only meaningful when wind is blowing) and stats
    ws = columns["wind_speed"]
    wd = columns["wind_direction"]
    blow = ws > 0.05
    if blow.any():
        plot_timeseries(axes[2, 0], times[blow], wd[blow],
                        "Wind direction (wind > 0.05 m/s)", "tab:olive")
    axes[2, 0].set_ylabel("deg")
    axes[2, 0].set_ylim(0, 360)
    axes[2, 0].legend(loc="upper right")

    axes[2, 1].axis("off")
    axes[2, 1].text(0.02, 0.98, format_stats_text(columns),
                    transform=axes[2, 1].transAxes, va="top", ha="left",
                    fontsize=10, family="monospace",
                    bbox=dict(boxstyle="round", fc="whitesmoke", ec="gray"))

    for ax in axes.flat:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = os.path.join(PLOT_DIR, f"{station}_Overview_Oct6-7.png")
    fig.savefig(out, dpi=OUTPUT_DPI)
    plt.close(fig)
    return out


def make_wind_rose(station, times, columns, interval_min):
    """Wind rose from wind speed and direction (only when wind is blowing)."""
    ws = columns["wind_speed"]
    wd = columns["wind_direction"]
    valid = (ws > 0.05) & np.isfinite(ws) & np.isfinite(wd)
    if valid.sum() < 20:
        return None

    dirs = (wd[valid] % 360.0) / 360.0 * 2 * np.pi
    speeds = ws[valid]
    speed_edges = [0, 0.1, 0.2, 0.4, 1.0]
    n_bins = 16
    angle_edges = np.linspace(0, 2 * np.pi, n_bins + 1)

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, projection="polar")
    colors = ["#c6dbef", "#6baed6", "#3182bd", "#08519c"]
    max_count = 0

    for i in range(len(speed_edges) - 1):
        lo, hi = speed_edges[i], speed_edges[i + 1]
        mask = (speeds >= lo) & (speeds < hi)
        counts, _ = np.histogram(dirs[mask], bins=angle_edges)
        max_count = max(max_count, counts.max())
        centers = angle_edges[:-1] + np.diff(angle_edges) / 2
        ax.bar(centers, counts, width=np.diff(angle_edges),
               bottom=0, color=colors[i], alpha=0.85,
               edgecolor="white", linewidth=0.5,
               label=f"{lo:.1f}-{hi:.1f} m/s")

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlabel_position(30)
    ax.set_title(f"{station} - Wind rose, Oct 6-7 2026 "
                 f"({interval_min}-min data, n={valid.sum()})",
                 fontsize=13, fontweight="bold")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.15, -0.12))
    out = os.path.join(PLOT_DIR, f"{station}_WindRose_Oct6-7.png")
    fig.savefig(out, dpi=OUTPUT_DPI, bbox_inches="tight")
    plt.close(fig)
    return out


def make_extra_plot(station, times, columns, interval_min):
    """Plot additional sensors when the station has them."""
    available = [(name, label, unit) for name, label, unit in SENSOR_GROUPS["extra"]
                 if name in columns and np.isfinite(columns[name]).any()]
    if not available:
        return None

    n = len(available)
    fig, axes = plt.subplots(n, 1, figsize=(13, 3.2 * n), sharex=True, squeeze=False)
    fig.suptitle(f"{station} - Additional sensors, Oct 6-7 2026 "
                 f"({interval_min}-min data)", fontsize=13, fontweight="bold")
    colors = plt.get_cmap("Dark2").colors
    for ax, (name, label, unit), color in zip(axes[:, 0], available,
                                              colors[:n]):
        plot_timeseries(ax, times, columns[name], label, color)
        ax.set_ylabel(unit)
        ax.legend(loc="upper right")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = os.path.join(PLOT_DIR, f"{station}_ExtraSensors_Oct6-7.png")
    fig.savefig(out, dpi=OUTPUT_DPI)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Station comparisons (overlaid plots)
# ---------------------------------------------------------------------------
def make_comparison_plots(stations, interval_min):
    """Overlay common variables of several stations on one figure.

    stations: list of (station_name, times, columns). All series share the
    same resampled time grid, so they can be overlaid directly.
    """
    if len(stations) < 2:
        return []
    colors = plt.get_cmap("tab10").colors
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)
    fig.suptitle(f"Station comparison, Oct 6-7 2026 ({interval_min}-min data)",
                 fontsize=13, fontweight="bold")

    for i, (name, times, columns) in enumerate(stations):
        color = colors[i % len(colors)]
        plot_timeseries(axes[0, 0], times, columns["temperature"], name, color)
        plot_timeseries(axes[0, 1], times, columns["rel_humidity"], name, color)
        plot_timeseries(axes[1, 0], times, columns["wind_speed"], name, color)
        plot_timeseries(axes[1, 0], times, columns["gust_speed"], None, color,
                        linewidth=1.3, linestyle="--")
        ws = columns["wind_speed"]
        wd = columns["wind_direction"]
        blow = ws > 0.05
        if blow.any():
            plot_timeseries(axes[1, 1], times[blow], wd[blow], name, color)

    axes[0, 0].set_ylabel("degC")
    axes[0, 0].legend(loc="upper right")
    axes[0, 1].set_ylabel("%")
    axes[0, 1].legend(loc="upper right")
    axes[1, 0].set_ylabel("m/s")
    handles, labels = axes[1, 0].get_legend_handles_labels()
    handles.append(Line2D([], [], color="black", linestyle="--",
                          label="Gust speed (bin max)"))
    axes[1, 0].legend(handles=handles, loc="upper right")
    axes[1, 1].set_ylabel("deg")
    axes[1, 1].set_ylim(0, 360)
    axes[1, 1].legend(loc="upper right")

    for ax in axes.flat:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = os.path.join(PLOT_DIR, "Comparison_Overview_Oct6-7.png")
    fig.savefig(out, dpi=OUTPUT_DPI)
    plt.close(fig)
    return [out]


def make_pressure_comparison(stations, interval_min):
    """Overlay air pressure for the stations that measure it."""
    have = [(n, t, c) for n, t, c in stations
            if "air_pressure" in c and np.isfinite(c["air_pressure"]).any()]
    if len(have) < 2:
        return []
    colors = plt.get_cmap("tab10").colors
    fig, ax = plt.subplots(figsize=(13, 4.5))
    for i, (name, times, columns) in enumerate(have):
        plot_timeseries(ax, times, columns["air_pressure"], name,
                        colors[i % len(colors)])
    ax.set_ylabel("hPa")
    ax.set_title(f"Air pressure comparison, Oct 6-7 2026 "
                 f"({interval_min}-min data)", fontsize=13, fontweight="bold")
    ax.legend(loc="upper right")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    out = os.path.join(PLOT_DIR, "Comparison_AirPressure_Oct6-7.png")
    fig.savefig(out, dpi=OUTPUT_DPI)
    plt.close(fig)
    return [out]


# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------
def print_summary(path, station, times, columns, units, interval_min,
                  n_raw, samples_per_bin):
    print("=" * 72)
    print(f"Station : {station}")
    print(f"File    : {path}")
    if len(times) == 0:
        print("No data within October 6-7 2026.")
        return
    n_bins_max = int((SELECT_END - SELECT_START).total_seconds()
                     / (interval_min * 60))
    n_bins = (samples_per_bin > 0).sum()
    filled = samples_per_bin[samples_per_bin > 0]
    first = times[samples_per_bin > 0][0]
    last = times[samples_per_bin > 0][-1]
    print(f"1-min records   : {n_raw}")
    print(f"{interval_min}-min bins    : {n_bins} of {n_bins_max} "
          f"({n_bins / n_bins_max * 100:.1f}% coverage), "
          f"mean {filled.mean():.1f} samples/bin")
    print(f"Data period     : {first} -> {last} (bin starts)")
    print("-" * 72)
    print(f"{'Variable':<32}{'Unit':<10}{'Valid':<8}{'Min':>12}{'Max':>12}{'Mean':>12}")
    for name, label, unit in SENSOR_GROUPS["overview"] + SENSOR_GROUPS["extra"]:
        if name not in columns:
            continue
        values = columns[name]
        valid = values[np.isfinite(values)]
        unit_text = units.get(name, "")
        if len(valid) == 0:
            print(f"{label:<32}{unit_text:<10}{'0':<8}")
            continue
        print(f"{label:<32}{unit_text:<10}{len(valid):<8}"
              f"{valid.min():>12.2f}{valid.max():>12.2f}{valid.mean():>12.2f}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def process_file(path, interval_min):
    """Analyse one station file; return (name, times, columns) for later use
    in comparison plots, or None if the window is empty."""
    station = station_name(path)
    times, columns, units, meas_types = parse_toa5(path)
    if len(times) == 0:
        print_summary(path, station, times, columns, units, interval_min,
                      0, np.array([]))
        return None
    bin_times, bin_columns, samples_per_bin = resample_to_bins(
        times, columns, meas_types, interval_min)
    print_summary(path, station, bin_times, bin_columns, units, interval_min,
                  len(times), samples_per_bin)
    if len(bin_times) == 0:
        return None

    plots = [
        make_overview_plot(station, bin_times, bin_columns, interval_min),
        make_wind_rose(station, bin_times, bin_columns, interval_min),
        make_extra_plot(station, bin_times, bin_columns, interval_min),
    ]
    print(f"Saved plots: {', '.join(p for p in plots if p)}\n")
    return station, bin_times, bin_columns


def main():
    parser = argparse.ArgumentParser(
        description="Analyze CR200 mini-AWS logger files (TOA5), Oct 6-7 2026, "
                    "resampled to N-minute bins (default 10).")
    parser.add_argument("--minutes", type=int, default=DEFAULT_INTERVAL_MIN,
                        help="resampling interval in minutes (default: 10)")
    parser.add_argument("files", nargs="*",
                        help="One or more .dat files (default: all .dat in the "
                             "data folder)")
    args = parser.parse_args()

    if args.minutes <= 0:
        print("--minutes must be a positive integer.")
        sys.exit(1)

    if args.files:
        files = [f if os.path.isabs(f) else os.path.join(SCRIPT_DIR, f)
                 for f in args.files]
    else:
        files = sorted(os.path.join(DATA_DIR, f)
                       for f in os.listdir(DATA_DIR) if f.endswith(".dat"))

    if not files:
        print(f"No .dat files found in {DATA_DIR}")
        sys.exit(1)

    os.makedirs(PLOT_DIR, exist_ok=True)
    stations = []
    for path in files:
        try:
            result = process_file(path, args.minutes)
            if result is not None:
                stations.append(result)
        except Exception as exc:
            print(f"ERROR processing {path}: {exc}", file=sys.stderr)

    if len(stations) >= 2:
        comparison_plots = (make_comparison_plots(stations, args.minutes)
                            + make_pressure_comparison(stations, args.minutes))
        print(f"Comparison plots: {', '.join(comparison_plots)}\n")


if __name__ == "__main__":
    main()