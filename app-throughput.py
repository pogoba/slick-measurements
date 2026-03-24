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
from plotting import HATCHES as hatches
from plotting import mybarplot
from tqdm import tqdm
import scipy.stats as scipyst
from functools import reduce
import operator


PLOTTING_NAME="foobar"
DEFAULT_OUTPUT=f"{PLOTTING_NAME}.pdf"

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

size_map = {
        # 'ebpf-click-unikraftvm': 'Unikraft click (eBPF)',
        # 'click-unikraftvm': 'Unikraft click',
        # 'click-linuxvm': 'Linux click',
        'linux': 'Linux/Click',
        'ukebpfjit': 'MorphOS',
        'uk': 'Unikraft/Click',
        }

hue_map = {
    'firewall-10000': 'Firewall-10k',
    'firewall-1000': 'Firewall-1k',
    'firewall-2': 'Firewall-2',
    'empty': 'Empty',
    'ids': 'IDS',
    'nat': 'NAT',
    'mirror': 'Mirror'
}

YLABEL = 'Throughput [Mpps]'
XLABEL = 'Packet size [B]'

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
                        help='Use other setting to plot for presentation slides',
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
    plt.grid()
    # plt.xlim(0, 0.83)
    log_scale = (False, True) if args.logarithmic else False
    ax.set_yscale('log' if args.logarithmic else 'linear')

    # dfs = []
    # for color in COLORS:
    #     if args.__dict__[color]:
    #         log(f"Reading files for --name-{color}")
    #         arg_dfs = [ pd.read_csv(f.name) for f in tqdm(args.__dict__[color]) ]
    #         arg_df = pd.concat(arg_dfs)
    #         name = args.__dict__[f'{color}_name']
    #         arg_df["arglabel"] = name
    #         dfs += [ arg_df ]
    #         # throughput = ThroughputDatapoint(
    #         #     moongen_log_filepaths=[f.name for f in args.__dict__[color]],
    #         #     name=args.__dict__[f'{color}_name'],
    #         #     color=color,
    #         # )
    #         # dfs += color_dfs
    # df = pd.concat(dfs, ignore_index=True)

    log("Preparing plotting data")


    columns = ['size', 'vnf', 'msec']
    sizes = [ "64", "256", "1024", "1508" ]
    vnfs = [ "Native", "LibOS (Gramine)", "Containers (Kata)", "VM (KVM-Linux)", "CVM (SEV-SNP)", "Wallet", "Slick" ]
    rows = []
    for size in sizes:
        for vnf in vnfs:
            value = 1
            if vnf == "Wallet":
                value = 0.5
            if vnf == "Slick":
                value = 2
            rows += [[size, vnf, value]]
    df = pd.DataFrame(rows, columns=columns)


    df['size'] = df['size'].apply(lambda row: size_map.get(str(row), row))
    df['vnf'] = df['vnf'].apply(lambda row: hue_map.get(str(row), row))

    # map colors to hues
    colors = sns.color_palette("pastel", len(df['vnf'].unique())-1) + [ mcolors.to_rgb('sandybrown') ]
    # palette = dict(zip(df['hue'].unique(), colors))

    # Only removes outliers that are excessive (e.g. 1000ms from a median of 15ms).
    # We need this because our linux measurements sometimes break and don't detect when click is up.
    dfs = []
    for size in df['size'].unique():
        for hue in df['vnf'].unique():
            raw = df[(df['size'] == size) & (df['vnf'] == hue)]
            clean = raw[(raw['msec'] < (50*raw['msec'].median()))]
            dfs += [ clean ]
    df = pd.concat(dfs)

    df = df[df['vnf'] != 'filter']

    log("Plotting data")

    # Plot using Seaborn
    sns.barplot(
               data=df,
               x='size',
               y='msec',
               hue="vnf",
               # palette=palette,
               palette="deep",
               saturation=1,
               edgecolor="dimgray",
               )

    mybarplot.add_hatches(data=df, x='size', y='msec', hue='vnf', ax=ax, hatch_by='vnf', hatches=hatches)
    mybarplot.add_colors(data=df, x='size', y='msec', hue='vnf', ax=ax, color_by='vnf', colors=colors)
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
    # Fix the legend hatches
    for i, legend_patch in enumerate(ax.get_legend().get_patches()):
        hatch = hatches[i % len(hatches)]
        color = colors[i % len(colors)]
        legend_patch.set_hatch(f"{hatch}{hatch}")
        legend_patch.set_facecolor(color)
    sns.move_legend(
        ax, "upper right",
        title="VNF",
        # bbox_to_anchor=(.5, 1), ncol=3, title=None, frameon=False,
    )
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
    plt.annotate(
        "↑ Higher is better", # or ↓ ← ↑ →
        xycoords="axes points",
        # xy=(0, 0),
        xy=(0, 0),
        xytext=(-40, -27),
        # fontsize=FONT_SIZE,
        color="navy",
        weight="bold",
    )

    plt.xlabel(XLABEL)
    plt.ylabel(YLABEL)

    # plt.ylim(0, 350)
    if not args.logarithmic:
        plt.ylim(bottom=0)
    else:
        plt.ylim(bottom=1)
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
    plt.tight_layout(pad=0.5)
    # plt.subplots_adjust(right=0.78)
    # fig.tight_layout(rect=(0, 0, 0.3, 1))
    plt.savefig(args.output.name)
    plt.close()





if __name__ == '__main__':
    main()
