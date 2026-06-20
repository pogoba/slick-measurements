#!/usr/bin/env python3
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
import argparse
from re import search
from os.path import basename, getsize
import pandas as pd
from plotting import map_grid_titles
import os

PLOTTING_NAME="memory-consumption"
DEFAULT_OUTPUT=f"{PLOTTING_NAME}.pdf"

COLORS = [ str(i) for i in range(20) ]

LEGEND_MAP = {
    "vm": "VM",
    "kata": "Kata",
    "cvm": "CVM",
}

system_map = {
        'vm': 'VM',
        'kata': 'Kata',
        'cvm': 'CVM',
        }

# Instance counts we want to label on the x axis
INSTANCE_TICKS = [1, 100, 200, 300, 400, 500, 600, 700]

# Page size used to convert the SVSM trustlet page counts (.memory files) to bytes.
PAGE_SIZE = 4096


def parse_memory_file(path):
    """Parse an SVSM '.memory' file into a dict of TRUSTLET_* -> int."""
    vals = {}
    with open(path) as fh:
        for line in fh:
            m = search(r"(TRUSTLET_[A-Z_]+)\s+(\d+)", line)
            if m:
                vals[m.group(1)] = int(m.group(2))
    return vals


def slick_vnflet_frame(name, files, instances):
    """Model the "Slick VNFlets" baseline from SVSM '.memory' page stats.

    Memory for N instances is `priv_avg + N * unpriv_avg` pages, where each
    average sums the COW and non-COW pages of the (un)privileged trustlet.
    Per-trustlet averages are themselves averaged across all provided files.
    """
    priv, unpriv = [], []
    for fh in files:
        v = parse_memory_file(fh.name)
        priv.append(v["TRUSTLET_PAGES_AVG_COW_PRIV"]
                    + v["TRUSTLET_PAGES_AVG_NON_COW_PRIV"])
        unpriv.append(v["TRUSTLET_PAGES_AVG_COW_UNPRIV"]
                      + v["TRUSTLET_PAGES_AVG_NON_COW_UNPRIV"])
    priv_avg = float(np.mean(priv))
    unpriv_avg = float(np.mean(unpriv))

    df = pd.DataFrame({"instances": list(instances)})
    df["bytes"] = (priv_avg + df["instances"] * unpriv_avg) * PAGE_SIZE
    df["system"] = name
    df["memory_gib"] = df["bytes"] / (1024 ** 3)
    return df


def setup_parser():
    parser = argparse.ArgumentParser(
        description=f'Plot {PLOTTING_NAME} graph'
    )

    parser.add_argument('-t',
                        '--title',
                        type=str,
                        help='Title of the plot',
                        )
    parser.add_argument('-W', '--width',
                        type=float,
                        default=12,
                        help='Width of the plot in inches'
                        )
    parser.add_argument('-H', '--height',
                        type=float,
                        default=6,
                        help='Height of the plot in inches'
                        )
    parser.add_argument('-l', '--logarithmic',
                        action='store_true',
                        help='Plot logarithmic memory axis',
                        )
    parser.add_argument('-o', '--output',
                        type=argparse.FileType('w+'),
                        help=f'''Path to the output plot
                             (default: {DEFAULT_OUTPUT})''',
                        default=DEFAULT_OUTPUT
                        )
    parser.add_argument('-c', '--compress',
                        action='store_true',
                        help='Compress the legend',
                        default=False
                        )
    for color in COLORS:
        parser.add_argument(f'--{color}',
                            type=argparse.FileType('r'),
                            nargs='+',
                            help=f'''Paths to memory measurement CSVs for
                                  {color} plot''',
                            )
    for color in COLORS:
        parser.add_argument(f'--{color}-name',
                            type=str,
                            default=color,
                            nargs='+',
                            help=f'''Name of {color} plot''',
                            )

    return parser


def parse_args(parser):
    args = parser.parse_args()

    if not any([args.__dict__[color] for color in COLORS]):
        parser.error('At least one set of data paths must be provided')

    return args


def main():
    parser = setup_parser()
    args = parse_args(parser)

    # Each --<color> provides the memory logs of one system, labelled via
    # --<color>-name. Logs report cumulative memory (bytes) per instance count.
    frames = []
    systems = []
    # ".memory" baselines (e.g. Slick VNFlets) are modelled, not read as CSVs;
    # defer them until we know the instance range covered by the other systems.
    baselines = []
    for color in COLORS:
        files = args.__dict__.get(color)
        if not files:
            continue
        name = args.__dict__.get(f"{color}_name", color)
        if isinstance(name, list):
            name = " ".join(name)
        systems.append(name)
        if all(fh.name.endswith(".memory") for fh in files):
            baselines.append((name, files))
            continue
        measurements = pd.concat(
            [pd.read_csv(fh.name) for fh in files if getsize(fh.name) > 0]
        )
        df = measurements[["instances", "bytes"]].copy()
        df["system"] = name
        # bytes -> GiB for a readable axis
        df["memory_gib"] = df["bytes"] / (1024 ** 3)
        frames.append(df)

    # Span the modelled baselines over the same instance counts as the measured
    # systems (fall back to the labelled ticks if no CSV systems are present).
    if frames:
        instances = sorted(pd.concat(frames)["instances"].unique())
    else:
        instances = INSTANCE_TICKS
    for name, files in baselines:
        frames.append(slick_vnflet_frame(name, files, instances))

    df = pd.concat(frames, ignore_index=True)

    fig, ax = plt.subplots(figsize=(args.width, args.height))

    ax.set_axisbelow(True)
    ax.grid(True)

    sns.lineplot(
        data=df,
        x="instances",
        y="memory_gib",
        hue="system",
        hue_order=systems,
        style="system",
        style_order=systems,
        markers=True,
        errorbar='ci',
        ax=ax,
    )

    if args.logarithmic:
        ax.set_yscale('log')

    def rename_legend_labels(ax, label_map):
        if ax.get_legend() is not None:
            for i, text in enumerate(ax.get_legend().get_texts()):
                if text.get_text() in label_map:
                    text.set_text(label_map[text.get_text()])

    rename_legend_labels(ax, LEGEND_MAP)

    # Position the legend outside the plot area
    sns.move_legend(ax, "upper center", bbox_to_anchor=(0.4, 1.2),
                    ncol=2, title=None, frameon=False)

    ax.annotate(
        "↓ Lower is better", # or ↓ ← ↑ →
        xycoords="axes points",
        xy=(10, 0),
        xytext=(-25, -27),
        color="navy",
        weight="bold",
    )

    # Reference lines: physical server memory and CVM key limit
    ax.axhline(956, color="red", linestyle="-", linewidth=1)
    ax.text(5, 940, "Available RAM", color="red",
            va="top", ha="left")
    ax.axvline(512, color="red", linestyle="-", linewidth=1)
    ax.text(500, 0.5, "Max. nr. of\nCVM keys", color="red",
            va="bottom", ha="right",
            transform=ax.get_xaxis_transform())

    ax.set_xticks(INSTANCE_TICKS)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)

    ax.set_xlabel('Instances')
    ax.set_ylabel('Memory (GiB)')

    # Adjust layout and save
    fig.tight_layout(pad=0.03)
    # fig.subplots_adjust(top=0.8)
    fig.savefig(args.output.name)
    plt.close()


if __name__ == '__main__':
    main()
