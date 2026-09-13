#!/usr/bin/env python3
"""
pcie_tx_preset_gui.py

PCIe Gen3/Gen4/Gen5 Tx Preset real-time visualizer.

Features:
  - Preset selectable by combo box
  - Editable NRZ bit pattern
  - Real-time coefficient / voltage-ratio display
  - Real-time Tx FFE waveform update
  - Supports P0~P9 fixed presets from PCIe Table 8-1

Model:
    y[n] =
        C-2 * x[n+2]
      + C-1 * x[n+1]
      + C0  * x[n]
      + C+1 * x[n-1]

Where:
    C-2 : 2nd pre-cursor
    C-1 : 1st pre-cursor
    C0  : main cursor
    C+1 : post-cursor

For Gen3~Gen5 fixed presets:
    C-2 = 0

NRZ:
    bit 0 -> -1
    bit 1 -> +1
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import Dict, List, Sequence

import numpy as np

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


@dataclass(frozen=True)
class Preset:
    name: str
    c_m2: float
    c_m1: float
    c_p1: float

    @property
    def c0(self) -> float:
        return 1.0 - abs(self.c_m2) - abs(self.c_m1) - abs(self.c_p1)


PRESETS: Dict[str, Preset] = {
    "P0": Preset("P0", 0.000,  0.000, -0.250),
    "P1": Preset("P1", 0.000,  0.000, -0.167),
    "P2": Preset("P2", 0.000,  0.000, -0.200),
    "P3": Preset("P3", 0.000,  0.000, -0.125),
    "P4": Preset("P4", 0.000,  0.000,  0.000),
    "P5": Preset("P5", 0.000, -0.100,  0.000),
    "P6": Preset("P6", 0.000, -0.125,  0.000),
    "P7": Preset("P7", 0.000, -0.100, -0.200),
    "P8": Preset("P8", 0.000, -0.125, -0.125),
    "P9": Preset("P9", 0.000, -0.167,  0.000),
}

PRESET_ORDER = ["P4", "P1", "P0", "P9", "P8", "P7", "P5", "P6", "P3", "P2"]


def db20(ratio: float) -> float:
    if ratio <= 0:
        return float("-inf")
    return 20.0 * math.log10(ratio)


def voltage_levels(p: Preset) -> dict:
    cm2, cm1, c0, cp1 = p.c_m2, p.c_m1, p.c0, p.c_p1

    va  = +cm2 + cm1 + c0 - cp1
    vb  = +cm2 + cm1 + c0 + cp1
    vc1 = +cm2 - cm1 + c0 + cp1
    vc2 = -cm2 + cm1 + c0 + cp1
    vd  = -cm2 - cm1 + c0 - cp1

    return {
        "Va": va,
        "Vb": vb,
        "Vc1": vc1,
        "Vc2": vc2,
        "Vd": vd,
        "deemph_db": db20(vb / va),
        "preshoot1_db": db20(vc1 / vb),
        "preshoot2_db": db20(vc2 / vb),
        "boost_db": db20(vd / vb),
    }


def bits_to_nrz(bits: str) -> List[float]:
    clean = bits.replace("_", "").replace(" ", "")
    if not clean:
        raise ValueError("bit pattern is empty")
    for ch in clean:
        if ch not in "01":
            raise ValueError("bit pattern may only contain 0, 1, spaces, or underscores")
    return [1.0 if ch == "1" else -1.0 for ch in clean]


def get_sample(x: Sequence[float], i: int) -> float:
    if i < 0:
        return x[0]
    if i >= len(x):
        return x[-1]
    return x[i]


def apply_ffe(x: Sequence[float], p: Preset) -> List[float]:
    y = []
    for n in range(len(x)):
        y.append(
            p.c_m2 * get_sample(x, n + 2)
            + p.c_m1 * get_sample(x, n + 1)
            + p.c0  * get_sample(x, n)
            + p.c_p1 * get_sample(x, n - 1)
        )
    return y


class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.figure = Figure(figsize=(10, 5), tight_layout=True)
        super().__init__(self.figure)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.updateGeometry()
        self.ax = self.figure.add_subplot(111)

    def update_plot(self, bits: str, p: Preset):
        x = bits_to_nrz(bits)
        y = apply_ffe(x, p)

        sps = 80
        x_os = np.repeat(np.asarray(x), sps)
        y_os = np.repeat(np.asarray(y), sps)
        t = np.arange(len(x_os)) / sps

        self.ax.clear()
        self.ax.step(t, x_os, where="post", label="Original NRZ x[n]", linewidth=1.4)
        self.ax.step(t, y_os, where="post", label=f"{p.name} Tx FFE y[n]", linewidth=2.0)
        self.ax.axhline(0.0, linewidth=0.8, alpha=0.5)
        self.ax.set_xlim(0, max(len(x), 1))
        self.ax.set_ylim(-1.2, 1.2)
        self.ax.set_xlabel("Time [UI]")
        self.ax.set_ylabel("Normalized amplitude")
        self.ax.set_title(
            f"{p.name}  |  "
            f"C-2={p.c_m2:+.3f}, "
            f"C-1={p.c_m1:+.3f}, "
            f"C0={p.c0:+.3f}, "
            f"C+1={p.c_p1:+.3f}"
        )
        self.ax.grid(True, alpha=0.25)
        self.ax.legend(loc="upper right")
        self.draw_idle()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PCIe Gen3~Gen5 Tx Preset Visualizer")
        self.resize(1180, 720)

        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        control_box = QGroupBox("Tx Preset")
        control_layout = QFormLayout(control_box)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(PRESET_ORDER)
        self.preset_combo.setCurrentText("P8")
        control_layout.addRow("Preset:", self.preset_combo)
        self.bits_edit = QLineEdit("0000111100011110000")
        self.bits_edit.setPlaceholderText("e.g. 000011110001111")
        control_layout.addRow("NRZ pattern:", self.bits_edit)
        self.example_btn = QPushButton("Load transition pattern")
        control_layout.addRow("", self.example_btn)
        top_layout.addWidget(control_box, 1)

        coef_box = QGroupBox("FFE coefficients")
        coef_layout = QFormLayout(coef_box)
        self.c_m2_label = QLabel()
        self.c_m1_label = QLabel()
        self.c0_label = QLabel()
        self.c_p1_label = QLabel()
        coef_layout.addRow("C-2:", self.c_m2_label)
        coef_layout.addRow("C-1:", self.c_m1_label)
        coef_layout.addRow("C0:", self.c0_label)
        coef_layout.addRow("C+1:", self.c_p1_label)
        top_layout.addWidget(coef_box, 1)

        ratio_box = QGroupBox("PCIe equalization ratios")
        ratio_layout = QFormLayout(ratio_box)
        self.ps2_label = QLabel()
        self.ps1_label = QLabel()
        self.de_label = QLabel()
        self.boost_label = QLabel()
        ratio_layout.addRow("Pre-Shoot 2:", self.ps2_label)
        ratio_layout.addRow("Pre-Shoot 1:", self.ps1_label)
        ratio_layout.addRow("De-emphasis:", self.de_label)
        ratio_layout.addRow("Boost:", self.boost_label)
        top_layout.addWidget(ratio_box, 1)

        voltage_box = QGroupBox("Voltage levels")
        voltage_layout = QFormLayout(voltage_box)
        self.va_label = QLabel()
        self.vb_label = QLabel()
        self.vc1_label = QLabel()
        self.vc2_label = QLabel()
        self.vd_label = QLabel()
        voltage_layout.addRow("Va:", self.va_label)
        voltage_layout.addRow("Vb:", self.vb_label)
        voltage_layout.addRow("Vc1:", self.vc1_label)
        voltage_layout.addRow("Vc2:", self.vc2_label)
        voltage_layout.addRow("Vd:", self.vd_label)
        top_layout.addWidget(voltage_box, 1)

        self.canvas = PlotCanvas(self)
        main_layout.addWidget(self.canvas, 1)
        self.status = QLabel()
        self.status.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        main_layout.addWidget(self.status)

        self.preset_combo.currentTextChanged.connect(self.refresh)
        self.bits_edit.textChanged.connect(self.refresh)
        self.example_btn.clicked.connect(self.load_example)
        self.refresh()

    def load_example(self):
        self.bits_edit.setText("0000111100011110000")

    def refresh(self):
        try:
            p = PRESETS[self.preset_combo.currentText()]
            v = voltage_levels(p)

            self.c_m2_label.setText(f"{p.c_m2:+.3f}")
            self.c_m1_label.setText(f"{p.c_m1:+.3f}")
            self.c0_label.setText(f"{p.c0:+.3f}")
            self.c_p1_label.setText(f"{p.c_p1:+.3f}")
            self.ps2_label.setText(f"{v['preshoot2_db']:+.2f} dB")
            self.ps1_label.setText(f"{v['preshoot1_db']:+.2f} dB")
            self.de_label.setText(f"{v['deemph_db']:+.2f} dB")
            self.boost_label.setText(f"{v['boost_db']:+.2f} dB")
            self.va_label.setText(f"{v['Va']:.3f}")
            self.vb_label.setText(f"{v['Vb']:.3f}")
            self.vc1_label.setText(f"{v['Vc1']:.3f}")
            self.vc2_label.setText(f"{v['Vc2']:.3f}")
            self.vd_label.setText(f"{v['Vd']:.3f}")

            self.canvas.update_plot(self.bits_edit.text(), p)
            self.status.setText(
                "x[n] is the original NRZ symbol sequence; y[n] is the Tx FFE output."
            )
            self.status.setStyleSheet("")

        except ValueError as exc:
            self.status.setText(str(exc))
            self.status.setStyleSheet("color: red;")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
