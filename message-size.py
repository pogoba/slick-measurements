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

PLOTTING_NAME="message-size"
DEFAULT_OUTPUT=f"{PLOTTING_NAME}.pdf"

COLORS = [ str(i) for i in range(20) ]
COLOR_MAP = {
        1: 'blue',
        2: 'red',
        3: 'green',
        4: 'cyan',
        5: 'violet',
        6: 'magenta',
        7: 'orange',
        8: 'brown',
        9: 'yellow',
        }
# COLORS = mcolors.CSS4_COLORS.keys()
LINES = {
    '1': '-',
    '2': '-.',
    '3': ':',
    '4': ':',
    '5': ':',
    '6': '--',
    '7': '--',
    '8': '-',
    '9': '--',
    }
# COLORS = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w']

LEGEND_MAP = {
    "linux": "Linux",
    "uk": "Unikraft",
    "ukebpfjit": "UniBPF",
    "ukebpf": "UniBPF no JIT",
}

system_map = {
        'ebpf-click-unikraftvm': 'Uk click (eBPF)',
        'click-unikraftvm': 'Uk click',
        'click-linuxvm': 'Linux click',
        'ukebpfjit': 'MorphOS + MPK',
        'ukebpfjit_nompk': 'MorphOS',
        'linux': 'Linux',
        'uk': 'Unikraft',
        'Max IO bandwidth': 'Link speed (10G)'
        }

grid_title_map = {
    'plot_type = throughput': 'Throughput',
    'plot_type = latency': 'Latency',
}

# Set global font size
# plt.rcParams['font.size'] = 10  # Sets the global font size to 14
# plt.rcParams['axes.labelsize'] = 10  # Sets axis label size
# plt.rcParams['xtick.labelsize'] = 8  # Sets x-tick label size
# plt.rcParams['ytick.labelsize'] = 8  # Sets y-tick label size
# plt.rcParams['legend.fontsize'] = 8  # Sets legend font size
# plt.rcParams['axes.titlesize'] = 16  # Sets title font size

class FirewallPlot(object):
    _df = None
    _name = None
    _color = None
    _line = None
    _line_color = None
    _plot = None

    def __init__(self, histogram_filepaths, name, color, line, line_color):
        self._name = name
        self._color = color
        self._line = line
        self._line_color = line_color

        dfs = []
        for filepath in histogram_filepaths:
            if getsize(filepath) > 0:
                dfs += [ pd.read_csv(filepath) ]
        df = pd.concat(dfs)

        df['pps'] = df['pps'].apply(lambda pps: pps / 1_000_000) # now mpps

        self._df = df

    def plot(self):
        self._plot = sns.lineplot(
            data=self._df,
            # x=bin_edges[1:],
            # y=cdf,
            x = "fw_size",
            y = "pps",
            label=f'{self._name}',
            color=self._line_color,
            linestyle=self._line,
            # linewidth=1,
            markers=True,
            # markers=[ 'X' ],
            # markeredgecolor='black',
            # markersize=60,
            # markeredgewidth=1,

        )


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
                        help='Plot logarithmic latency axis',
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
                            help=f'''Paths to latency histogram CSVs for
                                  {color} plot''',
                            )
    for color in COLORS:
        parser.add_argument(f'--{color}-name',
                            type=str,
                            default=color,
                            nargs='+',
                            help=f'''Name of {color} plot''',
                            )
    for color in COLORS:
        parser.add_argument(f'--lat-{color}',
                            type=argparse.FileType('r'),
                            nargs='+',
                            help=f'''Paths to latency CSVs for {color} plot''',
                            )
    for color in COLORS:
        parser.add_argument(f'--lat-{color}-name',
                            type=str,
                            default=color,
                            nargs='+',
                            help=f'''Name of latency {color} plot''',
                            )
    # for color in COLORS:
    #     parser.add_argument(f'--{color}-line',
    #                         type=str,
    #                         default="-",
    #                         help=f'''Line style of {color} plot''',
    #                         )
    # for color in COLORS:
    #     parser.add_argument(f'--{color}-color',
    #                         type=str,
    #                         default="blue",
    #                         help=f'''Color of {color} plot''',
    #                         )

    return parser


def parse_args(parser):
    args = parser.parse_args()

    lat_keys = [f"lat_{color}" for color in COLORS]
    if not any([args.__dict__[color] for color in COLORS]) and \
       not any([args.__dict__[k] for k in lat_keys]):
        parser.error('At least one set of data paths must be provided')

    return args


def chain(lst: list[list]) -> list:
    return [item for sublist in lst for item in sublist]

def mpps_to_gbitps(mpps, size):
    return mpps * (size + 20) * 8 / 1000 # 20: preamble + packet gap


# IPC network communication data (extracted from IPC_log.pdf)
MESSAGE_SIZES = ["64B", "256B", "1KB", "8KB", "16KB", "64KB", "256KB", "1MB"]
MESSAGE_SIZES_BYTES = [64, 256, 1024, 8192, 16384, 65536, 262144, 1048576]


def compute_override_times(filepaths):
    """Compute communication times for a system from measured Mpps logs.

    Each input log reports Mpps for a single packet size; the communication
    time is taken as 1/Mpps. Message sizes larger than the biggest one we
    actually measured are extrapolated by assuming we have to send multiple
    copies of the largest measured packet (e.g. 16KB time = 16 * 1KB time).
    """
    times_by_pktsize = {}
    for fh in filepaths:
        df = pd.read_csv(fh.name)
        pktsize = int(df["pktsize"].iloc[0])
        # 1/Mpps is microseconds per message; /1000 -> milliseconds
        times_by_pktsize[pktsize] = (1.0 / df["Mpps"].mean()) / 1000

    # largest message size for which we have a direct measurement; bigger
    # message sizes are extrapolated as multiples of this one's time
    measured = [b for b in MESSAGE_SIZES_BYTES if b in times_by_pktsize]
    base_b = max(measured)
    base_time = times_by_pktsize[base_b]

    result = {}
    for size, size_b in zip(MESSAGE_SIZES, MESSAGE_SIZES_BYTES):
        if size_b in times_by_pktsize:
            result[size] = times_by_pktsize[size_b]
        else:
            result[size] = (size_b / base_b) * base_time
    return result


def main():
    parser = setup_parser()
    args = parser.parse_args()

    IPC_DATA = {
        # "Native":           [0.14,  0.12,  0.13,  0.16,  0.19,  0.25,  0.25,  0.26],
        # "LibOS (Gramine)":  [0.09,  0.085, 0.085, 0.11,  0.13,  0.35,  1.3,   7.0],
        # "Containers (Kata)":[0.6,   0.58,  0.65,  0.65,  0.7,   1.5,   3.0,   8.0],
        # "VM (KVM-Linux)":   [3.7,   3.6,   3.5,   3.6,   4.2,   5.0,   8.5,   14.0],
        # "CVM (SEV-SNP)":    [4.5,   4.3,   4.2,   4.5,   4.8,   5.5,   9.0,   16.0],
        # "Wallet":           [0.22,  0.20,  0.25,  0.27,  0.38,  0.40,  1.8,   6.0],
    }

    # Any system whose data files are passed via --<color> overrides the
    # hardcoded values for the system named via --<color>-name.
    overrides = {}
    for color in COLORS:
        files = args.__dict__.get(color)
        if not files:
            continue
        name = args.__dict__.get(f"{color}_name", color)
        if isinstance(name, list):
            name = " ".join(name)
        overrides[name] = compute_override_times(files)

    rows = []
    for system, times in IPC_DATA.items():
        if system in overrides:
            continue
        for size, time_ms in zip(MESSAGE_SIZES, times):
            rows.append({"system": system, "message_size": size, "time_ms": time_ms})
    # if "Slick" not in overrides:
    #     for size, size_b in zip(MESSAGE_SIZES, MESSAGE_SIZES_BYTES):
    #         if size == "64B":
    #             gbit = 4.1
    #             message_ps = gbit * 1024 * 1024 * 1024 / 8 / 64
    #             time_ms = 1000 / message_ps
    #             time_ms += 0.009 # latency
    #         else:
    #             gbit = 37.7
    #             message_ps = gbit * 1024 * 1024 * 1024 / 8 / size_b
    #             time_ms = 1000 / message_ps
    #             time_ms += 0.016 # latency
    #         rows.append({"system": "Slick", "message_size": size, "time_ms": time_ms})
    for name, times in overrides.items():
        for size in MESSAGE_SIZES:
            rows.append({"system": name, "message_size": size, "time_ms": times[size]})
    df = pd.DataFrame(rows)
    df["message_size"] = pd.Categorical(df["message_size"], categories=MESSAGE_SIZES, ordered=True)

    systems = list(dict.fromkeys(df["system"]))

    fig, ax = plt.subplots(figsize=(args.width, args.height))

    ax.set_axisbelow(True)
    ax.grid(True)

    sns.lineplot(
        data=df,
        x="message_size",
        y="time_ms",
        hue="system",
        hue_order=systems,
        style="system",
        style_order=systems,
        markers=True,
        errorbar='ci',
        ax=ax,
    )

    ax.set_yscale('log')

    def rename_legend_labels(ax, label_map):
        if ax.get_legend() is not None:
            for i, text in enumerate(ax.get_legend().get_texts()):
                if text.get_text() in label_map:
                    text.set_text(label_map[text.get_text()])

    rename_legend_labels(ax, LEGEND_MAP)

    # Position the legend outside the plot area
    sns.move_legend(ax, "upper center", bbox_to_anchor=(0.4, 1.6),
                    ncol=2, title=None, frameon=False)

    # if args.compress:
    #     # empty  name1 name2 ...
    #     # 25pctl x     x     ...
    #     # 50pctl x     x     ...
    #     # 75pctl x     x     ...
    #     # 99pctl x     x     ...
    #     dummy, = plt.plot([0], marker='None', linestyle='None',
    #                      label='dummy')
    #     legend = plt.legend(
    #         chain([
    #             [dummy, p._plot25, p._plot50, p._plot75, p._plot99]
    #             for p in plots
    #         ]),
    #         chain([
    #             [p._name, '25.pctl', '50.pctl', '75.pctl', '99.pctl']
    #             for p in plots
    #         ]),
    #         ncol=len(plots),
    #         prop={'size': 8},
    #         loc="lower right",
    #     )
    # else:
    #     legend = plt.legend(loc="lower right", bbox_to_anchor=(1.15, 1),
    #                         ncol=3, title=None, frameon=False,
    #                         )

    ax.annotate(
        "↓ Lower is better", # or ↓ ← ↑ →
        xycoords="axes points",
        xy=(10, 0),
        xytext=(-45, -27),
        color="navy",
        weight="bold",
    )

    for i, label in enumerate(ax.get_xticklabels()):
        if i % 2 != 0:
            label.set_visible(False)

    ax.set_xlabel('Message size')
    ax.set_ylabel('Time (ms)')

    # Adjust layout and save
    fig.tight_layout(pad=0.01)
    fig.subplots_adjust(top=0.7)
    fig.savefig(args.output.name)
    plt.close()


if __name__ == '__main__':
    main()

