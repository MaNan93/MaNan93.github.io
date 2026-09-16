---
title: "PCIe PHY Rterm、VCM 与 AC Coupling"
date: 2026-09-16 10:00:00 +0800
categories: [PCIe, PHY]
tags: [PCIe, PHY, Rterm, VCM, AC Coupling, Receiver Detect]
permalink: /pcie-phy-rterm/
---

在 PCIe PHY 调试中，经常会看到 `Rterm`、`VCM`、Rterm calibration、Receiver Detect 等概念。它们实际上都和高速差分接收端的电气工作方式有关。

## 1. Rterm 是什么

**Rterm（Receiver Termination）**就是接收端终端阻抗。PCIe 差分通道通常按约 100 Ω 差分阻抗设计，因此 RX 端需要提供与通道匹配的终端阻抗，以降低信号反射。

反射系数为：

```text
Γ = (ZL - Z0) / (ZL + Z0)
```

当负载阻抗 `ZL = Z0` 时，Γ = 0，理想情况下没有反射；如果接收端接近开路，则会产生很强的反射。

## 2. 两种容易遇到的 Rterm 形式

### 跨接（Differential / Cross Termination）

```text
RX_P ───────+──── RX input
            |
           100Ω
            |
RX_N ───────+──── RX input
```

这种方式直接在 P/N 之间提供约 100 Ω 阻抗。它对差分信号形成终端，但对 P、N 同方向变化的共模信号基本不起作用。

### 接地型 Termination

```text
RX_P ───────+──── RX input
            |
           50Ω
            |
           GND

RX_N ───────+──── RX input
            |
           50Ω
            |
           GND
```

从差分路径看，两只 50 Ω 串起来仍约等于 100 Ω；与此同时，每根线相对于地都有明确的终端路径。

> “PHY Rterm 默认端接方式是跨接形式，应该配置成接地（AC 耦合）”通常是在描述某个具体 PHY IP 的 termination 配置要求，并不是说所有 PCIe PHY 的 RX termination 都必须物理连接到 GND。
{: .prompt-info }

## 3. VCM 是什么

**VCM（Common-Mode Voltage）**是差分接收器的共模电压，也就是 P/N 两根线共同的直流工作点：

```text
VCM   = (VP + VN) / 2
VDIFF = VP - VN

VP = VCM + VDIFF/2
VN = VCM - VDIFF/2
```

可以把差分信号理解为 P/N 围绕 VCM 一上一下变化。VCM 决定 RX 前端的直流工作点，而真正承载数据的是 P/N 之间的差分电压。

## 4. 为什么 AC Coupling 和 VCM 有关系

PCIe 链路使用 AC coupling capacitor。电容允许高速变化的交流分量通过，但隔离 TX 和 RX 两侧的直流共模电压：

```text
TX_P ──||──────────────── RX_P
        AC cap

TX_N ──||──────────────── RX_N
        AC cap

TX common-mode  ──X──  RX common-mode
                  ↑
             DC 被隔离
```

因此 TX 可以工作在自己的 common-mode voltage，而 RX PHY 需要在接收端建立自己的直流工作条件。不同 PHY 的内部实现可能使用 VCM-referenced termination、ground-referenced termination、MOS termination 或其他可校准网络。

## 5. Rterm 为什么需要 Calibration

片上电阻会受到 Process、Voltage、Temperature（PVT）的影响。如果目标是约 50 Ω，实际裸电阻可能发生明显漂移。因此 SerDes PHY 通常会进行 impedance / Rterm calibration。

```text
reference
    |
    v
impedance calibration
    |
    +── TX impedance trim
    |
    +── RX Rterm trim
```

PHY 内部可以通过可开关的电阻或 MOS 单元调整等效阻抗，所以寄存器中常见 `RTERM_EN`、`RTERM_CAL`、`RTERM_CODE`、`RTERM_TRIM`、`ZCAL` 等字段。

## 6. Rterm 与 PCIe Receiver Detect

Rterm 不只用于正常高速传输时的阻抗匹配，它还和 PCIe 的 **Receiver Detect** 密切相关。TX 在 Detect 阶段通过线路的电气响应判断对端是否存在 Receiver termination。

```text
存在 RX：
TX ───────── channel ───────── RX Rterm
                ↓
         检测到预期负载
                ↓
        Receiver Present

不存在 RX：
TX ───────── channel ───────── OPEN
                ↓
        电气响应明显不同
                ↓
      Receiver Not Present
```

因此 Receiver Detect 从物理层角度并不是在识别“对面有没有 PCIe 协议设备”，而是在判断该 Lane 对端是否呈现符合预期的接收端电气特征。

## 7. 对掉 Lane 问题的意义

如果某条 Lane 的 RX termination 没有正确使能、Rterm mode 配置错误、calibration 异常，或者通道本身存在连接问题，对端 TX 做 Receiver Detect 时就可能检测不到这条 Lane。

```text
RX Rterm / 通道异常
        ↓
对端 Receiver Detect 异常
        ↓
该 Lane 被认为不存在
        ↓
链路可能以更窄宽度训练
```

因此对于“设计为 x16，但实际只能训练到 x2/x4；插入协议分析仪后现象发生变化”这类问题，Rterm、RX termination calibration、Receiver Detect、电气连接以及 PCB 通道都值得重点检查。

## 8. 一句话总结

**Rterm** 解决接收端阻抗匹配并参与 Receiver Detect；**VCM** 提供 RX 的共模直流工作点；**AC coupling** 隔离 TX/RX 两侧的直流共模，使双方可以建立各自的 bias；而 PHY 的 **Rterm mode / calibration** 决定实际接收端终端网络如何工作。
