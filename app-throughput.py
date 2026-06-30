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

def ns2s(ns) -> float:
    return ns / 1e9

def pps2mpps(pps) -> float:
    return pps / 1e6

def nspp2mpps(nspp) -> float:
    return pps2mpps(1 / ns2s(nspp))

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
        df = pd.DataFrame(columns=['size', 'vnf', 'msec'])

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
    for size in df['size'].unique():
        for hue in df['vnf'].unique():
            raw = df[(df['size'] == size) & (df['vnf'] == hue)]
            clean = raw[(raw['msec'] < (50*raw['msec'].median()))]
            dfs += [ clean ]
    df = pd.concat(dfs)

    df = df[df['vnf'] != 'filter']

    log("Plotting data")

    # Plot using Seaborn
    size_order = sorted(df['size'].unique(), key=lambda s: int(s))
    sns.barplot(
               data=df,
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

    mybarplot.add_hatches(data=df, x='size', y='msec', hue='vnf', ax=ax, hatch_by='vnf', hatches=hatch_map)
    mybarplot.add_colors(data=df, x='size', y='msec', hue='vnf', ax=ax, color_by='vnf', colors=color_map)
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
        vnf = hue_order[i]
        legend_patch.set_hatch(f"{hatch_map[vnf]}{hatch_map[vnf]}")
        legend_patch.set_facecolor(color_map[vnf])
    n_labels = len(ax.get_legend().get_texts())
    sns.move_legend(ax, "upper center", bbox_to_anchor=(0.5, 1.05), ncol=n_labels, title=None, frameon=False, bbox_transform=fig.transFigure)
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

    # --- Theoretical cipher throughput ceiling per packet size --------------
    # Cipher de/encryption cost [ns/packet] measured at 64B and 1500B (from
    # cypher-speed.py); linearly interpolated for the intermediate sizes.
    # Throughput ceiling [Mpps] = 1000 / ns_per_packet. Drawn as a short
    # horizontal tick over each size's bar group; values above the y-axis are
    # clamped to the top and marked with a "↑".
    CIPHER_NS = {
        "64B": {"AES-256-GCM": 70.9, "AES-256-CBC-SHA1": 132.4, "ChaCha20-Poly1305": 205.5},
        "1500B": {"AES-256-GCM": 674.8, "AES-256-CBC-SHA1": 371.5, "ChaCha20-Poly1305": 1293.5},
    }
    CIPHERS = ["AES-256-GCM", "AES-256-CBC-SHA1", "ChaCha20-Poly1305"]
    CIPHERS_MAP = {
        "AES-256-GCM": "AES-GCM",
        "AES-256-CBC-SHA1": "AES-CBC",
        "ChaCha20-Poly1305": "ChaCha20"
    }
    IPSEC_MAP = { # see *.ipsec files and take average of encrypt and decrypt: python3 ./pybench/measure_vm.py -vvv -b --system mirror --real_workload realProfiled --pktsize 64 128 256 512 1024 1500
        64:   (764+ 757)/2,
        128:  (900+ 870)/2,
        256:  (1014+ 987)/2,
        512:  (1075+ 1060)/2,
        1024: (1442+ 1437)/2,
        1500: (2001+ 2003)/2,
    }


    def cipher_throughput_mpps(cipher, size_b):
        a, b = CIPHER_NS["64B"][cipher], CIPHER_NS["1500B"][cipher]
        ns = a + (b - a) / (1500 - 64) * (size_b - 64)  # interpolate ns/packet
        return 1000.0 / ns

    half_w = 0.42                       # half the categorical bar-group width
    seg = 2 * half_w / len(CIPHERS)     # one sub-slot per cipher within a group
    max_bar = ax.get_ylim()[1]           # autoscaled top driven by the measured bars
    ax.set_ylim(top=max_bar * 1.1)      # scale to the tallest bar, not the cipher ceiling
    for i, size_label in enumerate(size_order):
        size_b = int(size_label)
        if size_b in IPSEC_MAP.keys():
            y_true = nspp2mpps(IPSEC_MAP[size_b])
            ax.hlines(y_true, i - half_w, i + half_w,
                        color="black", lw=0.5, zorder=5)
            ax.annotate("IPSec", xy=(i, y_true), xytext=(1, 1.5),
                        textcoords="offset points", ha="center", va="bottom",
                        # rotation=90,
                        fontsize=6, color="black", zorder=6)
        # for j, cipher in enumerate(CIPHERS):
        #     y_true = cipher_throughput_mpps(cipher, size_b)
        #     ax.hlines(y_true, i - half_w, i + half_w,
        #               color="black", lw=0.5, zorder=5)
        #     ax.annotate(CIPHERS_MAP[cipher], xy=(i, y_true), xytext=(1, 1.5),
        #                 textcoords="offset points", ha="center", va="bottom",
        #                 # rotation=90,
        #                 fontsize=6, color="black", zorder=6)

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
    plt.subplots_adjust(top=0.85, right=0.98)
    # fig.tight_layout(rect=(0, 0, 0.3, 1))
    plt.savefig(args.output.name)
    plt.close()





if __name__ == '__main__':
    main()
