import os
import importlib
import sys
import plotly.graph_objects as go
import tempfile, multiprocessing
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
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        app = QApplication(sys.argv)
        view = QWebEngineView()
        view.setWindowTitle('Plot')
        view.load(QUrl.fromLocalFile(path))
        view.resize(900, 600)
        view.show()
        app.exec()
        os.unlink(path)

    p = multiprocessing.Process(target=_show, args=(html_file.name,))
    p.start()
    if block:
        p.join()

def plot():

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

print("Repl.py loaded 🦘")
print("Reload with `repl.reload()`")


# if __name__ == "__main__":
    # print("This script is supposed to be used for static definitions in `make repl`")
    # os.exit(1)
