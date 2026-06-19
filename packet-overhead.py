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

PLOTTING_NAME="microbenchmarks"
DEFAULT_OUTPUT=f"{PLOTTING_NAME}.pdf"

hatches = _hatches.copy()
hatches[0] = _hatches[6]
hatches[6] = _hatches[2]
hatches[2] = _hatches[0]

COLORS = [ str(i) for i in range(20) ]
# COLORS = mcolors.CSS4_COLORS.keys()
# COLORS = [
#     'blue',
#     'cyan',
#     'green',
#     'yellow',
#     'orange',
#     'red',
#     'magenta',
# ]

# hue_map = {
#     '9_vmux-dpdk-e810_hardware': 'vmux-emu (w/ rte_flow)',
#     '9_vmux-med_hardware': 'vmux-med (w/ rte_flow)',
#     '9_vmux-dpdk-e810_software': 'vmux-emu',
#     '9_vmux-med_software': 'vmux-med',
#     '1_vfio_software': 'qemu-pt',
#     '1_vmux-pt_software': 'vmux-pt',
#     '1_vmux-pt_hardware': 'vmux-pt (w/ rte_flow)',
#     '1_vfio_hardware': 'qemu-pt (w/ rte_flow)',
# }

system_map = {
        'ebpf-click-unikraftvm': 'UniBPF',
        'click-unikraftvm': 'Unikraft/Click',
        'click-linuxvm': 'Linux/Click',
        'ebpf-unikraftvm': 'MorphOS',
        'ebpf-linuxvm': 'XDP',
        }

YLABEL = 'Processing time [ns]'
XLABEL = 'System'

# Broken y-axis: the lower half zooms into [0, SPLIT] so the smaller
# contributors (and the batched bars) are readable; the upper half shows
# [SPLIT, max] so the tall VM-exit segment stays in view.
SPLIT = 1300

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
                        help='Plot logarithmic latency axis',
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
                            help=f'''Paths to MoonGen measurement logs for
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
        parser.error('At least one set of moongen log paths must be ' +
                     'provided')

    return args

# hatches = ['/', '\\', '|', '-', '+', 'x', 'o', 'O']
hatches_used = 0

# Define a custom function to add hatches to the bar plots
def barplot_with_hatches(*args, **kwargs):
    global hatches_used
    sns.barplot(*args, **kwargs)
    for i, bar in enumerate(plt.gca().patches):
        hatch = hatches[hatches_used % len(hatches)]
        print(hatch)
        bar.set_hatch(hatch)
        hatches_used += 1


def main():
    parser = setup_parser()
    args = parse_args(parser)

    log("Using hardcoded data")
    # Hardcoded data to replace parse_data(df) and CSV reading
    rows = []
    # Data for each system and contributor (in nanoseconds)

    # VMs
    rows.append(['VMs', 'VM exit', 4000])
    rows.append(['VMs', 'De/encryption', 0])  # Not applicable for VMs
    rows.append(['VMs', 'Bounce buffer', 0])  # Not applicable for VMs
    rows.append(['VMs', 'Memory copy', 207])
    rows.append(['VMs', 'Other', 220])

    # CVMs
    rows.append(['CVMs', 'VM exit', 4000])
    rows.append(['CVMs', 'De/encryption', 623 ])
    rows.append(['CVMs', 'Bounce buffer', 207])
    rows.append(['CVMs', 'Memory copy', 207])
    rows.append(['CVMs', 'Other', 220])

    # VMs \n(batched)
    rows.append(['VMs (batched)', 'VM exit', 4000 / 32])
    rows.append(['VMs (batched)', 'De/encryption', 0])  # Not applicable for VMs
    rows.append(['VMs (batched)', 'Bounce buffer', 0])  # Not applicable for VMs
    rows.append(['VMs (batched)', 'Memory copy', 207])
    rows.append(['VMs (batched)', 'Other', 220 / 32])

    # CVMs \n(batched)
    rows.append(['CVMs (batched)', 'VM exit', 4000 / 32])
    rows.append(['CVMs (batched)', 'De/encryption', 623 ])
    rows.append(['CVMs (batched)', 'Bounce buffer', 207])
    rows.append(['CVMs (batched)', 'Memory copy', 207])
    rows.append(['CVMs (batched)', 'Other', 220 / 32])

    data = pd.DataFrame(rows, columns=['system', 'label', 'nsec'])

    log("Preparing plotting data")
    Contributors = [ "VM exit", "De/encryption", "Bounce buffer", "Memory copy", "Other" ]
    data = data[data['label'].isin(Contributors)]
    data['Contributor'] = data['label']
    data['restart_s'] = data['nsec']
    data = data[['system', 'Contributor', 'restart_s']]
    df = data.groupby(['system', 'Contributor'])['restart_s'].mean().reset_index()
    # df['restart_s'] = df['restart_s']/1000000

    # Set categorical order for systems
    df['system'] = pd.Categorical(df['system'], ['VMs', 'CVMs', 'VMs (batched)', 'CVMs (batched)'])
    # Rename VMs to vms
    df['system'] = df['system'].cat.rename_categories({'VMs (batched)': 'VMs\n(batched) ', 'CVMs (batched)': 'CVMs\n (batched)'})
    # Broken y-axis: stack the same plot on two axes and zoom each differently.
    fig, (ax_top, ax_bottom) = plt.subplots(
        2, 1, sharex=True, figsize=(args.width, args.height),
        gridspec_kw={'height_ratios': [1, 1]},
    )
    if args.title:
        ax_top.set_title(args.title)

    hue_order = ['VM exit', 'De/encryption', 'Bounce buffer', 'Memory copy', 'Other']
    for ax in (ax_top, ax_bottom):
        ax.set_axisbelow(True)
        if not args.slides:
            ax.grid()
        sns.histplot(
                   data=df,
                   x='system',
                   weights='restart_s',
                   hue="Contributor",
                   hue_order=hue_order,
                   multiple="stack",
                   palette="deep",
                   edgecolor="dimgray",
                   shrink=0.8,
                   legend=(ax is ax_top),
                   ax=ax,
                   )

    # lower half zooms in, upper half shows the bar tops
    total_max = df.groupby('system', observed=True)['restart_s'].sum().max()
    ax_bottom.set_ylim(0, SPLIT)
    ax_top.set_ylim(SPLIT, total_max * 1.05)

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
        ncol=2, title=None, frameon=False,
    )

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
    # use a regular axis label (default 'medium' size) centered across both panels
    ax_bottom.set_ylabel(YLABEL)
    ax_bottom.yaxis.set_label_coords(-0.18, 1.0)

    fig.tight_layout(pad=0.1)
    fig.subplots_adjust(top=0.7, hspace=0.12, left=0.2)
    fig.savefig(args.output.name)
    plt.close()





if __name__ == '__main__':
    main()
