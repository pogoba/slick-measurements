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

# Order systems by increasing isolation/overhead. The Slick variants are CVM
# plus a cumulative stack of iomgr's startup phases (see build_slick_systems).
SYSTEM_ORDER = ['native', 'gramine', 'kata', 'vm', 'cvm',
                'slick', 'zygote', 'trustlet']
system_map = {
        'native': 'Native',
        'gramine': 'Gramine',
        'kata': 'Kata',
        'vm': 'VM',
        'cvm': 'CVM',
        'slick': 'Slick',
        'zygote': 'Zygote',
        'trustlet': 'Trustlet',
        }

# iomgr phases (from out29 startup.csv) that make up the Slick systems. The
# "remaining" tasks are the small ones that are merged into one segment.
IOMGR_REMAINING = ['trustlet', 'iomgr_shm', 'init_trustlets',
                   'trustlet_shm', 'init_trustlets2', 'launch_trustlets']


def build_slick_systems(data):
    """Synthesize the Slick systems from the CVM base and iomgr phases.

      - slick:    CVM base + DPDK
      - zygote:   iomgr's zygote phase only, shown as a single "Runtime" segment
      - trustlet: remaining iomgr tasks only (~2.5s), as a single "Invoke" segment

    Returns `data` with the new systems appended and the raw 'iomgr' rows
    (which only existed to source these phases) removed.
    """
    iomgr = data[data['system'] == 'iomgr'].groupby('step')['time_ms'].mean()
    cvm = data[data['system'] == 'cvm'].groupby('step')['time_ms'].mean()

    # Slick is a CVM that additionally runs iomgr's DPDK init; the other two
    # systems consist solely of their respective iomgr phase(s), reusing the
    # existing "Runtime"/"Invoke" step labels.
    systems = {
        'slick': [(step, t) for step, t in cvm.items()] + [('DPDK', iomgr['dpdk'])],
        'zygote': [('Runtime', iomgr['zygote'])] + [('DPDK', iomgr['dpdk'])],
        'trustlet': [('Invoke', iomgr[IOMGR_REMAINING].sum())],
    }

    extra = pd.concat([
        pd.DataFrame([
            {'system': name, 'sample': 0, 'step': step, 'time_ms': t}
            for step, t in steps
        ])
        for name, steps in systems.items()
    ], ignore_index=True)

    data = data[data['system'] != 'iomgr']
    return pd.concat([data, extra], ignore_index=True)

# Stacking order of startup phases, bottom (earliest) to top (latest).
# Phases that never co-occur in the same system are interleaved so that each
# system's bar stacks in chronological order.
STEP_ORDER = [
    'VMM (QEMU)',
    'Firmware',
    'Guest OS',
    'Other',  # was 'VMM+OVMF+OS'
    'Runtime',
    'Invoke',
]

YLABEL = 'Startup [s]'
XLABEL = 'System'

# Broken y-axis: the lower half zooms into [0, SPLIT_LOW] so the small systems
# (Gramine, Kata, ...) are readable; the upper half shows [SPLIT_HIGH, max] to
# keep the tall VM/CVM bars in view. Units are seconds.
SPLIT_LOW = 0.4
SPLIT_HIGH = 1

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
    # Kata's "Early runtime" is a runtime phase like "Runtime"; merge the two
    # to keep the legend compact (totals are preserved).
    data['step'] = data['step'].replace({
        'Early runtime': 'Runtime',
        'Firmware (OVMF)': 'Firmware',
        'OS/Guest-OS': 'Guest OS',
        'VMM+OVMF+OS': 'Other',
        'Attestation': 'Attest',
    })
    # Add the CVM-based Slick systems built from iomgr's startup phases.
    data = build_slick_systems(data)
    # Sum phases sharing a label within a sample, then average over samples
    per_sample = data.groupby(['system', 'sample', 'step'])['time_ms'].sum().reset_index()
    df = per_sample.groupby(['system', 'step'])['time_ms'].mean().reset_index()
    # Report startup durations in seconds rather than milliseconds.
    df['time_ms'] = df['time_ms'] / 1000.0

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
    ax_top.set_ylim(SPLIT_HIGH, total_max * 1.4)

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
        ncol=3, title=None, frameon=False, columnspacing=0.6,
    )
    # rotate the system labels (like network-performance.pdf) so they fit at the
    # default font size without overlapping
    for label in ax_bottom.get_xticklabels():
        label.set_rotation(30)
        label.set_horizontalalignment('right')

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
        label = f"{total:.1f}" if total >= 1 else f"{total:.2g}"
        target.annotate(label, xy=(i, total), xytext=(0, 2),
                        textcoords="offset points", ha="center", va="bottom", fontsize=7)

    ax_top.text(
        0.03, 0.95, "↓ Lower is better", # or ↓ ← ↑ →
        transform=ax_top.transAxes,
        ha="left", va="top",
        color="navy",
        weight="bold",
    )

    ax_bottom.set_xlabel("")
    ax_top.set_ylabel("")
    # use a regular axis label (default 'medium' size) centered across both panels
    ax_bottom.set_ylabel(YLABEL)
    ax_bottom.yaxis.set_label_coords(-0.23, 1.5)

    fig.tight_layout(pad=0.1)
    # widen the left margin so the y-axis label clears the tick numbers
    fig.subplots_adjust(top=0.7, hspace=0.12, left=0.23, right=0.98)
    fig.savefig(args.output.name)
    plt.close()


if __name__ == '__main__':
    main()
