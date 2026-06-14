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

YLABEL = 'Comm. time [us]'
XLABEL = ''

# time spent in the VNFlet network stack (hardcoded for now)
VNFLET_STACK_SHARE = 0.3
# extra stub driver share, only added to mirrorMicrobenchmark bars (hardcoded for now)
STUB_DRIVER_SHARE = 0.5
STUB_DRIVER_SYSTEM = 'mirrorMicrobenchmark'

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

    fig = plt.figure(figsize=(args.width, args.height))
    # fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    # ax.set_axisbelow(True)
    if args.title:
        plt.title(args.title)
    if not args.slides:
        plt.grid()
    # plt.xlim(0, 0.83)
    log_scale = (False, True) if args.logarithmic else False
    ax.set_yscale('log' if args.logarithmic else 'linear')

    log("Preparing plotting data")

    # Read measurement logs from file arguments. The --N order has no impact;
    # the system display name is taken from --N-name. Bars are derived from the
    # display name plus the data (pktsize, batchsize).
    all_dfs = []
    name_order = []
    for color in COLORS:
        if args.__dict__[color]:
            log(f"Reading files for --{color}")
            arg_df = pd.concat([pd.read_csv(f.name) for f in args.__dict__[color]], ignore_index=True)
            name = args.__dict__[f'{color}_name']
            arg_df['sysname'] = name
            if name not in name_order:
                name_order += [ name ]
            all_dfs += [ arg_df ]
    raw_df = pd.concat(all_dfs, ignore_index=True)
    raw_df = raw_df[raw_df['Mpps'] > 0]

    # convert packet rate into communication time per packet (1/rate)
    raw_df['nspp'] = 1.0 / raw_df['Mpps'] # Mpps -> ns per packet

    # one bar per (display name, pktsize, batchsize); each bar is stacked into
    # the VNFlet network stack share and the remainder. mirrorMicrobenchmark
    # bars get an additional stub driver segment on top.
    Contributors = [ "Stub driver", "VNFlet network stack", "Other" ]
    rows = []
    bar_order = []
    grouped = raw_df.groupby(['sysname', 'pktsize', 'batchsize'])
    nspp_mean = grouped['nspp'].mean()
    systems = grouped['system'].agg(lambda s: set(s))
    combos = sorted(nspp_mean.index, key=lambda c: (name_order.index(c[0]), int(c[1]), int(c[2])))
    for combo in combos:
        sysname, pktsize, batchsize = combo
        nspp = nspp_mean[combo]
        bar = f"{sysname}\n{pktsize}B" # \nb{batchsize}"
        bar_order += [ bar ]
        # carve named segments out of the measured time; "Other" is the remainder
        # so that the stacked bar height stays the measured communication time.
        other = nspp
        # vnflet = nspp * VNFLET_STACK_SHARE
        vnflet = VNFLET_STACK_SHARE
        other -= vnflet
        rows.append([bar, 'VNFlet network stack', vnflet])
        if STUB_DRIVER_SYSTEM in systems[combo]:
            stub = nspp * STUB_DRIVER_SHARE
            # stub = STUB_DRIVER_SHARE
            other -= stub
            rows.append([bar, 'Stub driver', stub])
        rows.append([bar, 'Other', other])

    df = pd.DataFrame(rows, columns=['system', 'Contributor', 'restart_s'])

    # Set categorical order for bars
    df['system'] = pd.Categorical(df['system'], bar_order)
    # Plot using Seaborn
    sns.histplot(
               data=df,
               x='system',
               weights='restart_s',
               hue="Contributor",
               hue_order = Contributors,
               multiple="stack",
               # palette=palette,
               palette="deep",
               edgecolor="dimgray",
               shrink=0.8,
               )

    # sns.add_legend(
    #         # bbox_to_anchor=(0.5, 0.77),
    #         loc='right',
    #         ncol=1, title=None, frameon=False,
    #                 )

    # # Fix the legend hatches
    # for i, legend_patch in enumerate(grid._legend.get_patches()):
    #     hatch = hatches[i % len(hatches)]
    #     legend_patch.set_hatch(f"{hatch}{hatch}")

    # # add hatches to bars
    # for (i, j, k), data in grid.facet_data():
    #     print(i, j, k)
    #     def barplot_add_hatches(plot_in_grid, nr_hues, offset=0):
    #         hatches_used = -1
    #         bars_hatched = 0
    #         for bar in plot_in_grid.patches:
    #             if nr_hues <= 1:
    #                 hatches_used += 1
    #             else: # with multiple hues, we draw bars with the same hatch in batches
    #                 if bars_hatched % nr_hues == 0:
    #                     hatches_used += 1
    #             # if bars_hatched % 7 == 0:
    #             #     hatches_used += 1
    #             bars_hatched += 1
    #             if bar.get_bbox().x0 == 0 and bar.get_bbox().x1 == 0 and bar.get_bbox().y0 == 0 and bar.get_bbox().y1 == 0:
    #                 # skip bars that are not rendered
    #                 continue
    #             hatch = hatches[(offset + hatches_used) % len(hatches)]
    #             print(bar, hatches_used, hatch)
    #             bar.set_hatch(hatch)
    #
    #     if (i, j, k) == (0, 0, 0):
    #         barplot_add_hatches(grid.facet_axis(i, j), 7)
    #     elif (i, j, k) == (0, 1, 0):
    #         barplot_add_hatches(grid.facet_axis(i, j), 1, offset=(7 if not args.slides else 4))

    # def grid_set_titles(grid, titles):
    #     for ax, title in zip(grid.axes.flat, titles):
    #         ax.set_title(title)
    #
    # grid_set_titles(grid, ["Emulation and Mediation", "Passthrough"])
    #
    # grid.figure.set_size_inches(args.width, args.height)
    # grid.set_titles("foobar")
    # plt.subplots_adjust(left=0.06)
    # bar = sns.barplot(x='num_vms', y='rxMppsCalc', hue="hue", data=pd.concat(dfs),
    #             palette='colorblind',
    #             edgecolor='dimgray',
    #             # kind='bar',
    #             # capsize=.05,  # errorbar='sd'
    #             # log_scale=log_scale,
    #             ax=ax,
    #             )
    sns.move_legend(
        ax, "lower center",
        bbox_to_anchor=(.5, 1.02), ncol=3, title=None, frameon=False,
    )

    color_hatch_map = dict()
    # Fix the legend hatches
    for i, legend_patch in enumerate(ax.get_legend().get_patches()):
        hatch = hatches[i % len(hatches)]
        legend_patch.set_hatch(f"{hatch}{hatch}")
        color_hatch_map[legend_patch.get_facecolor()] = hatch
        print(f"legend {hatch}")

    for bar in ax.patches:
        hatch = color_hatch_map[bar.get_facecolor()]
        bar.set_hatch(hatch)
    #
    # sns.move_legend(
    #     grid, "lower center",
    #     bbox_to_anchor=(0.45, 1),
    #     ncol=1,
    #     title=None,
    #     # frameon=False,
    # )
    # grid.set_xlabels(XLABEL)
    # grid.set_ylabels(YLABEL)
    #
    ax.annotate(
        "↓ Lower\nis better", # or ↓ ← ↑ →
        xycoords="axes points",
        # xy=(0, 0),
        xy=(0, 0),
        xytext=(-30, -28),
        # fontsize=FONT_SIZE,
        color="navy",
        weight="bold",
    )

    plt.xlabel(XLABEL)
    plt.ylabel(YLABEL)

    # plt.ylim(0, 250)
    if not args.logarithmic:
        plt.ylim(bottom=0)
    # for container in ax.containers:
    #     ax.bar_label(container, fmt='%.0f')

    # # iterate through each container, hatch, and legend handle
    # for container, hatch, handle in zip(ax.containers, hatches, ax.get_legend().legend_handles[::-1]):
    #     # update the hatching in the legend handle
    #     handle.set_hatch(hatch)
    #     # iterate through each rectangle in the container
    #     for rectangle in container:
    #         # set the rectangle hatch
    #         rectangle.set_hatch(hatch)

    # # Loop over the bars
    # for i,thisbar in enumerate(bar.patches):
    #     # Set a different hatch for each bar
    #     thisbar.set_hatch(hatches[i % len(hatches)])

    # legend = plt.legend()
    # legend.get_frame().set_facecolor('white')
    # legend.get_frame().set_alpha(0.8)
    # fig.tight_layout(rect = (0, 0, 0, 0.1))
    # ax.set_position((0.1, 0.1, 0.5, 0.8))
    plt.tight_layout(pad=0.1)
    plt.subplots_adjust(top=0.85)
    plt.savefig(args.output.name)
    plt.close()





if __name__ == '__main__':
    main()
