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
from plotting import map_grid_titles
from tqdm import tqdm
import scipy.stats as scipyst
from functools import reduce
import operator
from trivial import *


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

    all_dfs = []

    # Read throughput data from file arguments
    for color in COLORS:
        if args.__dict__[color]:
            log(f"Reading files for --{color}-name")
            arg_dfs = [pd.read_csv(f.name) for f in args.__dict__[color]]
            arg_df = pd.concat(arg_dfs)
            name = args.__dict__[f'{color}_name']
            arg_df["vnf"] = name
            arg_df["size"] = arg_df["pktsize"].astype(int).astype(str)
            arg_df["msec"] = arg_df["Mpps"]
            all_dfs.append(arg_df)

    if all_dfs:
        df = pd.concat(all_dfs, ignore_index=True)
    else:
        df = pd.DataFrame(columns=['size', 'vnf', 'msec', 'real_workload'])

    # # Add synthetic Wallet baseline (same as microbenchmarks.py)
    # vnfs = ["Insecure", "Secure", "Wallet", "Naive", "Slick"]
    # sizes = sorted(df['size'].unique()) if not df.empty else ["64", "256", "1024", "1508"]
    # existing_vnfs = set(df['vnf'].unique()) if not df.empty else set()
    # wallet_rows = []
    # for size in sizes:
    #     if "Wallet" not in existing_vnfs:
    #         if size == "64":
    #             wallet_rows.append([size, "Wallet", 0.188]) # nspp2mpps(mpps2nspp(0.22) + (770ns for chacha20-poly1305))
    #         elif size == "1500":
    #             wallet_rows.append([size, "Wallet", 0.152]) # nspp2mpps(mpps2nspp(0.22) + 2002ns for chacha20-poly1305)
    #         else:
    #             ipsec_time = lambda pktsize: 770 + ((2002-770)/(1500-64) * (pktsize - 64))
    #             value = nspp2mpps(mpps2nspp(0.22) + ipsec_time(int(size)))
    #             wallet_rows.append([size, "Wallet", value])
    # if wallet_rows:
    #     df = pd.concat([df, pd.DataFrame(wallet_rows, columns=['size', 'vnf', 'msec'])], ignore_index=True)
    # vnfs += [v for v in df['vnf'].unique() if v not in vnfs]
    vnfs = df['vnf'].unique()

    # Ensure barplot ordering matches vnfs list
    hue_order = vnfs


    df['size'] = df['size'].apply(lambda row: size_map.get(str(row), row))
    df['vnf'] = df['vnf'].apply(lambda row: hue_map.get(str(row), row))

    # map colors and hatches to hues (keyed by hue_order for consistency)
    colors = sns.color_palette("pastel", len(hue_order)-1) + [ mcolors.to_rgb('sandybrown') ]
    hatch_map = {vnf: hatches[i % len(hatches)] for i, vnf in enumerate(hue_order)}
    color_map = {vnf: colors[i % len(colors)] for i, vnf in enumerate(hue_order)}
    # palette = dict(zip(df['hue'].unique(), colors))

    # Only removes outliers that are excessive (e.g. 1000ms from a median of 15ms).
    # We need this because our linux measurements sometimes break and don't detect when click is up.
    dfs = []
    for workload in df['real_workload'].unique():
        for size in df['size'].unique():
            for hue in df['vnf'].unique():
                raw = df[(df['real_workload'] == workload) & (df['size'] == size) & (df['vnf'] == hue)]
                clean = raw[(raw['msec'] < (50*raw['msec'].median()))]
                dfs += [ clean ]
    df = pd.concat(dfs)

    df = df[df['vnf'] != 'filter']

    log("Plotting data")

    # One facet row per workload type (upper: synthetic, lower: real)
    grid_title_map = {
        'real_workload = synthetic': 'No IPSec',
        'real_workload = real': 'With IPSec',
    }
    workloads = [w for w in ['synthetic', 'real'] if w in df['real_workload'].unique()]

    size_order = sorted(df['size'].unique(), key=lambda s: int(s))

    # Create FacetGrid with one row per workload type
    grid = sns.FacetGrid(df, row='real_workload', row_order=workloads,
                         height=args.height / len(workloads),
                         aspect=args.width / (args.height / len(workloads)),
                         sharex=True, sharey=False)
    if args.title:
        grid.figure.suptitle(args.title)

    for ax in grid.axes.flat:
        ax.set_axisbelow(True)
        ax.grid(True)
        ax.set_yscale('log' if args.logarithmic else 'linear')

    # Map barplot to each facet
    grid.map_dataframe(sns.barplot,
                       x='size',
                       y='msec',
                       order=size_order,
                       hue="vnf",
                       hue_order=hue_order,
                       # palette=palette,
                       palette="deep",
                       saturation=1,
                       edgecolor="dimgray",
                       )

    # materialize tick labels on all (shared) axes so that mybarplot can
    # look up x categories via ax.get_xticklabels()
    grid.figure.canvas.draw()

    # apply custom hatches and colors per facet
    for (row_i, col_j, hue_k), facet_df in grid.facet_data():
        ax = grid.facet_axis(row_i, col_j)
        mybarplot.add_hatches(data=facet_df, x='size', y='msec', hue='vnf', ax=ax, hatch_by='vnf', hatches=hatch_map)
        mybarplot.add_colors(data=facet_df, x='size', y='msec', hue='vnf', ax=ax, color_by='vnf', colors=color_map)

    for ax in grid.axes.flat:
        if not args.logarithmic:
            ax.set_ylim(bottom=0)
        else:
            ax.set_ylim(bottom=1)

    map_grid_titles(grid, grid_title_map)
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
    # Add a single legend to the grid
    grid.add_legend(title=None, frameon=False)

    # Fix the legend hatches
    legend = grid._legend
    for legend_patch, legend_text in zip(legend.get_patches(), legend.get_texts()):
        vnf = legend_text.get_text()
        legend_patch.set_hatch(f"{hatch_map[vnf]}{hatch_map[vnf]}")
        legend_patch.set_facecolor(color_map[vnf])
    n_labels = len(legend.get_texts())
    sns.move_legend(grid, "lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, title=None, frameon=False)
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
    grid.axes.flat[-1].annotate(
        "↑ Higher is better", # or ↓ ← ↑ →
        xycoords="axes points",
        # xy=(0, 0),
        xy=(0, 0),
        xytext=(-40, -27),
        # fontsize=FONT_SIZE,
        color="navy",
        weight="bold",
    )

    grid.set_axis_labels(XLABEL, YLABEL)
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
    grid.figure.set_size_inches(args.width, args.height)
    grid.figure.tight_layout(pad=0.1)
    grid.figure.subplots_adjust(hspace=0.4) # spacing between grid rows
    # fig.tight_layout(rect=(0, 0, 0.3, 1))
    grid.savefig(args.output.name)
    plt.close()





if __name__ == '__main__':
    main()
