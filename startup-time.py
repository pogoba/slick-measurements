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

# Broken y-axis: the lower half zooms into [0, SPLIT_LOW] so the small systems
# (Gramine, Kata, ...) are readable; the upper half shows [SPLIT_HIGH, max] to
# keep the tall VM/CVM bars in view.
SPLIT_LOW = 400
SPLIT_HIGH = 400

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
    # Order stack segments by overall magnitude so the smallest portions end up
    # at the bottom of each bar (seaborn stacks hue_order[0] at the top).
    step_sizes = df.groupby('step', observed=True)['time_ms'].sum()
    steps = list(step_sizes.sort_values(ascending=False).index)

    df['system'] = pd.Categorical(df['system'], categories=systems, ordered=True)
    df['system'] = df['system'].cat.rename_categories(system_map)

    # Broken y-axis: stack the same plot on two axes and zoom each differently.
    fig, (ax_top, ax_bottom) = plt.subplots(
        2, 1, sharex=True, figsize=(args.width, args.height),
        gridspec_kw={'height_ratios': [2, 1]},
    )
    if args.title:
        ax_top.set_title(args.title)

    for ax in (ax_top, ax_bottom):
        ax.set_axisbelow(True)
        if not args.slides:
            ax.grid()
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
                   legend=(ax is ax_top),
                   ax=ax,
                   )

    # lower half zooms in, upper half shows the bar tops
    total_max = df.groupby('system', observed=True)['time_ms'].sum().max()
    ax_bottom.set_ylim(0, SPLIT_LOW)
    ax_top.set_ylim(SPLIT_HIGH, total_max * 1.15)

    # hide the facing spines and draw diagonal break marks across the cut
    ax_top.spines['bottom'].set_visible(False)
    ax_bottom.spines['top'].set_visible(False)
    ax_top.tick_params(axis='x', which='both', bottom=False, labelbottom=False)

    d = .5  # slope of the diagonal break marks
    break_kwargs = dict(marker=[(-1, -d), (1, d)], markersize=8,
                        linestyle="none", color='dimgray', mec='dimgray',
                        mew=1, clip_on=False)
    ax_top.plot([0, 1], [0, 0], transform=ax_top.transAxes, **break_kwargs)
    ax_bottom.plot([0, 1], [1, 1], transform=ax_bottom.transAxes, **break_kwargs)

    sns.move_legend(
        ax_top, "upper center",
        bbox_to_anchor=(.5, 1.0), bbox_transform=fig.transFigure,
        ncol=2, title=None, frameon=False, fontsize=8,
    )
    # keep the (many) x-axis system labels from overlapping in a narrow figure
    ax_bottom.tick_params(axis='x', labelsize=8)

    color_hatch_map = dict()
    # Fix the legend hatches
    for i, legend_patch in enumerate(ax_top.get_legend().get_patches()):
        hatch = hatches[i % len(hatches)]
        legend_patch.set_hatch(f"{hatch}{hatch}")
        color_hatch_map[legend_patch.get_facecolor()] = hatch

    for ax in (ax_top, ax_bottom):
        for bar in ax.patches:
            hatch = color_hatch_map.get(bar.get_facecolor())
            if hatch is not None:
                bar.set_hatch(hatch)

    # Total labels above each stacked bar, on whichever half the total sits in
    totals = df.groupby('system', observed=True)['time_ms'].sum()
    for i, name in enumerate(system_map[s] for s in systems):
        total = totals[name]
        target = ax_top if total > SPLIT_LOW else ax_bottom
        target.annotate(f"{total:.1f}", xy=(i, total), xytext=(0, 2),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=7)

    if (args.slides):
        ax_bottom.annotate(
            "↓ Lower is better", # or ↓ ← ↑ →
            xycoords="axes points",
            xy=(0, 0),
            xytext=(-4, -28),
            color="navy",
            weight="bold",
        )

    ax_bottom.set_xlabel(XLABEL)
    ax_top.set_ylabel("")
    ax_bottom.set_ylabel("")
    fig.supylabel(YLABEL, fontsize=10)

    fig.tight_layout(pad=0.1)
    fig.subplots_adjust(top=0.7, hspace=0.12)
    fig.savefig(args.output.name)
    plt.close()


if __name__ == '__main__':
    main()
