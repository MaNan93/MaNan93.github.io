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

本文重点不是只看编码表，而是把 **NFM TLP 到 FM TLP 的字段重组**画出来。这样可以直接看到：哪些字段保留、哪些字段扩展、哪些字段从固定 Header 中移出，以及 OHC 为什么会出现。

---

## 1. Flit Mode TLP 的组成

可以把一个 Flit Mode TLP 写成：

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

需要注意：**TLP size 与 256B Flit size 是两个概念。**

一个 Flit 可以包含多个 TLP，一个 TLP 也可以跨多个 Flit。

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

例如 Memory Request：

```text
MRd32 : 000_00000 = 0x00
MRd64 : 001_00000 = 0x20
MWr32 : 010_00000 = 0x40
MWr64 : 011_00000 = 0x60
```

因此 NFM parser 必须联合解释 `Fmt + Type`。

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

很多传统 TLP 的编码仍然保留了历史连续性。例如：

```text
IOWr : NFM 010_00010 = 0x42
       FM  Type       = 0x42

CplD : NFM 010_01010 = 0x4A
       FM  Type       = 0x4A

MWr64: NFM 011_00000 = 0x60
       FM  Type       = 0x60
```

但并非所有类型都能原值保留。最典型的是 `MRd32`：

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

这里的 `Translation Rule = 1:1` 指 **transaction meaning / behavior 保持一致**，不是说 Header bits 原样 passthrough。

---

## 5. MWr64：把 NFM 和 FM 放在 bit 位置上比较

这一组最适合观察 Header 的重组。

PCIe 5.0 Figure 2-17 中，64-bit Address Memory Request 的 NFM Header 是 4DW。MWr64 使用：

```text
Fmt  = 011b
Type = 00000b
Byte0 = 0x60
```

PCIe 6.0 Figure 2-39 中，Flit Mode Mem64 Request 同样是 4DW Header Base，但字段布局已经重新定义。

### 5.1 NFM MWr64 — PCIe 5.0 Figure 2-17

<div class="table-responsive">
<table class="table table-bordered text-center align-middle">
<thead><tr><th>DW / bit</th><th>31:29</th><th>28:24</th><th>23</th><th>22:20</th><th>19</th><th>18</th><th>17</th><th>16</th><th>15</th><th>14</th><th>13:12</th><th>11:10</th><th>9:0</th></tr></thead>
<tbody>
<tr><th>DW0</th><td>Fmt</td><td>Type</td><td>T9</td><td>TC</td><td>T8</td><td>Attr</td><td>LN</td><td>TH</td><td>TD</td><td>EP</td><td>Attr</td><td>AT</td><td>Length</td></tr>
</tbody>
</table>
</div>

<div class="table-responsive">
<table class="table table-bordered text-center align-middle">
<thead><tr><th>DW</th><th>31:16</th><th>15:8</th><th>7:4</th><th>3:0</th></tr></thead>
<tbody>
<tr><th>DW1</th><td>Requester ID</td><td>Tag[7:0]</td><td>Last DW BE</td><td>First DW BE</td></tr>
<tr><th>DW2</th><td colspan="4">Address[63:32]</td></tr>
<tr><th>DW3</th><td colspan="3">Address[31:2]</td><td>PH / low aligned bits</td></tr>
</tbody>
</table>
</div>

> NFM 中扩展 Tag 的高位通过 `T9/T8` 参与形成 Tag；图中固定 Header 还直接保留 Last/First DW Byte Enable。

### 5.2 FM MWr64 — PCIe 6.0 Figure 2-39

<div class="table-responsive">
<table class="table table-bordered text-center align-middle">
<thead><tr><th>DW / bit</th><th>31:24</th><th>23:21</th><th>20:16</th><th>15:13</th><th>12:10</th><th>9:0</th></tr></thead>
<tbody>
<tr><th>DW0</th><td>Type[7:0]</td><td>TC[2:0]</td><td>OHC[4:0]</td><td>TS[2:0]</td><td>Attr[2:0]</td><td>Length[9:0]</td></tr>
</tbody>
</table>
</div>

<div class="table-responsive">
<table class="table table-bordered text-center align-middle">
<thead><tr><th>DW</th><th>31:16</th><th>15</th><th>14</th><th>13:0</th></tr></thead>
<tbody>
<tr><th>DW1</th><td>Requester ID[15:0]</td><td>EP</td><td>R</td><td>Tag[13:0]</td></tr>
<tr><th>DW2</th><td colspan="4">Address[63:32]</td></tr>
<tr><th>DW3</th><td colspan="3">Address[31:2]</td><td>AT[1:0]</td></tr>
</tbody>
</table>
</div>

### 5.3 字段到底怎么变了

把两边直接对应起来：

| 语义 | NFM MWr64 | FM MWr64 |
|---|---|---|
| TLP 类型 | `Fmt=011 + Type=00000` | `Type[7:0]=0x60` |
| Header 长度 / with-data 信息 | `Fmt` 显式编码 | 由 `Type[7:0]` 对应的 FM type 定义 |
| Requester ID | Header 内 | Header Base 内 |
| Tag | `Tag[7:0] + T8 + T9`，最多 10-bit | Base Header 直接 `Tag[13:0]` |
| Byte Enable | 固定占用 DW1 | 默认值可隐含；需要特殊 BE 时由 OHC（例如 OHC-A1）携带 |
| Address | DW2/DW3 | 仍在 DW2/DW3，但 Header Base 重新编码 |
| AT | NFM common/request header 中 | FM DW3 `[1:0]` |
| Prefix / 扩展信息 | TLP Prefix / header overload | OHC |

因此 MWr64 是一个很好的例子：**表面上两边都是 4DW，但绝不是同一个 4DW Header format。**

```text
NFM 4DW Header
     │ semantic decode
     ▼
Memory Write + 64b Address + Payload
     │ regenerate
     ▼
FM 4DW Header Base + optional OHC
```

---

## 6. CplD：更容易看出 OHC 为什么存在

Completion with Data 的编码在两种模式中都保持 `0x4A`：

```text
NFM: Fmt=010, Type=01010 -> 0x4A
FM : Type[7:0]            -> 0x4A
```

但 Header 字段组织发生了明显变化。

### 6.1 NFM Completion — PCIe 5.0 Figure 2-38

<div class="table-responsive">
<table class="table table-bordered text-center align-middle">
<thead><tr><th>DW</th><th>31:16</th><th>15:13</th><th>12</th><th>11:0</th></tr></thead>
<tbody>
<tr><th>DW1</th><td>Completer ID</td><td>Completion Status</td><td>BCM</td><td>Byte Count</td></tr>
</tbody>
</table>
</div>

<div class="table-responsive">
<table class="table table-bordered text-center align-middle">
<thead><tr><th>DW</th><th>31:16</th><th>15:8</th><th>7</th><th>6:0</th></tr></thead>
<tbody>
<tr><th>DW2</th><td>Requester ID</td><td>Tag[7:0]</td><td>R</td><td>Lower Address[6:0]</td></tr>
</tbody>
</table>
</div>

NFM Completion Header 固定包含：

- Completer ID；
- Completion Status；
- BCM；
- Byte Count；
- Requester ID；
- Tag；
- Lower Address。

### 6.2 FM Completion Header Base — PCIe 6.0 Figure 2-76

<div class="table-responsive">
<table class="table table-bordered text-center align-middle">
<thead><tr><th>DW / bit</th><th>31:24</th><th>23:21</th><th>20:16</th><th>15:13</th><th>12:10</th><th>9:0</th></tr></thead>
<tbody>
<tr><th>DW0</th><td>Type</td><td>TC</td><td>OHC</td><td>TS</td><td>Attr</td><td>Length</td></tr>
</tbody>
</table>
</div>

<div class="table-responsive">
<table class="table table-bordered text-center align-middle">
<thead><tr><th>DW</th><th>31:16</th><th>15</th><th>14</th><th>13:0</th></tr></thead>
<tbody>
<tr><th>DW1</th><td>Completer ID</td><td>EP</td><td>LA[6]</td><td>Tag[13:0]</td></tr>
</tbody>
</table>
</div>

<div class="table-responsive">
<table class="table table-bordered text-center align-middle">
<thead><tr><th>DW</th><th>31:16</th><th>15:12</th><th>11:0</th></tr></thead>
<tbody>
<tr><th>DW2</th><td>Destination BDF / BF (ARI)</td><td>LA[5:2]</td><td>Byte Count[11:0]</td></tr>
</tbody>
</table>
</div>

这里最值得注意的是：FM Completion Header Base 不再简单照搬 NFM Completion Header。

例如一些 Completion 相关的附加信息按条件进入 **OHC-A5**。这样 Base Header 保留高频、核心字段，低频或扩展语义按需出现。

所以 CplD 更能说明：

```text
NFM:
固定 Header 承载更多字段

FM:
Header Base = core information
OHC         = conditional / orthogonal information
```

这就是 OHC 设计最直观的价值之一。

---

## 7. Header Base 不是按“3DW/4DW”定义类型

Flit Mode 中，真正决定格式的是 `Type[7:0]`。

因此更准确的关系是：

```text
Type[7:0]
   │
   ├─ TLP semantics
   ├─ Header Base format
   ├─ Header Base size
   └─ Data payload property
```

不同 Type 的 Header Base size 可以不同。常见传统事务里 3DW/4DW 很多，但 FM type space 还定义或预留了更长的 Header Base。

所以 parser 不应该写成：

```text
if 3DW ...
else if 4DW ...
```

更合理的是：

```text
Type[7:0]
   ↓
header-format lookup
   ↓
Header Base size / field decode
   ↓
OHC decode
   ↓
Payload / Trailer
```

---

## 8. OHC：不是 UIO 专属

OHC = **Orthogonal Header Content**。

它不是 UIO，也不是 UIO 专属扩展，而是 Flit Mode TLP Header 的通用机制。

可以把它理解成：

```text
Header Base
  = 当前 TLP Type 的核心字段

OHC
  = 按需出现的附加语义
```

NFM 中的一部分 Prefix / overloaded header 信息，在 FM 中被重新组织到 OHC 体系里。

所以 NFM ↔ FM 的兼容关系是：

```text
transaction semantic compatibility
```

而不是：

```text
binary header compatibility
```

---

## 9. Message 也有 FM Header Base

Message 并没有被排除在这套结构之外。

NFM Message：

```text
Fmt + Type(routing)
Requester ID
Message Code
message-specific fields
```

FM Message：

```text
Type[7:0]
Header Base
+ OHC (when required)
+ Payload (for MsgD-like semantics)
+ Trailer
```

所以从 FM parser 的角度，Memory / Configuration / Completion / Message / AtomicOp 等都遵循同一主线：

```text
Type -> Header Base -> OHC -> Payload -> Trailer
```

---

## 10. UIO 在哪里

UIO 是 transaction / ordering semantics 层面的能力，不等于 OHC。

```text
Flit Mode TLP framework
        │
        ├─ traditional PCIe transactions
        │    MRd / MWr / Cpl / Cfg / Msg ...
        │
        └─ UIO transactions
             new ordering semantics
```

UIO TLP 仍然使用 Flit Mode 的 Header Base / OHC 体系。

一些 FM-only TLP Type 没有 NFM 对应形式；当这些 TLP 试图经过 NFM Egress 时，协议可能要求阻断并报告对应的 TLP Translation Egress Blocked 条件。

---

## 11. 从 RTL Translator 的角度看

真正的 NFM → FM translator 至少要做：

```text
1. decode NFM Fmt + Type
2. recover transaction semantics
3. map to FM Type[7:0]
4. regenerate FM Header Base
5. move/expand fields into OHC when required
6. preserve payload semantics
7. generate FM trailer-related information
```

反方向也是一样：

```text
FM Type + Header Base + OHC
        ↓
semantic decode
        ↓
NFM Fmt + Type + Header/Prefix
```

因此最重要的一句话是：

> **NFM/FΜ Translation 是 transaction-semantic translation，不是 Header bits 的简单搬运。**

---

## 12. 总结

1. NFM 使用 `Fmt[2:0] + Type[4:0]`；FM 使用 fully-decoded `Type[7:0]`。
2. FM 的 Type 同时决定 Header Base format 和 size。
3. `Translation Rule = 1:1` 表示事务语义保持不变，不表示 Header binary layout 不变。
4. MWr64 虽然 NFM/FM 都是 4DW，但字段组织已经发生变化。
5. FM Tag 直接扩展到 14 bit。
6. Byte Enable 等信息不再必须永久占用 Base Header；需要时可通过 OHC 携带。
7. Completion 的变化更明显：FM 将核心 Completion 信息保留在 Base Header，把部分条件性扩展语义交给 OHC。
8. Message、AtomicOp、UIO 等最终都落在 `Type -> Header Base -> OHC -> Payload -> Trailer` 这套 FM TLP 框架中。
9. 256B Flit 是 Data Stream 组织单元，不是对 PHY 128b/130b block 的替代。

### 协议参考

- PCI Express Base Specification Revision 5.0：Section 2.2，Table 2-2 / Table 2-3，Figure 2-17，Figure 2-38。
- PCI Express Base Specification Revision 6.0：Table 2-5，Section 2.2.7.2，Figure 2-39，Figure 2-76，以及 OHC-A 相关定义。
