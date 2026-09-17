---
title: PCIe 6 Flit Mode TLP：Header Base、OHC 与 NFM/FM 转换
date: 2026-09-16 14:40:00 +0800
categories: [PCIe, Protocol]
tags: [PCIe, PCIe 6.0, PCIe 6.2, Flit Mode, TLP, OHC, UIO]
permalink: /pcie6-flit-tlp-header-ohc-translation/
description: 从 PCIe 5.x Non-Flit Mode 的 Fmt+Type 出发，梳理 PCIe 6.x Flit Mode TLP 的 Header Base、OHC、Trailer、Type[7:0] 编码、NFM/FM 转换关系，以及 PCIe 6.2 UIO。
toc: true
---

PCIe 6.0 引入 Flit Mode 后，TLP 并没有消失；真正发生变化的是 **TLP Header 的组织方式**。

最重要的主线是：

```text
Non-Flit Mode
Fmt[2:0] + Type[4:0]
3DW / 4DW Header
optional TLP Prefix
        │
        │ semantic translation
        ▼
Flit Mode
Type[7:0]
Header Base
+ OHC
+ Payload
+ TLP Trailer
```

本文重点不是只看编码表，而是理解 **NFM TLP 到 FM TLP 的字段重组**：哪些字段保留、哪些字段扩展、哪些字段从固定 Header 中移入 OHC，以及不同 TLP family 的 Header Base 怎么变化。文末另外加入 PCIe 6.2 的 UIO，作为 Flit-only 新事务单独讨论。

### 先看 NFM 与 FM 到底改了什么

如果先不看具体 bit，NFM 与 FM 的差异可以概括成下面几项：

| 维度 | Non-Flit Mode | Flit Mode |
|---|---|---|
| TLP 类型编码 | `Fmt[2:0] + Type[4:0]` | fully-decoded `Type[7:0]` |
| Header 组织 | 固定 3DW / 4DW Header | `Header Base + OHC` |
| 可选附加信息 | TLP Prefix / 固定 Header 中预留字段 | OHC-A/B/C/E 按需出现 |
| Header 长度来源 | `Fmt` 明确区分 3DW / 4DW | 由 `Type[7:0]` 直接决定 Header Base format/size |
| Byte Enable | Memory/I/O/Config Request 的固定 Header 字段 | 根据 TLP family 移入对应 OHC-A |
| Tag | `Tag[7:0]`，再由 `T8/T9` 扩展 | Header Base 中连续的 `Tag[13:0]` |
| Address Type | NFM DW0 中的 `AT[1:0]` | Memory/Atomic 中移到最后一个 Address DWORD `[1:0]` |
| TPH / PASID / IDE 等 | Header / Prefix 中分散表达 | 按用途拆到 OHC-A/B/C |
| ECRC / Trailer | `TD` 指示 TLP Digest | `TS[2:0]` 描述 FM Trailer |
| 新事务扩展 | 受传统 Fmt/Type 结构约束 | 可直接定义新的 FM Type，例如 PCIe 6.2 UIO |

因此，PCIe 6 的核心变化不是“把 3DW/4DW 换成另一套固定 Header”，而是把传统 Header 拆成两层：

```text
Header Base
= 当前 transaction 必须具备的核心字段

OHC
= 只有在对应 feature / condition 存在时才携带的附加 Header 内容
```

后面的 `Type[7:0]`、OHC-A1~A5、OHC-B/C、NFM↔FM translation，其实都可以沿着这条主线理解。

---

## 1. Flit Mode TLP 的组成

一个 Flit Mode TLP 可以写成：

```text
TLP Size
=
Header Base Size
+ OHC Size
+ Payload Size
+ TLP Trailer Size
```

其中：

- **Header Base Size**：由 `Type[7:0]` 决定；
- **OHC Size**：可以为 0；
- **Payload Size**：由 TLP 类型和 `Length` 决定；
- **TLP Trailer**：按 `TS[2:0]` 等规则决定是否存在及长度。

需要注意：**TLP size 与 256B Flit size 是两个概念。** 一个 Flit 可以包含多个 TLP，一个 TLP 也可以跨多个 Flit。

---

## 2. NFM：Fmt + Type

PCIe 5.x 的传统 Non-Flit Mode 使用：

```text
Fmt[2:0] + Type[4:0]
```

`Fmt` 同时告诉 Receiver Header 长度以及是否带 Data：

| Fmt | 含义 |
|---|---|
| `000b` | 3DW Header，No Data |
| `001b` | 4DW Header，No Data |
| `010b` | 3DW Header，With Data |
| `011b` | 4DW Header，With Data |
| `100b` | TLP Prefix |

例如：

```text
MRd32 : 000_00000 = 0x00
MRd64 : 001_00000 = 0x20
MWr32 : 010_00000 = 0x40
MWr64 : 011_00000 = 0x60
```

所以 NFM parser 必须联合解释 `Fmt + Type`。

---

## 3. FM：fully-decoded Type[7:0]

Flit Mode 取消独立的 `Fmt` 字段，改用：

```text
Type[7:0]
```

`Type[7:0]` 直接决定：

- transaction type；
- Header Base format；
- Header Base size；
- 是否带 Payload 等基本属性。

很多传统 TLP 的编码保留了历史连续性，例如：

```text
IOWr : NFM 010_00010 = 0x42
       FM  Type       = 0x42

CplD : NFM 010_01010 = 0x4A
       FM  Type       = 0x4A

MWr64: NFM 011_00000 = 0x60
       FM  Type       = 0x60
```

但并非所有类型都原值保留。最典型的是 `MRd32`：

```text
NFM MRd32 = 0x00
FM  0x00  = NOP
FM  MRd32 = 0x03
```

因此 PCIe 6.0 Table 2-5 对 MRd32 明确要求修改 Type field value。

---

## 4. 常用 NFM ↔ FM Type 对照

| Transaction | NFM Fmt | NFM Type | NFM Byte0 | FM Type[7:0] | Translation |
|---|---:|---:|---:|---:|---|
| MRd 32b | `000` | `00000` | `0x00` | `0x03` | Type 改编码 |
| MRd 64b | `001` | `00000` | `0x20` | `0x20` | 1:1 |
| MWr 32b | `010` | `00000` | `0x40` | `0x40` | 1:1 |
| MWr 64b | `011` | `00000` | `0x60` | `0x60` | 1:1 |
| MRdLk 32b | `000` | `00001` | `0x01` | `0x01` | 1:1 |
| MRdLk 64b | `001` | `00001` | `0x21` | `0x21` | 1:1 |
| IORd | `000` | `00010` | `0x02` | `0x02` | 1:1 |
| IOWr | `010` | `00010` | `0x42` | `0x42` | 1:1 |
| CfgRd0 | `000` | `00100` | `0x04` | `0x04` | 1:1 |
| CfgWr0 | `010` | `00100` | `0x44` | `0x44` | 1:1 |
| CfgRd1 | `000` | `00101` | `0x05` | `0x05` | 1:1 |
| CfgWr1 | `010` | `00101` | `0x45` | `0x45` | 1:1 |
| Cpl | `000` | `01010` | `0x0A` | `0x0A` | 1:1 |
| CplD | `010` | `01010` | `0x4A` | `0x4A` | 1:1 |
| CplLk | `000` | `01011` | `0x0B` | `0x0B` | 1:1 |
| CplDLk | `010` | `01011` | `0x4B` | `0x4B` | 1:1 |
| FetchAdd 32b | `010` | `01100` | `0x4C` | `0x4C` | 1:1 |
| FetchAdd 64b | `011` | `01100` | `0x6C` | `0x6C` | 1:1 |
| Swap 32b | `010` | `01101` | `0x4D` | `0x4D` | 1:1 |
| Swap 64b | `011` | `01101` | `0x6D` | `0x6D` | 1:1 |
| CAS 32b | `010` | `01110` | `0x4E` | `0x4E` | 1:1 |
| CAS 64b | `011` | `01110` | `0x6E` | `0x6E` | 1:1 |
| Msg | `001` | `10rrr` | `0x30~0x37` | `0x30~0x37` | 1:1 for corresponding legacy Message routes |
| MsgD | `011` | `10rrr` | `0x70~0x77` | `0x70~0x77` | 1:1 for corresponding legacy Message routes |

这里的 `Translation Rule = 1:1` 指 **transaction meaning / behavior 保持一致**，不是说 Header bits 原样 passthrough。

---

## 5. 可点击的 NFM ↔ FM Header / OHC 字段对照

下面这块不是静态图片，而是一个可交互的 bit-field explorer：

- 下拉框分为 **PCIe 6.0 baseline** 与 **PCIe 6.2 UIO (Flit-only)** 两组；
- 可以切换 MRd/MWr、I/O、Configuration、Completion、AtomicOp、Message，以及 UIO 五种新 TLP；
- **上方显示 NFM，下方显示 FM**；UIO 没有 NFM 编码，因此会明确显示 Flit-only；
- 每个 Header/OHC 表只保留一行 `31...0` bit ruler，下面连续排列各 DWORD；
- 字段宽度按实际 bit 数显示；
- **点击字段**会显示 bit 范围与字段含义；
- FM 中协议要求必须携带的 OHC 会直接跟在 Header Base 后面显示；
- 条件式 OHC 则列在下方 `Conditional OHC` 区域。

{% include pcie-nfm-fm-explorer.html %}

### 5.1 如何读这张交互表

例如选择 `MWr64`：

- NFM 中 `Fmt=011 + Type=00000`；
- FM 中直接变成 `Type[7:0]=0x60`；
- NFM 的 Tag 由 `Tag[7:0] + T8 + T9` 组成；
- FM Header Base 直接给出 `Tag[13:0]`；
- NFM 固定放在 Header 里的 First/Last DW Byte Enable，在 FM 中若需要显式携带，会进入 `OHC-A1`；
- NFM DW0 的 `AT[1:0]` 在 FM Memory/Atomic address routing 中移动到最后一个 Address DWORD 的 `[1:0]`；
- TPH 相关 `PH/ST` 信息放入 `OHC-B`；
- IDE / Requester Segment 相关信息使用 `OHC-C`。

I/O Request 是一个容易混淆的例外：FM I/O Header Base 的地址 DWORD 是 `Address[31:2] + Reserved[1:0]`，并不是 Memory Request 的 `Address[31:2] + AT[1:0]`；同时 `OHC-A2` 必须存在。

Configuration Request 也重新整理了字段：NFM 中拆开的 Extended Register Number / Register Number，在 FM Header Base 中形成连续的 Register Number；`OHC-A3` 必须存在，用于 Byte Enable 以及 Destination Segment/DSV 等内容。

---

## 6. OHC 不是一个“统一固定格式”

OHC = **Orthogonal Header Content**。

`OHC[4:0] = 00000b` 表示没有 OHC。存在 OHC 时，`OHC[4:0]` 指示 Header Base 后面有哪些 OHC：

```text
OHC-A
OHC-B
OHC-C
OHC-E
```

多个 OHC 同时存在时，顺序固定为：

```text
Header Base
→ OHC-A
→ OHC-B
→ OHC-C
→ OHC-E
→ Payload
→ Trailer
```

其中 OHC-A 会根据 TLP family 采用不同格式：

- `OHC-A1`：Memory Requests、Translation Requests，以及 Address-Routed Message with PASID；可承载 Byte Enables、PASID、ER、PMR、NW 等；
- `OHC-A2`：I/O Requests，**必须存在**，First/Last DW Byte Enable 位于 OHC DWORD 的低 8 bit；
- `OHC-A3`：Configuration Requests，**必须存在**，承载 Byte Enables 与 Destination Segment/DSV；
- `OHC-A4`：ID-Routed Message 在需要 Destination Segment / PASID 时使用；
- `OHC-A5`：Completion 在协议规定的条件下使用，承载 Destination Segment、Completer Segment、Completion Status、`LA[1:0]` 等。

另外：

- `OHC-B` 用于 TLP Processing Hints，**只适用于 Memory Address Routed Request TLP**；
- `OHC-C` 用于 IDE 以及适用的 Requester Segment 信息；Configuration Request 仅在相应 IDE 条件下使用 OHC-C；
- `OHC-E1/E2/E4` 也是 FM OHC 体系的一部分，但当前交互表暂未展开其内部格式。

所以更准确的理解是：

```text
Header Base = 当前 TLP Type 的核心字段
OHC         = 与该事务正交、按需出现的附加 Header 信息
```

“可选 OHC”并不等于发送端可以任意省略：如果某个具体 TLP 类型或条件要求某种 OHC，那么发送端必须携带它。

---

## 7. Message 也遵循同一套 FM Header 机制

NFM Message 使用：

```text
Fmt + Type[4:0]
其中 Type 低 3 bit = routing r[2:0]
```

典型编码：

```text
Msg  : 001_10rrr = 0x30 ~ 0x37
MsgD : 011_10rrr = 0x70 ~ 0x77
```

FM 保留对应的 fully-decoded Type 编码，同时 Message Header Base 仍遵循 FM Header Base + OHC 的机制。

不同 routing / Message 语义会决定是否需要 `OHC-A1`、`OHC-A4` 或 `OHC-C`。需要特别注意：`OHC-B` 是 TPH 内容，只适用于 Memory Address Routed Request，不是普通 Message 的通用可选 OHC。

---

## 8. PCIe 6.2 UIO：Flit-only 的新增事务

UIO（Unordered I/O）不是 PCIe 6.0 baseline TLP 的普通 1:1 translation。它最初通过 UIO ECN 引入，随后并入 PCIe 6.2 Base Specification，并且只定义在 **Flit Mode**。

PCIe 6.2 定义了 5 个 UIO TLP 类型：

| UIO TLP | FM Type[7:0] | 作用 |
|---|---:|---|
| `UIOMRd` | `0x22` | UIO Memory Read |
| `UIOMWr` | `0x61` | UIO Memory Write |
| `UIOWrCpl` | `0x0C` | UIOMWr 的 Completion |
| `UIORdCpl` | `0x0D` | UIO Read Completion without Data |
| `UIORdCplD` | `0x48` | UIO Read Completion with Data |

它们和传统 MRd/MWr 最大的区别之一是：

```text
UIO TLP
→ Flit Mode only
→ 没有对应的 NFM TLP encoding
→ 不能直接按普通 NFM translation 转出去
```

因此交互表把 UIO 单独放在 `PCIe 6.2 UIO (Flit-only)` 分组，而不是混在 PCIe 6.0 的 NFM↔FM 对照里。

另外一个容易误解的点是 `UIOMWr`：它虽然是 Write，并使用相应的 Posted-request flow-control 类别，但事务语义上会得到 `UIOWrCpl`。UIO 的 ordering model 也与传统 PCIe ordering 不同，主要目的是允许源端管理必要的顺序关系，而不是依赖 fabric 对不同路径强制维持传统顺序。

UIO 的 Transaction ID 规则也单独成组：UIOWrCpl 对应的 Group II，以及 UIORdCpl/UIORdCplD 对应的 Group III，都把 `TC + Requester ID + Tag` 纳入相应的事务匹配语义。

---

## 9. 从 RTL Translator 的角度看

传统 NFM → FM translator 至少要做：

```text
1. decode NFM Fmt + Type
2. recover transaction semantics
3. map to FM Type[7:0]
4. regenerate FM Header Base
5. move / expand fields into OHC when required
6. preserve payload semantics
7. generate FM trailer-related information
```

反方向同理：

```text
FM Type + Header Base + OHC
        ↓
semantic decode
        ↓
NFM Fmt + Type + Header / Prefix
```

但 UIO 是一个重要边界条件：它是 Flit-only transaction，不能简单经过上述逆向路径生成一个“等价 NFM UIO TLP”。

因此最重要的一句话仍然是：

> **NFM/FM Translation 是 transaction-semantic translation，不是 Header bits 的简单搬运。**

---

## 10. 总结

1. NFM 使用 `Fmt[2:0] + Type[4:0]`；FM 使用 fully-decoded `Type[7:0]`。
2. FM 的 Type 同时决定 Header Base format 和 size。
3. `Translation Rule = 1:1` 表示事务语义保持不变，不表示 Header binary layout 不变。
4. Memory、I/O、Configuration、Completion、AtomicOp、Message 都可以在交互表中直接对照；PCIe 6.2 UIO 单独作为 Flit-only 分组。
5. FM Tag 可直接扩展到 14 bit。
6. Memory/Atomic Request 的 `AT` 从 NFM DW0 移到 FM 最后一个 Address DWORD 的 `[1:0]`；I/O 对应低 2 bit 为 Reserved。
7. Byte Enable、PASID、Segment、Completion Status、PH/ST、IDE 等附加信息会根据 TLP family 进入不同 OHC。
8. OHC-A 不是一个固定格式，而是 A1~A5 按 TLP family 分工；协议要求 mandatory 的 OHC 必须携带。
9. UIO 定义了 UIOMRd、UIOMWr 和三种 UIO Completion，没有直接 NFM 编码。
10. 完整 FM TLP 大小仍然是：

```text
Header Base + OHC + Payload + TLP Trailer
```

### 协议参考

- PCI Express Base Specification Revision 5.0：Section 2.2，NFM TLP Header、Memory/I/O/Configuration/Message/Completion Header formats。
- PCI Express Base Specification Revision 6.0：Flit Mode First DW、OHC-A1~A5/OHC-B/OHC-C、Memory/I/O/Configuration/Message/Completion Header Base 与 NFM/FM translation rules。
- PCI Express Unordered IO (UIO) ECN；PCI Express Base Specification Revision 6.2：UIO TLP types、Transaction ID groups、Flit-only / egress handling rules。
