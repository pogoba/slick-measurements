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
    for color in COLORS:
        files = args.__dict__.get(color)
        if not files:
            continue
        name = args.__dict__.get(f"{color}_name", color)
        if isinstance(name, list):
            name = " ".join(name)
        measurements = pd.concat(
            [pd.read_csv(fh.name) for fh in files if getsize(fh.name) > 0]
        )
        df = measurements[["instances", "bytes"]].copy()
        df["system"] = name
        # bytes -> GiB for a readable axis
        df["memory_gib"] = df["bytes"] / (1024 ** 3)
        frames.append(df)
        systems.append(name)

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
    sns.move_legend(ax, "upper center", bbox_to_anchor=(0.4, 1.4),
                    ncol=3, title=None, frameon=False)

    ax.annotate(
        "↓ Lower is better", # or ↓ ← ↑ →
        xycoords="axes points",
        xy=(10, 0),
        xytext=(-45, -27),
        color="navy",
        weight="bold",
    )

    # Reference lines: physical server memory and CVM key limit
    ax.axhline(991, color="red", linestyle="-", linewidth=1)
    ax.text(5, 991, "Server memory capacity", color="red",
            fontsize=8, va="bottom", ha="left")
    ax.axvline(512, color="red", linestyle="-", linewidth=1)
    ax.text(500, 0.5, "Max. nr. of\nCVM keys", color="red",
            fontsize=8, va="bottom", ha="right",
            transform=ax.get_xaxis_transform())

    ax.set_xticks(INSTANCE_TICKS)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0, top=1100)

    ax.set_xlabel('Instances')
    ax.set_ylabel('Memory (GiB)')

    # Adjust layout and save
    fig.tight_layout(pad=0.01)
    fig.subplots_adjust(top=0.8)
    fig.savefig(args.output.name)
    plt.close()


if __name__ == '__main__':
    main()
