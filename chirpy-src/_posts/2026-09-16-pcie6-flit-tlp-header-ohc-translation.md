---
title: PCIe 6 Flit Mode TLP：Header Base、OHC 与 NFM/FM 转换
date: 2026-09-16 14:40:00 +0800
categories: [PCIe, Protocol]
tags: [PCIe, PCIe 6.0, Flit Mode, TLP, OHC, UIO]
permalink: /pcie6-flit-tlp-header-ohc-translation/
description: 从 PCIe 5.x Non-Flit Mode 的 Fmt+Type 出发，梳理 PCIe 6.0 Flit Mode TLP 的 Header Base、OHC、Trailer、Type[7:0] 编码，以及 NFM 与 FM 之间的转换关系。
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

本文重点不是只看编码表，而是理解 **NFM TLP 到 FM TLP 的字段重组**：哪些字段保留、哪些字段扩展、哪些字段从固定 Header 中移入 OHC，以及不同 TLP family 的 Header Base 怎么变化。

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

- 下拉框可以切换 MRd/MWr、I/O、Configuration、Completion、AtomicOp、Message；
- **上方显示 NFM，下方显示 FM**，更适合当前页面宽度；
- 每个 DW 都带 `31...0` bit ruler；
- 字段宽度按实际 bit 数显示；
- **点击字段**会显示 bit 范围与字段含义；
- 下方会自动列出该 TLP family 相关的 OHC；
- 点击 `OHC-A1/A2/A3/A4/A5/B/C` 可以继续看 OHC 内部字段。

{% include pcie-nfm-fm-explorer.html %}

### 5.1 如何读这张交互表

例如选择 `MWr64`：

- NFM 中 `Fmt=011 + Type=00000`；
- FM 中直接变成 `Type[7:0]=0x60`；
- NFM 的 Tag 由 `Tag[7:0] + T8 + T9` 组成；
- FM Header Base 直接给出 `Tag[13:0]`；
- NFM 固定放在 Header 里的 First/Last DW Byte Enable，在 FM 中若需要显式携带，会进入 `OHC-A1`；
- TPH 相关 `PH/ST` 信息则放入 `OHC-B`；
- IDE / Requester Segment 相关信息则使用 `OHC-C`。

再例如选择 `CplD`：

- `0x4A` 本身可以保持 1:1；
- Completion Header Base 重新组织；
- Tag 扩展为 14 bit；
- Completion Status、`LA[1:0]`、segment information 在需要显式携带时进入 `OHC-A5`。

这比单纯画一张 NFM → FM 静态图更适合查协议，因为可以直接点字段看语义。

---

## 6. OHC 不是一个“统一固定格式”

OHC = **Orthogonal Header Content**。

`OHC[4:0]` 指示 Header Base 后面存在哪些 OHC：

```text
OHC-A
OHC-B
OHC-C
OHC-E
```

多个 OHC 同时存在时，顺序为：

```text
Header Base
→ OHC-A
→ OHC-B
→ OHC-C
→ OHC-E
→ Payload
→ Trailer
```

其中 OHC-A 又会根据 TLP family 采用不同格式：

- `OHC-A1`：Memory Requests、Translation Requests，以及部分 Message 场景；主要承载 Byte Enables、PASID、ER、PMR、NW 等；
- `OHC-A2`：I/O Requests，**必须存在**，主要承载 First/Last DW Byte Enable；
- `OHC-A3`：Configuration Requests，**必须存在**，承载 Byte Enables 与 Destination Segment/DSV；
- `OHC-A4`：ID-Routed Message 在需要 Destination Segment / PASID 时使用；
- `OHC-A5`：Completion 在协议规定的条件下使用，承载 Destination Segment、Completer Segment、Completion Status、`LA[1:0]` 等。

另外：

- `OHC-B` 用于 TLP Processing Hints，包含 PH、Steering Tag、HV、AMA、AV；
- `OHC-C` 用于 IDE 以及部分 Segment 信息，包含 Requester Segment、Stream ID、Sub-Stream 等。

所以更准确的理解是：

```text
Header Base = 当前 TLP Type 的核心字段
OHC         = 与该事务正交、按需出现的附加 Header 信息
```

这也是为什么很多 NFM 字段到了 FM 后看起来“消失了”——它们往往只是从固定 Header 移到了 OHC。

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

FM 保留对应的 fully-decoded Type 编码，同时 Message Header Base 仍然是 4DW 类格式。

Message routing 仍由 `r[2:0]` 表达，例如 Routed to Root Complex、Routed by Address、Routed by ID、Broadcast、Local 等。不同 routing / Message 语义还会决定是否需要 `OHC-A1`、`OHC-A4`、`OHC-B` 或 `OHC-C`。

因此 Message 也不是例外：

```text
Type
→ Header Base
→ OHC
→ Payload（MsgD 等）
→ Trailer
```

---

## 8. 从 RTL Translator 的角度看

真正的 NFM → FM translator 至少要做：

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

因此最重要的一句话是：

> **NFM/FM Translation 是 transaction-semantic translation，不是 Header bits 的简单搬运。**

---

## 9. 总结

1. NFM 使用 `Fmt[2:0] + Type[4:0]`；FM 使用 fully-decoded `Type[7:0]`。
2. FM 的 Type 同时决定 Header Base format 和 size。
3. `Translation Rule = 1:1` 表示事务语义保持不变，不表示 Header binary layout 不变。
4. Memory、I/O、Configuration、Completion、AtomicOp、Message 都可以在交互表中直接对照 bit 位置。
5. FM Tag 可直接扩展到 14 bit。
6. Byte Enable、PASID、Segment、Completion Status、PH/ST、IDE 等附加信息会根据 TLP family 进入不同 OHC。
7. OHC-A 不是一个固定格式，而是 A1~A5 按 TLP family 分工。
8. Message 也使用 FM Header Base + OHC 框架，并保留 routing 语义。
9. 完整 FM TLP 大小仍然是：

```text
Header Base + OHC + Payload + TLP Trailer
```

### 协议参考

- PCI Express Base Specification Revision 5.0：Section 2.2，NFM TLP Header、Memory/I/O/Configuration/Message/Completion Header formats。
- PCI Express Base Specification Revision 6.0：Section 2.2.1.2、Table 2-5、Table 2-6、Figure 2-6 ~ Figure 2-13、Section 2.2.7.2，以及 Message / Completion 的 Flit Mode Header Base 定义。
