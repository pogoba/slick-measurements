import matplotlib
matplotlib.use("Agg")
from matplotlib.axes import Axes
from matplotlib.patches import Rectangle
from pandas import DataFrame
import pandas as pd
import matplotlib.legend as mlegend
from typing import List, Dict, Any
import seaborn as sns
import matplotlib.colors as mcolors

# most of this file expects to work with seaborn plots

HATCHES = ['O', '\\\\', '*', 'o', 'xx', '.O', '//', '..']

COLORS = sns.color_palette("pastel", 5) + [ mcolors.to_rgb('sandybrown') ]

class mybarplot():
    def __init__(self, data: DataFrame, x: str, y: str, hue: str = None):
        pass

    @staticmethod
    def x_category_value(rect: Rectangle, ax: Axes):
        """
        In a categorical barplot (where x axis is not numerical), get the value of the X category represented by the bar.
        """
        x_coord = rect.get_bbox().x0 + rect.get_bbox().width / 2
        x_category_id = round(x_coord) # x axis is not numerical
        labels = [label.get_text() for label in ax.get_xticklabels()]
        if not labels:
            # axes sharing their x axis (e.g. FacetGrid rows) may not have
            # materialized tick label Texts; ask the (shared) formatter instead
            labels = ax.xaxis.get_major_formatter().format_ticks(ax.get_xticks())
        x_category_value = labels[x_category_id]
        return x_category_value


    @staticmethod
    def y_value(rect: Rectangle):
        """
        Y value represented by the bar.
        """
        return rect.get_bbox().height


    @staticmethod
    def hue_value(bar, hues_list):
        """
        @param hues_list: use list_hues()
        """
        lookalikes = []
        for handle, label in hues_list:
            if mybarplot.bars_equal(bar, handle):
                lookalikes += [label]

        if len(lookalikes) != 1:
            raise Exception("Cannot identify bar.")
        hue_value = lookalikes[0]
        return hue_value


    @staticmethod
    def bars_equal(a, b):
        """
        Check if two bars look the same (dimensions aside)
        """
        # return (
        #         a.get_facecolor() == b.get_facecolor()
        # )
        try:
            ret = (
                    a.get_edgecolor() == b.get_edgecolor() and
                    a.get_facecolor() == b.get_facecolor() and
                    a.get_hatch() == b.get_hatch()
            )
        except Exception as _:
            ret = False
        return ret


    @staticmethod
    def list_hues(ax: Axes):
        handles, labels = mlegend._get_legend_handles_labels([ax])
        handles_labels = []
        # convert single-use zip iterator to proper list
        for handle, label in zip(handles, labels):
            handles_labels += [(handle, label)]
        return handles_labels


    @staticmethod
    def convert_for(value: str, data: DataFrame, column: str):
        target_type = data[column].dtype

        # Convert the string to the appropriate type
        if pd.api.types.is_integer_dtype(target_type):
            return int(value)
        elif pd.api.types.is_float_dtype(target_type):
            return float(value)
        else:
            # If it's already a string type, no conversion needed
            return value

    @staticmethod
    def all_bars(data: DataFrame, x: str, y: str, hue: str, ax: Axes):
        hue_handles_labels = mybarplot.list_hues(ax)
        for bar in ax.patches:
            hue_value = mybarplot.hue_value(bar, hue_handles_labels)
            x_category_value = mybarplot.x_category_value(bar, ax)
            y_value = mybarplot.y_value(bar)

            # get the data used for this bar
            x_category_value = mybarplot.convert_for(x_category_value, data, x)
            bars_data = data[(data[x] == x_category_value) & (data[hue] == hue_value)]

            yield bar, bars_data, y_value


    @staticmethod
    def add_colors(data: DataFrame, x: str, y: str, hue: str, ax: Axes, colors: List[str] | Dict[str, Any], color_by: str):
        color_map = dict()
        if isinstance(colors, list):
            for hue_value, color in zip(data[color_by].unique(), colors):
                color_map[hue_value] = color
        elif isinstance(colors, dict):
            color_map = colors

        for bar, bars_data, bars_y in mybarplot.all_bars(data, x, y, hue, ax):
            color_by_value = bars_data[color_by].unique()
            if len(color_by_value) == 0:
                continue # bar without data (e.g. hue missing for this x category)
            if len(color_by_value) != 1:
                raise Exception(f"Color by {color_by} is ambiguous.")
            color_by_value = color_by_value[0]

            bar.set_facecolor(color_map[color_by_value])


    @staticmethod
    def add_hatches(data: DataFrame, x: str, y: str, hue: str, ax: Axes, hatch_by: str, hatches: List[str] | Dict[str, str] = HATCHES):
        hatch_map = dict()
        if isinstance(hatches, list):
            for hue_value, hatch in zip(data[hatch_by].unique(), hatches):
                hatch_map[hue_value] = hatch
        elif isinstance(hatches, dict):
            hatch_map = hatches

        for bar, bars_data, bars_y in mybarplot.all_bars(data, x, y, hue, ax):
            hatch_by_value = bars_data[hatch_by].unique()
            if len(hatch_by_value) == 0:
                continue # bar without data (e.g. hue missing for this x category)
            if len(hatch_by_value) != 1:
                raise Exception(f"Hatch by {hatch_by} is ambiguous.")
            hatch_by_value = hatch_by_value[0]

            bar.set_hatch(hatch_map[hatch_by_value])






def barplot_add_hatches(plot_in_grid: Axes, nr_hues: int, offset: int = 0, hatches=HATCHES):
    """
    Iterates over a plots bars and adds hatches.

    @param nr_hues: To understand which bar is which, we need info about how many bars are at each tick.
    @param offset: If you don't want to start with the first hatch in `hatches`
    @param hatches: List of hatches that gets mapped to bars
    """
    hatches_used = -1
    bars_hatched = 0
    for bar in plot_in_grid.patches:
        if nr_hues <= 1:
            hatches_used += 1
        else: # with multiple hues, we draw bars with the same hatch in batches
            if bars_hatched % nr_hues == 0:
                hatches_used += 1
        # if bars_hatched % 7 == 0:
        #     hatches_used += 1
        bars_hatched += 1
        if bar.get_bbox().x0 == 0 and bar.get_bbox().x1 == 0 and bar.get_bbox().y0 == 0 and bar.get_bbox().y1 == 0:
            # skip bars that are not rendered
            continue
        hatch = hatches[(offset + hatches_used) % len(hatches)]
        print(bar, hatches_used, hatch)
        bar.set_hatch(hatch)

def grid_set_titles(facet_grid, titles):
    for ax, title in zip(facet_grid.axes.flat, titles):
        ax.set_title(title)

def map_grid_titles(facet_grid, map):
    for ax in facet_grid.axes.flat:
        if ax.figure is None:
            continue # skip remove()ed grid tiles
        new_title = map.get(ax.get_title(), ax.get_title())
        # for some reason, we change the default font size if we don't specify it
        fontsize = ax.title.get_fontsize()
        ax.set_title(new_title, fontdict={'fontsize': fontsize})


