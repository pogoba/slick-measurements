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

PLOTTING_NAME="cypher-speed"
DEFAULT_OUTPUT=f"{PLOTTING_NAME}.pdf"

hatches = _hatches.copy()
hatches[0] = _hatches[6]
hatches[6] = _hatches[2]
hatches[2] = _hatches[0]

# Cipher de/encryption cost per packet [ns], measured for two packet sizes.
CIPHERS = ["AES-256-GCM", "AES-256-CBC-SHA1", "ChaCha20-Poly1305"]
CIPHER_NS = {
    "64B": {
        "AES-256-GCM": 70.9,
        "AES-256-CBC-SHA1": 132.4,
        "ChaCha20-Poly1305": 205.5,
    },
    "1500B": {
        "AES-256-GCM": 674.8,
        "AES-256-CBC-SHA1": 371.5,
        "ChaCha20-Poly1305": 1293.5,
    },
}

# Per-packet time budgets [ns] to sustain line rate, drawn as horizontal lines.
BUDGETS = {
    "64B": {"10 Gbit/s": 67.2, "100 Gbit/s": 6.7},
    "1500B": {"10 Gbit/s": 1216.0, "100 Gbit/s": 121.6},
}

PACKET_SIZES = ["64B", "1500B"]

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

YLABEL = 'De/encryption [ns]'
XLABEL = 'Cipher'

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
    # Build a tidy frame: one row per (packet size, cipher).
    rows = []
    for size in PACKET_SIZES:
        for cipher in CIPHERS:
            rows.append([size, cipher, CIPHER_NS[size][cipher]])
    df = pd.DataFrame(rows, columns=['size', 'cipher', 'nsec'])
    df['cipher'] = pd.Categorical(df['cipher'], CIPHERS)

    log("Preparing plotting data")
    # Two stacked panels (one per packet size) with horizontal bars. The
    # value axes differ by an order of magnitude, so they are NOT shared.
    fig, axes = plt.subplots(
        len(PACKET_SIZES), 1, sharex=False,
        figsize=(args.width, args.height),
    )
    if args.title:
        fig.suptitle(args.title)

    # one stable color/hatch per cipher across both panels
    palette = dict(zip(CIPHERS, sns.color_palette("deep", len(CIPHERS))))
    cipher_hatch = {cipher: hatches[i % len(hatches)]
                    for i, cipher in enumerate(CIPHERS)}
    # line styles for the budget annotations, shared across panels
    budget_styles = {"10 Gbit/s": "--", "100 Gbit/s": ":"}

    for ax, size in zip(axes, PACKET_SIZES):
        sub = df[df['size'] == size]
        ax.set_axisbelow(True)
        if not args.slides:
            ax.grid(axis='x')

        sns.barplot(
            data=sub,
            y='cipher',
            x='nsec',
            order=CIPHERS,
            hue='cipher',
            hue_order=CIPHERS,
            palette=palette,
            edgecolor="dimgray",
            legend=False,
            ax=ax,
        )
        for bar, cipher in zip(ax.patches, CIPHERS):
            bar.set_hatch(cipher_hatch[cipher])

        ax.set_ylabel("")
        ax.set_xlabel(f"{size} {YLABEL}")
        # headroom right of the longest of bars and budget lines
        right = max(sub['nsec'].max(), max(BUDGETS[size].values()))
        ax.set_xlim(0, right * 1.12)

        # Budget lines as vertical annotations. Place the label on the side of
        # the line with more room so it never runs off the panel.
        for label, value in BUDGETS[size].items():
            ax.axvline(value, color='darkblue',
                       linestyle=budget_styles.get(label, '-'),
                       linewidth=1.2, zorder=3)
            on_right = value > 0.65 * right
            ha = 'right' if on_right else 'left'
            dx = -3 if on_right else 3
            # nudge the 100 Gbit/s label slightly left to clear the 10 Gbit/s one
            if label == "100 Gbit/s":
                dx -= 4
            ax.annotate(
                label,
                xy=(value, 1.0), xycoords=('data', 'axes fraction'),
                xytext=(dx, 2), textcoords='offset points',
                ha=ha,
                va='bottom', fontsize='x-small', color='black',
            )

    axes[-1].annotate(
        "← Lower is better",
        xycoords="axes points",
        xy=(0, 0),
        xytext=(-104, -28),
        color="navy",
        weight="bold",
    )

    fig.tight_layout(pad=0.4)
    fig.subplots_adjust(hspace=1.0)
    fig.savefig(args.output.name)
    plt.close()





if __name__ == '__main__':
    main()
