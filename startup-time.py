#!/usr/bin/env python3
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import argparse
import seaborn as sns
import pandas as pd
from re import search, findall, MULTILINE
from os.path import basename, getsize, isfile
from typing import List, Any
from plotting import HATCHES as _hatches
from tqdm import tqdm
from functools import reduce
import scipy.stats as scipyst
import operator


# resource on how to do stackplots:
# https://stackoverflow.com/questions/59038979/stacked-bar-chart-in-seaborn

PLOTTING_NAME="startup-time"
DEFAULT_OUTPUT=f"{PLOTTING_NAME}.pdf"

hatches = _hatches.copy()
hatches[0] = _hatches[6]
hatches[6] = _hatches[2]
hatches[2] = _hatches[0]

COLORS = [ str(i) for i in range(20) ]

# Order systems by increasing isolation/overhead
SYSTEM_ORDER = ['native', 'gramine', 'kata', 'vm', 'cvm']
system_map = {
        'native': 'Native',
        'gramine': 'Gramine',
        'kata': 'Kata',
        'vm': 'VM',
        'cvm': 'CVM',
        }

# Stacking order of startup phases, bottom (earliest) to top (latest).
# Phases that never co-occur in the same system are interleaved so that each
# system's bar stacks in chronological order.
STEP_ORDER = [
    'VMM (QEMU)',
    'Firmware (OVMF)',
    'OS/Guest-OS',
    'Early runtime',
    'VMM+OVMF+OS',
    'Runtime',
    'Invoke',
]

YLABEL = 'Startup time [ms]'
XLABEL = 'System'

def map_hue(df_hue, hue_map):
    return df_hue.apply(lambda row: hue_map.get(str(row), row))

def log(s: str):
    print(s, flush=True)

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
    parser.add_argument('-o', '--output',
                        type=argparse.FileType('w+'),
                        help=f'''Path to the output plot
                             (default: {DEFAULT_OUTPUT})''',
                        default=DEFAULT_OUTPUT
                        )
    parser.add_argument('-l', '--logarithmic',
                        action='store_true',
                        help='Plot logarithmic time axis',
                        )
    parser.add_argument('-c', '--cached',
                        action='store_true',
                        help='Use cached version of parsed data',
                        )
    parser.add_argument('-s', '--slides',
                        action='store_true',
                        help='Use Other setting to plot for presentation slides',
                        )
    for color in COLORS:
        parser.add_argument(f'--{color}',
                            type=argparse.FileType('r'),
                            nargs='+',
                            help=f'''Path to the startup-time CSV for
                                  the {color} plot''',
                            )
    for color in COLORS:
        parser.add_argument(f'--{color}-name',
                            type=str,
                            default=color,
                            help=f'''Name of {color} plot''',
                            )

    return parser


def parse_args(parser):
    args = parser.parse_args()

    if not any([args.__dict__[color] for color in COLORS]):
        parser.error('At least one data path must be provided')

    return args


def main():
    parser = setup_parser()
    args = parse_args(parser)

    fig = plt.figure(figsize=(args.width, args.height))
    ax = fig.add_subplot(1, 1, 1)
    if args.title:
        plt.title(args.title)
    if not args.slides:
        plt.grid()

    # All data comes from a single file holding every system's breakdown.
    log("Reading data")
    dfs = []
    for color in COLORS:
        files = args.__dict__.get(color)
        if not files:
            continue
        for fh in files:
            if getsize(fh.name) > 0:
                dfs += [pd.read_csv(fh.name)]
    data = pd.concat(dfs, ignore_index=True)

    log("Preparing plotting data")
    # Mean over samples per (system, step)
    df = data.groupby(['system', 'step'])['time_ms'].mean().reset_index()

    systems = [s for s in SYSTEM_ORDER if s in df['system'].unique()]
    steps = [s for s in STEP_ORDER if s in df['step'].unique()]

    df['system'] = pd.Categorical(df['system'], categories=systems, ordered=True)
    df['system'] = df['system'].cat.rename_categories(system_map)

    # Plot using Seaborn
    sns.histplot(
               data=df,
               x='system',
               weights='time_ms',
               hue="step",
               hue_order=steps,
               multiple="stack",
               palette="deep",
               edgecolor="dimgray",
               shrink=0.8,
               )

    sns.move_legend(
        ax, "lower center",
        bbox_to_anchor=(.5, 1.02), ncol=2, title=None, frameon=False,
        fontsize=8,
    )
    # keep the (many) x-axis system labels from overlapping in a narrow figure
    ax.tick_params(axis='x', labelsize=8)

    color_hatch_map = dict()
    # Fix the legend hatches
    for i, legend_patch in enumerate(ax.get_legend().get_patches()):
        hatch = hatches[i % len(hatches)]
        legend_patch.set_hatch(f"{hatch}{hatch}")
        color_hatch_map[legend_patch.get_facecolor()] = hatch

    for bar in ax.patches:
        hatch = color_hatch_map.get(bar.get_facecolor())
        if hatch is not None:
            bar.set_hatch(hatch)

    if (args.slides):
        ax.annotate(
            "↓ Lower is better", # or ↓ ← ↑ →
            xycoords="axes points",
            xy=(0, 0),
            xytext=(-4, -28),
            color="navy",
            weight="bold",
        )

    plt.xlabel(XLABEL)
    plt.ylabel(YLABEL)

    if args.logarithmic:
        ax.set_yscale('log')
    else:
        plt.ylim(bottom=0)

    plt.tight_layout(pad=0.1)
    plt.subplots_adjust(top=0.62)
    plt.savefig(args.output.name)
    plt.close()


if __name__ == '__main__':
    main()
