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
DATA = "./data/out9-output2v2/"

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







# ========= Plotting infra ===========



save_dont_display = None # none or path
save_dont_display_magnify = None

def save(plotting_fn, filename, magnify=2):
    global save_dont_display
    global save_dont_display_magnify
    save_dont_display = filename
    save_dont_display_magnify = magnify
    plotting_fn()
    save_dont_display = None
    save_dont_display_magnify = None

def display(fig, block=False):

    if save_dont_display is not None:
        height = 500 / save_dont_display_magnify
        width = 700 / save_dont_display_magnify
        fig.update_layout(margin=dict(l=0, r=0, t=50, b=0))
        fig.write_image(save_dont_display, scale=3*save_dont_display_magnify, width=width, height=height)
        return

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




# ========= Data Loaders ===========




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

def parse_latency_csv(systems=None, **kwargs):

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
        for p in paths:
            df = pd.read_csv(p)
            # override lat_us in df with latency mean from .csv file
            csv_path = os.path.splitext(p)[0] + ".csv"
            if os.path.exists(csv_path):
                lat_df = pd.read_csv(csv_path)
                # Pktgen produces occasionally wrong latency numbers for minimum sized packets when the timestamp doesnt fit into the packet.
                # These outliers are typically a latency of 6s for a single sample only, which is clearly wrong as can be seen from the stable throughput numbers.
                # Mean doesnt work therefore, use median.
                df["lat_us"] = lat_df["Latency"].quantile(0.5)
                # df["lat_us"] = lat_df["Latency"].mean()
                df["lat_us"] = df["lat_us"] / 1000 # convert from ns to us

            else:
                print(f"Warning: no matching csv for {p}")
                df["lat_us"] = np.nan
            df["system"] = name
            dfs.append(df)

    df = pd.concat(dfs)
    return df



# ========= Base Plots ===========



def throughput_vs_workload(df, title):
    fig = go.Figure()
    for name in df["system"].unique():
        sdf = df[df["system"] == name].groupby("workload")["Mpps"].agg(["mean", "std"]).reset_index()
        fig.add_trace(go.Scatter(x=sdf["workload"], y=sdf["mean"],
                                 error_y=dict(type='data', array=sdf["std"]),
                                 mode='lines+markers', name=name))
    fig.update_layout(title=title, xaxis_title='Workload [ns]', yaxis_title='Throughput [Mpps]', yaxis_rangemode='tozero')
    display(fig)

def throughput_vs_memory_workload(df, title):
    df["memory_workload"] = df["memory_workload"] / 1024
    fig = go.Figure()
    for name in df["system"].unique():
        sdf = df[df["system"] == name].groupby("memory_workload")["Mpps"].agg(["mean", "std"]).reset_index()
        fig.add_trace(go.Scatter(x=sdf["memory_workload"], y=sdf["mean"],
                                 error_y=dict(type='data', array=sdf["std"]),
                                 mode='lines+markers', name=name))
    fig.update_layout(title=title, xaxis_title='Workload [kB]', yaxis_title='Throughput [Mpps]', yaxis_rangemode='tozero')
    display(fig)

def throughput_vs_chaining(df, title):
    fig = go.Figure()
    for name in df["system"].unique():
        sdf = df[df["system"] == name].groupby("chaining")["Mpps"].agg(["mean", "std"]).reset_index()
        fig.add_trace(go.Scatter(x=sdf["chaining"], y=sdf["mean"],
                                 error_y=dict(type='data', array=sdf["std"]),
                                 mode='lines+markers', name=name))
    fig.update_layout(title=title, xaxis_title='Chain length [VNFlets]', yaxis_title='Throughput [Mpps]', yaxis_rangemode='tozero')
    display(fig)

def latency_vs_workload(df, title):
    fig = go.Figure()
    for name in df["system"].unique():
        sdf = df[df["system"] == name].groupby("workload")["lat_us"].agg(["mean", "std"]).reset_index()
        fig.add_trace(go.Scatter(x=sdf["workload"], y=sdf["mean"],
                                 error_y=dict(type='data', array=sdf["std"]),
                                 mode='lines+markers', name=name))
    fig.update_layout(title=title, xaxis_title='Workload [ns]', yaxis_title='Latency [us]', yaxis_rangemode='tozero')
    display(fig)

def barplot(df, x_axis, x_axis_title, hue, title=None):
    agg = df.groupby([x_axis, hue])["Mpps"].agg(["mean", "std"]).reset_index()
    agg.columns = [x_axis, hue, "Mpps", "std"]
    fig = px.bar(agg, x=x_axis, y="Mpps", error_y="std", color=hue, barmode="group")
    fig.update_layout(title=title, xaxis_title=x_axis_title, yaxis_title='Throughput [Mpps]')
    display(fig)



# ========= Data Transformers ===========


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



# ========= Concrete Plots ===========


def throughput(pktsize=64, normalized=False):
    df = parse_data({
        # "Optimal": f"{DATA}/userspace_mirror_b32_*ns_0b_c2_{pktsize}b_rep*.log",
        "Insecure": f"{DATA}/userspace_insecure_b32_*ns_0b_c2_{pktsize}b_rep*.log",
        "Secure": f"./data/out10-output3v2/multivm_mirror_b32_*ns_0b_c0_v2_{pktsize}b_rep*.log",
        "Naive": f"{DATA}/userspace_noiomgr_b32_*ns_0b_c2_{pktsize}b_rep*.log",
        "Slick": f"{DATA}/userspace_iomgr_b32_*ns_0b_c2_{pktsize}b_rep*.log",
    })
    title = f"b=32; c=2; pktsize={pktsize}"
    if normalized:
        df = cpu_normalization(df)
        title += " (CPU-normalized)"
    throughput_vs_workload(df, title=title)

def throughput_memorywl(pktsize=64, normalized=False):
    # DATA = "./data/out7/"
    df = parse_data({
        "Optimal": f"{DATA}/userspace_mirror_b32_0ns_*b_c2_{pktsize}b_rep*.log",
        "Insecure": f"{DATA}/userspace_insecure_b32_0ns_*b_c2_{pktsize}b_rep*.log",
        "Secure": f"./data/out10-output3v2/multivm_mirror_b32_0ns_*b_c0_v2_{pktsize}b_rep*.log",
        "Naive": f"{DATA}/userspace_noiomgr_b32_0ns_*b_c2_{pktsize}b_rep*.log",
        "Slick": f"{DATA}/userspace_iomgr_b32_0ns_*b_c2_{pktsize}b_rep*.log",
    })
    title = f"b=32; c=2; pktsize={pktsize}"
    if normalized:
        df = cpu_normalization(df)
        title += " (CPU-normalized)"
    throughput_vs_memory_workload(df, title=title)

def latency(pktsize=64):
    # df = parse_data({
    df = parse_latency_csv({
        "Optimal": f"{DATA}/vm_lat_mirror_b32_*ns_c2_{pktsize}b_rep*.log",
        "Insecure": f"{DATA}/vm_lat_insecure_b32_*ns_c2_{pktsize}b_rep*.log",
        "Secure": f"./data/out10-output3v2/multivm_mirror_b32_0ns_*b_c0_v2_{pktsize}b_rep*.log",
        "Naive": f"{DATA}/vm_lat_noiomgr_b32_*ns_c2_{pktsize}b_rep*.log",
        "Slick": f"{DATA}/vm_lat_iomgr_b32_*ns_c2_{pktsize}b_rep1.log",
    })
    title = f"b=32; c=2; pktsize={pktsize}"
    latency_vs_workload(df, title=title)

def chaining(pktsize=64, normalized=False):
    df = parse_data({
        # "Optimal": f"{DATA}/userspace_mirror_b32_0ns_0b_c*_{pktsize}b_rep*.log",
        "Insecure": f"{DATA}/userspace_insecure_b32_0ns_0b_c*_{pktsize}b_rep*.log",
        "Secure": f"./data/out10-output3v2/multivm_mirror_b32_0ns_0b_c0_v*_{pktsize}b_rep*.log",
        "Naive": f"{DATA}/userspace_noiomgr_b32_0ns_0b_c*_{pktsize}b_rep*.log",
        "Slick": f"{DATA}/userspace_iomgr_b32_0ns_0b_c*_{pktsize}b_rep*.log",
    })
    title = f"b=32; pktsize={pktsize}"
    if normalized:
        df = cpu_normalization(df)
        title += " (CPU-normalized)"
    throughput_vs_chaining(df, title=title)

def systems():
    df = parse_data({
        "Optimal": f"{DATA}/userspace_mirror_b32_0ns_0b_c2_*.log",
        "Insecure": f"{DATA}/userspace_insecure_b32_0ns_0b_c2_*.log",
        "Secure": f"./data/out10-output3v2/multivm_mirror_b32_0ns_0b_c0_v2_*.log",
        "Naive": f"{DATA}/userspace_noiomgr_b32_0ns_0b_c2_*.log",
        "Slick": f"{DATA}/userspace_iomgr_b32_0ns_0b_c2_*.log",
    })
    x_axis = "pktsize"
    x_title = 'Packet size [B]'
    hue = "system"
    barplot(df, x_axis, x_title, hue, title="b=32; c=2; workload=0ns;")

def batchsizes():
    df = parse_data({
        "Optimal": f"{DATA}/userspace_mirror_b*_0ns_0b_c2_64b_*.log",
        "Insecure": f"{DATA}/userspace_insecure_b*_0ns_0b_c2_64b_*.log",
        "Secure": f"./data/out10-output3v2/multivm_mirror_b*_0ns_0b_c0_v2_64b_*.log",
        "Naive": f"{DATA}/userspace_noiomgr_b*_0ns_0b_c2_64b_*.log",
        "Slick": f"{DATA}/userspace_iomgr_b*_0ns_0b_c2_64b_*.log",
    })
    x_axis = "batchsize"
    x_title = 'Batch size [pkts]'
    hue = "system"
    barplot(df, x_axis, x_title, hue, title="c=2; size=64b; workload=0ns;")

def save_report(prefix = "report"):
    save(lambda: throughput(pktsize=64), f"{prefix}_throughput_64b.png")
    save(lambda: throughput(pktsize=1500), f"{prefix}_throughput_1500b.png")
    save(lambda: throughput_memorywl(pktsize=64), f"{prefix}_throughput_memorywl_64b.png")
    save(lambda: latency(pktsize=64), f"{prefix}_latency_64b.png")
    save(lambda: latency(pktsize=1500), f"{prefix}_latency_1500b.png")
    save(lambda: chaining(pktsize=64), f"{prefix}_chaining_64b.png")
    save(lambda: chaining(pktsize=1500), f"{prefix}_chaining_1500b.png")

print("Repl.py loaded 🦘")
print("Reload with `repl.reload()`")


# if __name__ == "__main__":
    # print("This script is supposed to be used for static definitions in `make repl`")
    # os.exit(1)
