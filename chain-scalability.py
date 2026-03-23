#!/usr/bin/env python3
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import seaborn as sns
import argparse
from re import search
from os.path import basename, getsize
import pandas as pd
from plotting import map_grid_titles
import os

PLOTTING_NAME="chain-scalability"
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

def main():
    parser = setup_parser()
    args = parse_args(parser)

    fig = plt.figure(figsize=(args.width, args.height))

    all_dfs = []

    # Read throughput data
    for color in COLORS:
        if args.__dict__[color]:
            arg_dfs = [ pd.read_csv(f.name) for f in args.__dict__[color] ]
            arg_df = pd.concat(arg_dfs)
            name = args.__dict__[f'{color}_name']
            arg_df["system"] = name[0]
            arg_df["plot_type"] = "throughput"
            arg_df["y_value"] = arg_df["Mpps"]
            all_dfs += [ arg_df ]

    # Read latency data
    for color in COLORS:
        key = f"lat_{color}"
        if args.__dict__[key]:
            name = args.__dict__[f'{key}_name']
            for f in args.__dict__[key]:
                arg_df = pd.read_csv(f.name)
                # Check for companion .csv with per-packet latency samples
                csv_path = os.path.splitext(f.name)[0] + ".csv"
                if os.path.exists(csv_path):
                    lat_df = pd.read_csv(csv_path)
                    # Use median to avoid pktgen outliers (see repl.py)
                    arg_df["lat_us"] = lat_df["Latency"].quantile(0.5)
                    arg_df["lat_us"] = arg_df["lat_us"] / 1000  # convert from ns to us
                elif "lat_us" not in arg_df.columns:
                    print(f"Warning: no latency data for {f.name}")
                    arg_df["lat_us"] = np.nan
                arg_df["system"] = name[0]
                arg_df["plot_type"] = "latency"
                arg_df["y_value"] = arg_df["lat_us"]
                all_dfs += [ arg_df ]

    if all_dfs:
        df = pd.concat(all_dfs)
    else:
        df = pd.DataFrame(columns=['system', 'chaining', 'y_value', 'plot_type'])

    columns = ['system', 'chaining', 'y_value', 'plot_type']
    systems = [ "Insecure", "Secure", "Naive", "Slick" ]
    chains = [ 1, 4, 16 ]
    rows = []

    existing_combos = set(zip(df["system"], df["plot_type"])) if not df.empty else set()

    # Create synthetic fallback data
    for plot_type in ["throughput", "latency"]:
        for system in systems:
            if (system, plot_type) in existing_combos:
                continue
            for ch in chains:
                value = 0
                if ch == 1:
                    value = 2
                elif ch == 4:
                    value = 1
                elif ch == 16:
                    value = 0.8

                factor = 1
                if system == "Slick":
                    factor = 1.5

                value *= factor

                if plot_type == "latency":
                    value = 3.5 - value

                rows += [[system, ch, value, plot_type]]

    df = pd.concat([df, pd.DataFrame(rows, columns=columns)])
    systems += [ s for s in df['system'].unique() if s not in systems ]



    # Create FacetGrid for side-by-side plots
    grid = sns.FacetGrid(df, col='plot_type', height=args.height, aspect=args.width/(2*args.height),
                         sharey=False, sharex=True)

    # Set axis below for all subplots
    for ax in grid.axes.flat:
        ax.set_axisbelow(True)
        ax.grid(True)

    # Map lineplot to each facet
    grid.map_dataframe(sns.lineplot,
                      x="chaining",
                      y="y_value",
                      hue="system",
                      hue_order=systems,
                      style="system",
                      style_order=systems,
                      markers=True,
                      errorbar='ci')

    if not args.logarithmic:
        for ax in grid.axes.flat:
            ax.set_ylim(bottom=0)
    else:
        for ax in grid.axes.flat:
            ax.set_xscale('log')

    def rename_legend_labels(ax, label_map):
        if ax.get_legend() is not None:
            for i, text in enumerate(ax.get_legend().get_texts()):
                if text.get_text() in label_map:
                    text.set_text(label_map[text.get_text()])

    # Apply legend renaming to each axis
    for ax in grid.axes.flat:
        rename_legend_labels(ax, LEGEND_MAP)

    # Add legend to the grid
    grid.add_legend(title=None, frameon=False)

    # Position the legend outside the plot area
    if grid._legend:
        # sns.move_legend(grid, "center left", bbox_to_anchor=(1.02, 0.5), ncol=1, title=None, frameon=False)
        n_labels = len(grid._legend.get_texts())
        sns.move_legend(grid, "upper center", bbox_to_anchor=(0.5, 1.08), ncol=n_labels, title=None, frameon=False)
    # plot.add_legend(
    #         bbox_to_anchor=(0.55, 0.3),
    #         loc='upper left',
    #         ncol=3, title=None, frameon=False,
    #                 )

    grid.figure.set_size_inches(args.width, args.height)

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

    # Add annotation to first subplot only
    grid.axes.flat[0].annotate(
        "↑ Higher is better", # or ↓ ← ↑ →
        xycoords="axes points",
        xy=(10, 0),
        xytext=(-25, -27),
        color="navy",
        weight="bold",
    )
    grid.axes.flat[1].annotate(
        "↓ Lower is better", # or ↓ ← ↑ →
        xycoords="axes points",
        xy=(10, 0),
        xytext=(-25, -27),
        color="navy",
        weight="bold",
    )

    # Set axis labels (different y-axis for each subplot)
    for i, ax in enumerate(grid.axes.flat):
        ax.set_xlabel('                          Chain length')
        if i == 0:
            ax.set_ylabel('Throughput [Mpps]')
        else:
            ax.set_ylabel('Latency [us]')

    map_grid_titles(grid, grid_title_map)

    # Adjust layout and save
    grid.figure.tight_layout(pad=0.1)
    grid.figure.subplots_adjust(top=0.8)
    grid.savefig(args.output.name)
    plt.close()


if __name__ == '__main__':
    main()

