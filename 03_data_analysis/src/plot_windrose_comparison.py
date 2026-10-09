"""
plot_windrose_comparison.py
===========================

Combine the wind roses of the three Endalen AWS stations
(Bobby McGee, Mrs Robinson, Rosanne) into a single figure for direct
visual comparison. Uses the same data pipeline and binning as
`analyze_aws_data.py` (10-minute bins, speed classes 0-0.1-0.2-0.4-1+ m/s).

Usage:
    python3 plot_windrose_comparison.py [--minutes 10]

Output:
    04_plots/WindRose_comparison_Oct6-7.png

Dependencies:
    numpy, matplotlib
"""

import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

import analyze_aws_data as aws


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=int, default=aws.DEFAULT_INTERVAL_MIN,
                        help="resampling interval in minutes (default: 10)")
    args = parser.parse_args()

    files = sorted(os.path.join(aws.DATA_DIR, f)
                   for f in os.listdir(aws.DATA_DIR) if f.endswith(".dat"))
    if not files:
        print(f"No .dat files found in {aws.DATA_DIR}")
        return

    fig, axes = plt.subplots(1, len(files), figsize=(6.5 * len(files), 6.5),
                             subplot_kw=dict(projection="polar"))
    if len(files) == 1:
        axes = [axes]

    colors = ["#c6dbef", "#6baed6", "#3182bd", "#08519c"]
    speed_edges = [0, 0.1, 0.2, 0.4, 1.0]
    n_bins = 16
    angle_edges = np.linspace(0, 2 * np.pi, n_bins + 1)
    centers = angle_edges[:-1] + np.diff(angle_edges) / 2

    max_count = 0.0
    roses = []
    for path in files:
        try:
            station = aws.station_name(path)
            times, columns, units, meas_types = aws.parse_toa5(path)
            bin_times, bin_columns, _ = aws.resample_to_bins(
                times, columns, meas_types, args.minutes)
            ws = bin_columns["wind_speed"]
            wd = bin_columns["wind_direction"]
            valid = (ws > 0.05) & np.isfinite(ws) & np.isfinite(wd)
            n_valid = int(valid.sum())
            dirs = (wd[valid] % 360.0) / 360.0 * 2 * np.pi
            speeds = ws[valid]
            stacked = []
            for i in range(len(speed_edges) - 1):
                lo, hi = speed_edges[i], speed_edges[i + 1]
                counts, _ = np.histogram(dirs[(speeds >= lo) & (speeds < hi)],
                                         bins=angle_edges)
                stacked.append(counts)
                max_count = max(max_count, counts.max())
            roses.append((station, stacked, n_valid))
        except Exception as exc:
            print(f"ERROR processing {path}: {exc}", file=sys.__stderr__)
            roses.append((aws.station_name(path), None, 0))

    for ax, (station, stacked, n_valid) in zip(axes, roses):
        if stacked is None:
            ax.set_title(f"{station}\n(no data)", fontsize=11, fontweight="bold")
            continue
        bottom = np.zeros(n_bins)
        for counts, color in zip(stacked, colors):
            ax.bar(centers, counts, width=np.diff(angle_edges), bottom=bottom,
                   color=color, alpha=0.85, edgecolor="white", linewidth=0.4)
            bottom += counts
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_rlabel_position(30)
        # shared radial scale for fair visual comparison
        ax.set_rmax(max(max_count * 1.05, 1))
        ax.set_title(f"{station.title().replace('Mcgee', 'McGee')}\n"
                     f"n={n_valid} ({args.minutes}-min bins)",
                     fontsize=12, fontweight="bold")

    handles = [Line2D([], [], marker="s", linestyle="", markersize=9,
                      color=c, label=f"{lo:.1f}-{hi:.1f} m/s")
               for c, (lo, hi) in zip(colors, zip(speed_edges, speed_edges[1:]))]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False)
    fig.suptitle("Wind roses - Endalen AWS stations, Oct 6-7 2026 "
                 "(only wind > 0.05 m/s)", fontsize=14, fontweight="bold")
    out = os.path.join(aws.PLOT_DIR, "WindRose_comparison_Oct6-7.png")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(out, dpi=aws.OUTPUT_DPI)
    print(f"Saved plot: {out}")


if __name__ == "__main__":
    main()
