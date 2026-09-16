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

本文重点不是只看编码表，而是理解 **NFM TLP 到 FM TLP 的字段重组**：哪些字段保留、哪些字段扩展、哪些字段从固定 Header 中移出，以及 OHC 为什么会出现。

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

很多传统 TLP 的编码仍然保留了历史连续性，例如：

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

## 5. MWr64：NFM → FM 的字段重组

下面直接用渲染后的图对照 MWr64。左侧按 PCIe 5.0 Figure 2-17 的 NFM 字段语义绘制，右侧按 PCIe 6.0 Figure 2-39 的 FM Header Base 语义绘制。字段块宽度按 bit 数比例显示，因此可以直接观察字段在一个 DW 内的相对位置。

![MWr64 NFM to FM](/assets/img/posts/pcie6-mwr64-nfm-to-fm.svg)

从图上可以很直观地看到：

- NFM 的 `Fmt=011 + Type=00000` 在 FM 中收敛为 `Type[7:0]=0x60`；
- `Fmt` 不再单独存在，“4DW + with data”的语义由 FM Type 本身定义；
- NFM 的 Tag 是 `Tag[7:0] + T8 + T9`，FM Base Header 直接提供 `Tag[13:0]`；
- Requester ID 与 64-bit Address 的事务语义保留，但 Header 编码重新组织；
- NFM 中固定占据 DW1 的 Byte Enable，不再必须永久占用 FM Header Base，需要时由相应 OHC 携带；
- Prefix / overloaded header 一类的扩展信息，在 FM 中统一进入 OHC 体系。

所以：

> **NFM 和 FM 的 MWr64 虽然都可以是 4DW，但绝不是同一个 4DW Header format。**

`1:1 translation` 表示事务语义保持一致，而不是 128-bit Header 原样复制。

---

## 6. CplD：更容易看出 OHC 为什么存在

CplD 在两种模式里的编码都保持 `0x4A`，但 Completion Header 内部的字段组织变化很明显。

下面的图左侧按 PCIe 5.0 Figure 2-38，右侧按 PCIe 6.0 Figure 2-76 的字段语义绘制。

![CplD NFM to FM](/assets/img/posts/pcie6-cpld-nfm-to-fm.svg)

这里最值得注意的是：

- `Type=0x4A` 本身可以保持不变；
- Completer ID 仍然存在，但 Tag 扩展到 14 bit；
- NFM 里的 Requester ID，在 FM Completion Base Header 中以 Destination BDF / BF 的形式重新组织；
- Byte Count 和 Lower Address 重新排列；
- Completion Status、Lower Address 的额外位以及部分 segment-related 信息，在需要时由 `OHC-A5` 携带。

这正好说明 OHC 的作用：

```text
NFM Completion
固定 Header 携带核心字段 + 条件字段
        │
        │ semantic regrouping
        ▼
FM Completion
Header Base = 高频核心字段
OHC-A5      = 条件性 / 扩展 Completion 信息
```

所以 OHC 并不是简单“加长 Header”，而是在把 Header 信息模块化。

---

## 7. Header Base 不是按“3DW/4DW”定义类型

Flit Mode 中，真正决定格式的是 `Type[7:0]`。

```text
Type[7:0]
   │
   ├─ TLP semantics
   ├─ Header Base format
   ├─ Header Base size
   └─ Data payload property
```

所以 parser 更合理的处理方式是：

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

而不是先假设“这是 3DW 还是 4DW”，再去猜 TLP 类型。

---

## 8. OHC：不是 UIO 专属

OHC = **Orthogonal Header Content**。

它不是 UIO，也不是 UIO 专属扩展，而是 Flit Mode TLP Header 的通用机制。

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
+ Payload (when present)
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

> **NFM/FM Translation 是 transaction-semantic translation，不是 Header bits 的简单搬运。**

---

## 12. 总结

1. NFM 使用 `Fmt[2:0] + Type[4:0]`；FM 使用 fully-decoded `Type[7:0]`。
2. FM 的 Type 同时决定 Header Base format 和 size。
3. `Translation Rule = 1:1` 表示事务语义保持不变，不表示 Header binary layout 不变。
4. MWr64 虽然 NFM/FM 都可以是 4DW，但字段组织已经发生变化。
5. FM Tag 直接扩展到 14 bit。
6. Byte Enable 等信息不再必须永久占用 Base Header，需要时可通过 OHC 携带。
7. Completion 的变化更明显：FM 将核心 Completion 信息保留在 Base Header，把部分条件性扩展语义交给 OHC。
8. Message、AtomicOp、UIO 等最终都落在 `Type -> Header Base -> OHC -> Payload -> Trailer` 这套 FM TLP 框架中。
9. 256B Flit 是 Data Stream 组织单元，不是对 PHY 128b/130b block 的替代。

### 协议参考

- PCI Express Base Specification Revision 5.0：Section 2.2，Table 2-2 / Table 2-3，Figure 2-17，Figure 2-38。
- PCI Express Base Specification Revision 6.0：Table 2-5，Section 2.2.7.2，Figure 2-39，Figure 2-76，以及 OHC-A 相关定义。
