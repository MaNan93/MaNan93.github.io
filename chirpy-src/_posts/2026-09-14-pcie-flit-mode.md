---
title: PCIe Flit Mode：能力、声明与协商
date: 2026-09-14 10:50:00 +0800
categories: [PCIe, Protocol]
tags: [PCIe, Flit Mode, LTSSM, Gen6]
permalink: /pcie-flit-mode/
description: 梳理 PCIe Flit Mode 的 Component Capability、TS Advertisement、Flit_Mode_Enabled 协商结果，以及它与 64 GT/s、L0s/L0p 的区别。
toc: true
---

PCIe 6.x 里，**Flit Mode** 很容易和 **Gen6 / 64 GT/s** 混在一起理解。

最重要的结论先放在前面：

> **Flit Mode 是 Data Stream Mode；64 GT/s 是 Data Rate。两者是两个不同维度。**

它们之间只有单向关系：

```text
64 GT/s  ─────►  Flit Mode mandatory

Flit Mode  ──X─►  不代表一定支持 64 GT/s
```

因此，一个按照 PCIe 6.x 协议设计、最高只支持 **32 GT/s** 的 Component，也可以实现并协商到 Flit Mode。

---

## 1. 先把五个 Flit Mode 术语分清楚

PCIe Base Specification 中有一个专门的 Implementation Note，用来区分全文中几个容易混淆的 Flit Mode 标识。

| 名称 | 性质 | 位置 | 含义 |
|---|---|---|---|
| **Flit Mode Supported** | Capability | PCI Express Capabilities Register | Component 是否具备 Flit Mode 能力 |
| **Flit Mode Disable** | Control | Link Control Register | 是否禁止本次使用 Flit Mode |
| **Flit Mode Supported bit** | Advertisement | TS1/TS2 Data Rate Identifier | 在线路上向 Link Partner 声明本次训练可以使用 Flit Mode |
| **`Flit_Mode_Enabled`** | Internal Variable | 协议 / LTSSM 内部 | 双方 Flit Mode 的最终协商结果 |
| **Flit Mode Status** | Status | Link Status 2 Register | 软件可见的当前/即将采用的 Flit Mode 状态 |

其中最需要区分的是：

```text
Flit Mode Supported
        ≠
Flit_Mode_Enabled
```

前者回答：

> **“我有没有这个能力？”**

后者回答：

> **“这条 Link 本次训练最终是不是使用 Flit Mode？”**

---

## 2. Component Capability：Flit Mode Supported

`Flit Mode Supported` 是 Component 的能力位。

例如：

```text
Flit Mode Supported = 1
```

表示该 Component 的实现具备 Flit Data Stream Mode。

它只是静态能力，并不表示当前 Link 已经工作在 Flit Mode。

因此完全可能出现：

```text
Flit Mode Supported = 1
Flit_Mode_Enabled   = 0
```

即硬件支持 Flit Mode，但当前这次 Link Training 最终仍然使用 Non-Flit Mode。

---

## 3. Software Control：Flit Mode Disable

另一个重要量是：

```text
Flit Mode Disable
```

它是软件控制。

所以 Component 是否会在本次训练中通过 TS 对外声明 Flit Mode，取决于两个条件：

```text
Flit Mode Supported = 1
        AND
Flit Mode Disable   = 0
```

可以写成：

```text
TS.FlitModeSupported =
    Capability.FlitModeSupported && !FlitModeDisable
```

对应关系如下：

| Flit Mode Supported | Flit Mode Disable | TS Flit Mode Supported |
|---:|---:|---:|
| 0 | 0 | 0 |
| 0 | 1 | 0 |
| 1 | 1 | 0 |
| **1** | **0** | **1** |

因此：

> **Component 有 Flit Mode 能力，不代表一定会在当前训练中对外宣告。`Flit Mode Disable` 可以阻止它。**

---

## 4. Polling.Active：开始在 TS 中声明 Flit Mode 能力

初始 Link Training：

```text
Detect
  ↓
Polling.Active
```

进入 `Polling.Active` 后，Port 开始发送 TS1。

如果本端满足：

```text
Flit Mode Supported = 1
Flit Mode Disable   = 0
```

那么 TS1 的 Data Rate Identifier 中：

```text
Flit Mode Supported = 1
```

因此，**双方从 Polling 阶段就开始获知对端是否可以使用 Flit Mode。**

```text
           Port A                         Port B

       Polling.Active                 Polling.Active

TS1: Flit Mode Supported=1  ────────►
                             ◄────────  TS1: Flit Mode Supported=1

        A 知道 B 支持 Flit
        B 知道 A 支持 Flit
```

但此时一定要注意：

> **知道对端支持 Flit Mode，不等于 Flit Mode 已经协商完成。**

此时交换的只是 capability advertisement。

---

## 5. Polling.Configuration：继续交换 Flit Mode Supported

接下来 LTSSM 进入：

```text
Polling.Active
       ↓
Polling.Configuration
```

TS2 中继续携带相关的 Flit Mode Supported 信息。

因此可以把 Polling 阶段理解为：

```text
Polling.Active
    │
    └── TS1：开始交换 Flit Mode capability
             ↓
Polling.Configuration
    │
    └── TS2：继续交换 / 确认相关 capability
             ↓
Configuration
```

这里在线上传输的仍然是：

```text
Flit Mode Supported
```

不是：

```text
Flit_Mode_Enabled
```

前者是协商的输入，后者才是协商结果。

---

## 6. Configuration.Linkwidth.Accept：形成 `Flit_Mode_Enabled`

进入 Configuration 后：

```text
Configuration.Linkwidth.Start
             ↓
Configuration.Linkwidth.Accept
```

在这里，协议根据此前 Polling / Configuration 中双方交换的 Flit Mode 信息，形成内部变量：

```text
Flit_Mode_Enabled
```

它表示本次 Link Training 最终协商出的 Data Stream Mode。

可以把流程理解成：

```text
Local capability allows Flit
             +
Partner advertised Flit support
             │
             ↓
Configuration.Linkwidth.Accept
             │
             ↓
      Flit_Mode_Enabled
          1 / 0
             │
             ├── 1 → 本次 Link 使用 Flit Mode
             └── 0 → 本次 Link 使用 Non-Flit Mode
```

所以一句话概括：

> **Polling 是“我支持 Flit”；`Configuration.Linkwidth.Accept` 是形成“我们这条 Link 最终是否使用 Flit”的协商结果的关键阶段。**

---

## 7. Configuration.Complete：Flit Mode 已经完成协商

之后继续经过：

```text
Configuration.Linkwidth.Accept
             ↓
Configuration.Lanenum.*
             ↓
Configuration.Complete
```

到 `Configuration.Complete` 时，Flit Mode 已经是 negotiated 状态。

这正好解释了 64 GT/s capability 为什么要晚一些再暴露。

整个顺序是：

```text
Polling
  │
  │ TS Flit Mode Supported
  ↓
双方交换 Flit capability
  ↓
Configuration.Linkwidth.Accept
  │
  └── Flit_Mode_Enabled 确定
       ↓
Configuration.Complete
  │
  └── Flit Mode has been negotiated
       ↓
满足规范条件时：
Supported Link Speeds = 1_0111b
       ↓
表示支持 2.5 GT/s through 64.0 GT/s inclusive
```

需要特别注意：

```text
Supported Link Speeds = 1_0111b
```

表示的是 **64 GT/s capability**，并不表示当前 TS 正在 64 GT/s 上传输。

---

## 8. 为什么要先协商 Flit Mode，再声明 64 GT/s

因为 PCIe 6.x 的关系是：

```text
64 GT/s  →  Flit Mode mandatory
```

因此在普通 Initial Link Training 中，协议必须先解决：

> **双方这次训练到底是否成功进入 Flit Mode？**

然后才能进一步处理 64 GT/s capability。

于是逻辑顺序变成：

```text
先声明 Flit capability
        ↓
双方完成 Flit negotiation
        ↓
Flit_Mode_Enabled 确定
        ↓
再允许满足条件的 64G Component
声明 64 GT/s capability
```

而不是反过来。

---

## 9. Flit Mode 和 Gen6 / 64 GT/s 是两码事

这是理解 PCIe 6.x 最关键的一点之一。

### Data Rate

```text
2.5 / 5 / 8 / 16 / 32 / 64 GT/s ...
```

### Data Stream Mode

```text
Non-Flit Mode
Flit Mode
```

它们是两个不同维度。

关系是：

```text
64 GT/s  ⇒  Flit Mode
```

但：

```text
Flit Mode  ⇏  64 GT/s
```

所以一个 Component 完全可以是：

```text
PCIe 6.x protocol implementation
Max Data Rate = 32 GT/s
Flit Mode Supported = 1
```

然后通过训练得到：

```text
32 GT/s + Flit Mode
```

这并不矛盾。

---

## 10. L0s / L0p：最典型的例子

L0s / L0p 正好说明为什么不能把“PCIe 6.0 新增功能”直接理解成“64 GT/s 功能”。

更准确的分类是：

| Data Stream Mode | L0s | L0p |
|---|---:|---:|
| **Non-Flit Mode** | 可支持 | 不使用 |
| **Flit Mode** | 不支持 | 可支持 |

因此不能简单记成：

```text
Gen5 → L0s
Gen6 → L0p
```

更准确的是：

```text
Non-Flit Mode → L0s
Flit Mode     → L0p
```

例如一个最高只有 32 GT/s、但实现 PCIe 6.x Flit Mode 的设备：

```text
32 GT/s + Non-Flit
    → 可以使用传统 L0s

32 GT/s + Flit
    → 不使用 L0s
    → 可以支持 L0p
```

所以判断某个 PCIe 6.x feature 时，要先问：

> **它真正绑定的是 Flit Mode，还是某个 Data Rate？**

---

## 11. 完整控制链

把前面的内容压缩成一条链：

```text
Component Capability
Flit Mode Supported
        │
        ├──────────────┐
        │              │
        │       Flit Mode Disable
        │          Control
        │              │
        └──────┬───────┘
               ↓
     TS Flit Mode Supported
         Advertisement
               │
               │ Polling / Configuration
               │ 双方交换
               ↓
  Configuration.Linkwidth.Accept
               │
               ↓
       Flit_Mode_Enabled
      Negotiation Result
               │
               ↓
       Flit Mode Status
            Status
```

---

## 12. LTSSM 时间线速记

| 阶段 | Flit Mode 相关动作 |
|---|---|
| **Before Link Training** | `Flit Mode Supported` 表示硬件能力；`Flit Mode Disable` 表示软件策略 |
| **Polling.Active** | TS1 开始发送 `Flit Mode Supported`，双方开始获知对端能力 |
| **Polling.Configuration** | TS2 继续交换相关 Flit capability |
| **Configuration.Linkwidth.Accept** | 形成 `Flit_Mode_Enabled` 协商结果 |
| **Configuration.Complete** | Flit Mode 已 negotiated；满足规范条件时可以进一步宣告 64 GT/s capability |
| **后续 Link operation** | 依据 `Flit_Mode_Enabled` 使用对应的 Data Stream Mode 规则 |

---

## 总结

可以把 PCIe Flit Mode 的逻辑压缩成下面几句话：

1. **`Flit Mode Supported` 是 Component Capability。**
2. **`Flit Mode Disable` 是软件 Control。**
3. 当 `Supported=1 && Disable=0` 时，从 **Polling.Active** 开始发送的 TS1/TS2 可以把 `Flit Mode Supported` 置 1。
4. 双方从 Polling 阶段开始知道对端是否支持 Flit Mode。
5. **`Flit_Mode_Enabled` 是双方协商结果，不是 Capability。**
6. 这个结果在 Configuration 流程中形成，`Configuration.Linkwidth.Accept` 是关键阶段。
7. 到 `Configuration.Complete` 时 Flit Mode 已经完成协商，满足条件的 64 GT/s Component 才进一步宣告 64 GT/s capability。
8. **Flit Mode 与 Gen6 Data Rate 是两个独立维度：64 GT/s 强制要求 Flit Mode，但 Flit Mode 不要求 64 GT/s。**

对于 RTL / LTSSM 设计，最值得一直记住的是：

> **Capability → Control → TS Advertisement → Negotiation → `Flit_Mode_Enabled` → Status**

只要把这条链分清楚，后面看 PCIe 6.x 的 L0p、Recovery、速率切换、64 GT/s Equalization 等规则，就不容易把“Flit Mode 规则”和“64 GT/s 规则”混在一起。
