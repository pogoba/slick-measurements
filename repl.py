import os
import importlib
import sys
import plotly.graph_objects as go
import plotly.express as px
import tempfile, multiprocessing
from typing import List
import glob
import pandas as pd
import numpy as np
os.environ["QT_QPA_PLATFORM"] = "xcb"

def foobar():
    print("ok7")

SIZE_SMALL = 64
SIZE_BIG = 1522

def ns2s(ns) -> float:
    return ns / 1e9

def s2ns(s) -> float:
    return s * 1e9

def pps2mpps(pps) -> float:
    return pps / 1e6

def mpps2pps(mpps) -> float:
    return mpps * 1e6

def mpps2gbit(mpps, size = SIZE_SMALL):
    bitps = mpps2pps(mpps) * (size + 20) * 8
    return bitps / 1e9

def mpps2nspp(mpps) -> float:
    return s2ns(1 / mpps2pps(mpps))

def nspp2mpps(nspp) -> float:
    return pps2mpps(1 / ns2s(nspp))

def gbit2mpps(gbitps, size = SIZE_SMALL):
    pps = gbitps * 1e9 / ((size + 20) * 8)
    return pps2mpps(pps)

def gb2gbit(gb):
    return gb * 8

def cycles2ns(cycles, freq_mhz=1996):
    s = cycles / (1e6*freq_mhz)
    return s * 1e9

def display(fig, block=False):

    html_file = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    html_file.write(fig.to_html().encode())
    html_file.close()

    def _show(path):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QKeySequence, QShortcut
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtWebEngineCore import QWebEngineProfile
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        app = QApplication(sys.argv)
        QWebEngineProfile.defaultProfile().downloadRequested.connect(
            lambda item: item.accept()
        )
        view = QWebEngineView()
        view.setWindowTitle('Plot')
        QShortcut(QKeySequence("Ctrl+W"), view, view.close)
        view.load(QUrl.fromLocalFile(path))
        view.resize(900, 600)
        view.show()
        app.exec()
        os.unlink(path)

    p = multiprocessing.Process(target=_show, args=(html_file.name,))
    p.start()
    if block:
        p.join()

def plot_example():

    workload_ns = [10, 50, 100, 200, 500]
    throughput_mpps = [4.88, 12.5, 9.8, 6.2, 2.8]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=workload_ns, y=throughput_mpps, mode='lines+markers'))
    fig.update_layout(
        xaxis_title='Workload [ns]',
        yaxis_title='Throughput [Mpps]',
    )
    # fig.show()
    display(fig, block=False)

def parse_data(systems=None, **kwargs):

    if systems is None:
        systems = kwargs
    else:
        systems = {**systems, **kwargs}

    dfs = []
    for name, pattern in systems.items():
        paths = glob.glob(pattern)
        if not paths:
            print(f"Warning: no files matched for {name}: {pattern}")
            continue
        df = pd.concat([pd.read_csv(p) for p in paths])
        df["system"] = name
        dfs.append(df)

    df = pd.concat(dfs)
    return df

def throughput_vs_workload(df, title):
    fig = go.Figure()
    for name in df["system"].unique():
        sdf = df[df["system"] == name].groupby("workload")["Mpps"].agg(["mean", "std"]).reset_index()
        fig.add_trace(go.Scatter(x=sdf["workload"], y=sdf["mean"],
                                 error_y=dict(type='data', array=sdf["std"]),
                                 mode='lines+markers', name=name))
    fig.update_layout(title=title, xaxis_title='Workload [ns]', yaxis_title='Throughput [Mpps]', yaxis_rangemode='tozero')
    display(fig)

def cpu_normalization(df):
    df["chaining"] = 2
    len = df.shape[0]
    optimal = df[df["system"] == "Optimal"]

    naive = df[df["system"] == "Naive"].copy()
    naive["Mpps"] = naive["Mpps"] / (naive["chaining"]) # + 1)

    slick = df[df["system"] == "Slick"].copy()
    slick["Mpps"] = slick["Mpps"] / (slick["chaining"]) # + 2)

    df = pd.concat([optimal, naive, slick])
    assert df.shape[0] == len, "Normalization should not change the number of rows"
    return df


def foo3(pktsize=64, normalized=False):
    df = parse_data({
        "Optimal": f"./data/out4/userspace_mirror_b32_*ns_c1_{pktsize}b_rep*.log",
        "Naive": f"./data/out4/userspace_noiomgr_b32_*ns_c1_{pktsize}b_rep*.log",
        "Slick": f"./data/out4/userspace_iomgr_b32_*ns_c1_{pktsize}b_rep*.log",
    })
    title = f"b=32; c=2; pktsize={pktsize}"
    if normalized:
        df = cpu_normalization(df)
        title += " (CPU-normalized)"
    throughput_vs_workload(df, title=title)

def barplot(df, x_axis, hue, title=None):
    agg = df.groupby([x_axis, hue])["Mpps"].agg(["mean", "std"]).reset_index()
    agg.columns = [x_axis, hue, "Mpps", "std"]
    fig = px.bar(agg, x=x_axis, y="Mpps", error_y="std", color=hue, barmode="group")
    fig.update_layout(title=title, xaxis_title='Packet size [B]', yaxis_title='Throughput [Mpps]')
    display(fig)

def systems():
    df = parse_data({
        "Optimal": "./data/out3/userspace_mirror_b32_0ns_c1_*.log",
        "Naive": "./data/out3/userspace_noiomgr_b32_0ns_c1_*.log",
        "Slick": "./data/out3/userspace_iomgr_b32_0ns_c1_*.log",
    })
    x_axis = "pktsize"
    hue = "system"
    barplot(df, x_axis, hue, title="b=32; c=2; workload=0ns;")

def batchsizes():
    df = parse_data({
        "Optimal": "./data/out3/userspace_mirror_b*_0ns_c1_64b_*.log",
        "Naive": "./data/out3/userspace_noiomgr_b*_0ns_c1_64b_*.log",
        "Slick": "./data/out3/userspace_iomgr_b*_0ns_c1_64b_*.log",
    })
    x_axis = "batchsize"
    hue = "system"
    barplot(df, x_axis, hue, title="c=2; size=64b; workload=0ns;")


print("Repl.py loaded 🦘")
print("Reload with `repl.reload()`")


# if __name__ == "__main__":
    # print("This script is supposed to be used for static definitions in `make repl`")
    # os.exit(1)
