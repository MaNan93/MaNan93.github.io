#!/usr/bin/env python3
"""
pcie_tx_preset.py

PCIe Gen3/Gen4/Gen5 Tx Preset demo based on Table 8-1.

4-tap Tx FFE coefficients:
    C-2, C-1, C0, C+1

For Gen3~Gen5 presets:
    C-2 = 0

Normalization:
    |C-2| + |C-1| + |C0| + |C+1| = 1

Discrete-symbol model:
    y[n] = C-2*x[n+2] + C-1*x[n+1] + C0*x[n] + C+1*x[n-1]

Thus:
    C-2 : 2nd pre-cursor
    C-1 : 1st pre-cursor
    C0  : main cursor
    C+1 : post-cursor

NRZ mapping:
    0 -> -1
    1 -> +1

P10 is not included as a fixed preset because its C+1 and related ratios
are defined by Note 2 rather than one fixed coefficient value.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from typing import Dict, List, Sequence


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


def db20(ratio: float) -> float:
    return 20.0 * math.log10(ratio)


def voltage_levels(p: Preset) -> dict:
    """PCIe Tx equalization voltage definitions and ratios."""
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
    out = []
    for ch in clean:
        if ch == "0":
            out.append(-1.0)
        elif ch == "1":
            out.append(+1.0)
        else:
            raise ValueError(f"invalid bit {ch!r}; only 0/1 are allowed")
    return out


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


def print_preset(p: Preset) -> None:
    v = voltage_levels(p)
    print(f"{p.name}")
    print(f"  C-2 = {p.c_m2:+.3f}")
    print(f"  C-1 = {p.c_m1:+.3f}")
    print(f"  C0  = {p.c0:+.3f}")
    print(f"  C+1 = {p.c_p1:+.3f}")
    print()
    print(f"  Va  = {v['Va']:.3f}")
    print(f"  Vb  = {v['Vb']:.3f}")
    print(f"  Vc1 = {v['Vc1']:.3f}")
    print(f"  Vc2 = {v['Vc2']:.3f}")
    print(f"  Vd  = {v['Vd']:.3f}")
    print()
    print(f"  Pre-Shoot 2 = {v['preshoot2_db']:+.2f} dB")
    print(f"  Pre-Shoot 1 = {v['preshoot1_db']:+.2f} dB")
    print(f"  De-emphasis = {v['deemph_db']:+.2f} dB")
    print(f"  Boost       = {v['boost_db']:+.2f} dB")


def print_all() -> None:
    order = ["P4", "P1", "P0", "P9", "P8", "P7", "P5", "P6", "P3", "P2"]
    header = (
        f"{'Preset':<6}"
        f"{'C-2':>8}{'C-1':>8}{'C0':>8}{'C+1':>8}"
        f"{'PS2(dB)':>10}{'PS1(dB)':>10}{'DE(dB)':>10}"
        f"{'Va/Vd':>9}{'Vb/Vd':>9}{'Vc1/Vd':>10}{'Vc2/Vd':>10}"
    )
    print(header)
    print("-" * len(header))

    for name in order:
        p = PRESETS[name]
        v = voltage_levels(p)
        vd = v["Vd"]
        print(
            f"{name:<6}"
            f"{p.c_m2:>8.3f}{p.c_m1:>8.3f}{p.c0:>8.3f}{p.c_p1:>8.3f}"
            f"{v['preshoot2_db']:>10.2f}"
            f"{v['preshoot1_db']:>10.2f}"
            f"{v['deemph_db']:>10.2f}"
            f"{v['Va']/vd:>9.3f}"
            f"{v['Vb']/vd:>9.3f}"
            f"{v['Vc1']/vd:>10.3f}"
            f"{v['Vc2']/vd:>10.3f}"
        )


def print_waveform(bits: str, p: Preset) -> None:
    clean = bits.replace("_", "").replace(" ", "")
    x = bits_to_nrz(clean)
    y = apply_ffe(x, p)

    print()
    print(f"Pattern: {clean}")
    print(f"Preset : {p.name}")
    print()
    print(f"{'n':>4} {'bit':>4} {'x[n]':>8} {'y[n]':>10}")
    print("-" * 30)
    for n, (bit, xv, yv) in enumerate(zip(clean, x, y)):
        print(f"{n:>4} {bit:>4} {xv:>8.3f} {yv:>10.3f}")


def plot_waveform(bits: str, p: Preset, samples_per_ui: int = 64) -> None:
    try:
        import numpy as np
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit(
            "Plot mode requires numpy and matplotlib:\n"
            "  pip install numpy matplotlib"
        ) from exc

    x = bits_to_nrz(bits)
    y = apply_ffe(x, p)

    x_os = np.repeat(np.asarray(x), samples_per_ui)
    y_os = np.repeat(np.asarray(y), samples_per_ui)
    t = np.arange(len(x_os)) / samples_per_ui

    plt.figure(figsize=(12, 5))
    plt.step(t, x_os, where="post", label="Original NRZ x[n]")
    plt.step(t, y_os, where="post", label=f"{p.name} Tx FFE y[n]")
    plt.xlabel("UI")
    plt.ylabel("Normalized amplitude")
    plt.title(
        f"PCIe Tx Preset {p.name}: "
        f"C-2={p.c_m2:.3f}, C-1={p.c_m1:.3f}, "
        f"C0={p.c0:.3f}, C+1={p.c_p1:.3f}"
    )
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description="PCIe Gen3~Gen5 Tx preset / FFE demo")
    parser.add_argument("-p", "--preset", choices=sorted(PRESETS), default="P8")
    parser.add_argument("-b", "--bits", default="0000111100011110000")
    parser.add_argument("--all", action="store_true", help="print all preset values")
    parser.add_argument("--plot", action="store_true", help="plot NRZ and FFE waveforms")
    args = parser.parse_args()

    if args.all:
        print_all()
        return

    p = PRESETS[args.preset]
    print_preset(p)
    print_waveform(args.bits, p)

    if args.plot:
        plot_waveform(args.bits, p)


if __name__ == "__main__":
    main()
