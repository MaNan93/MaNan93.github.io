---
title: PCIe 6 Flit Mode TLP：Header Base、OHC 与 NFM/FM 转换
date: 2026-09-16 14:40:00 +0800
categories: [PCIe, Protocol]
tags: [PCIe, PCIe 6.0, Flit Mode, TLP, OHC, UIO]
permalink: /pcie6-flit-tlp-header-ohc-translation/
description: 从 PCIe 5.x Non-Flit Mode 的 Fmt+Type 出发，梳理 PCIe 6.0 Flit Mode TLP 的 Header Base、OHC、Trailer、Type[7:0] 编码，以及 NFM 与 FM 之间的转换关系。
toc: true
---

PCIe 6.0 引入 Flit Mode 后，最容易产生的误解之一，是把 **256B Flit** 当成对传统 128b/130b Block 的替代。

实际上两者不在同一层次：

- **128b/130b** 是 PHY encoding；
- **Flit Mode** 是一种 Data Stream Mode；
- **256B Flit** 是 Flit Mode 下固定长度的数据组织单元；
- **TLP** 仍然存在，但其 Header 编码方式发生了明显变化。

本文重点讨论 PCIe 6.0 Transaction Layer 中最重要的一组变化：

```text
Non-Flit Mode TLP
    Fmt + Type
    3DW/4DW Header
    optional Prefix
          │
          │  semantic translation
          ▼
Flit Mode TLP
    Type[7:0]
    Header Base
    + OHC
    + Payload
    + TLP Trailer
```

---

## 1. Flit Mode TLP 的基本组成

PCIe 6.0 对 Flit Mode TLP 的组织可以概括为：

```text
Flit Mode TLP

+----------------------------+
| Header Base                |
+----------------------------+
| OHC                        |  optional，0~7 DW
+----------------------------+
| Payload                    |  0~1024 DW
+----------------------------+
| TLP Trailer                |  optional
+----------------------------+
```

因此可以写成：

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
- **Payload Size**：取决于 TLP 类型及 Length；
- **TLP Trailer**：由 Trailer 相关指示决定是否存在。

一个 TLP 并不等于一个 Flit。TLP 会继续作为 byte stream 被 packing 到 256B Flit 中：

```text
TLP A | TLP B | TLP C(partial)
                │
                ▼
           256B Flit N

TLP C(rest) | TLP D | ...
                │
                ▼
           256B Flit N+1
```

因此：

- 一个 Flit 可以包含多个 TLP；
- 一个 TLP 也可以跨多个 Flit。

---

## 2. NFM 的 TLP Header：Fmt + Type

PCIe 5.x 及 PCIe 6.0 的 Non-Flit Mode 延续传统 TLP 编码：

```text
Fmt[2:0] + Type[4:0]
```

`Fmt` 主要描述 Header 长度及是否带 Data：

| Fmt | 含义 |
|---|---|
| `000b` | 3DW Header，No Data |
| `001b` | 4DW Header，No Data |
| `010b` | 3DW Header，With Data |
| `011b` | 4DW Header，With Data |
| `100b` | TLP Prefix |

例如 Memory Request：

```text
MRd32 : Fmt=000 Type=00000
MRd64 : Fmt=001 Type=00000
MWr32 : Fmt=010 Type=00000
MWr64 : Fmt=011 Type=00000
```

因此 NFM 中必须把 `Fmt + Type` 放在一起解析，才能完整知道这是什么 TLP。

---

## 3. FM 改成 fully-decoded Type[7:0]

到了 Flit Mode，PCIe 6.0 不再使用独立的 `Fmt[2:0] + Type[4:0]` 来决定 packet 类型，而是直接定义：

```text
Type[7:0]
```

并要求 Receiver 对这个字段进行完整解码。

可以把变化理解成：

```text
NFM
+---------+---------+
| Fmt[2:0]|Type[4:0]|
+---------+---------+
          │
          ▼
FM
+-------------------+
|     Type[7:0]     |
+-------------------+
```

绝大多数传统 TLP 的 FM Type 编码都能看到明显的历史连续性：原来的 `Fmt + Type` 组合值基本被保留下来。

例如：

```text
IORd

NFM:
Fmt  = 000
Type = 00010

000_00010 = 0x02

FM:
Type[7:0] = 0x02
```

```text
IOWr

NFM:
Fmt  = 010
Type = 00010

010_00010 = 0x42

FM:
Type[7:0] = 0x42
```

```text
CplD

NFM:
Fmt  = 010
Type = 01010

010_01010 = 0x4A

FM:
Type[7:0] = 0x4A
```

因此 FM 并不是毫无关联地重新设计 Type 数值，而是把原本由 `Fmt + Type` 联合表达的信息，展开到了一个 fully-decoded 的 8-bit Type 空间中。

---

## 4. 一个特殊例子：MRd32 为什么变成 0x03

传统 NFM 中：

```text
MRd32
Fmt  = 000
Type = 00000

=> 0x00
```

但 PCIe 6.0 Flit Mode 中：

```text
Type 0x00 = NOP
```

因此 `0x00` 已经不能继续表示 MRd32。

PCIe 6.0 将 32-bit Address Memory Read Request 重新编码为：

```text
MRd32 → Type = 0x03
```

这也是 Table 2-5 中一个非常典型的 Translation Rule：

```text
Requires change of Type field value
```

所以 MRd32 是理解 NFM/FM translation 很好的切入点：

```text
NFM MRd32 : 0x00
      │
      │ Type translation
      ▼
FM  MRd32 : 0x03
```

---

## 5. 常用 NFM ↔ FM Type 对照

下面按“事务语义”整理常用类型。这里的 NFM Byte0 指把 `Fmt[2:0]` 与 `Type[4:0]` 拼成 8-bit 后的值。

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

PCIe 6.0 Table 2-5 的 `Translation Rule = 1:1` 的含义是：

> 在 Non-Flit Mode 与 Flit Mode 之间转换时，该 TLP 的事务语义和行为不发生变化。

注意：这里的 **1:1 不是说 Header 二进制内容原样透传**。

它只是表示 transaction meaning 不变。

真正的 translator 仍然必须重新组织 Header 字段。

---

## 6. Header Base：不是固定长度 Header

Flit Mode 中每个 TLP 都有 Header Base，但 Header Base 并不是固定 3DW 或固定 4DW。

其大小由：

```text
Type[7:0]
```

直接决定。

典型情况包括：

| TLP | Header Base Size |
|---|---:|
| NOP | 1 DW |
| MRd32 / IORd / Config Request | 3 DW |
| MRd64 | 4 DW |
| Completion | 通常 3 DW |
| 其他 FM Type | 根据 Type 定义，可更长 |

所以 RTL parser 的顺序应该是：

```text
Type[7:0]
    ↓
lookup Header Base format / size
    ↓
读取 Header Base
    ↓
解析 OHC presence
    ↓
读取 OHC
    ↓
Payload / Trailer
```

而不是先假定所有 FM Header 都是 3DW 或 4DW。

---

## 7. Header Base 第一 DW 是统一的

虽然不同 Type 的 Header Base 后续字段不同，但所有普通 Flit Mode TLP 的 Header Base 第一 DW 都使用公共格式。

核心字段包括：

```text
Type
TC
OHC
TS
Attr
Length
```

因此第一 DW 完成两件事：

1. 告诉 Receiver 这是什么 TLP；
2. 给出继续解析 Header/OHC/Payload 所需要的基本信息。

后面的 Header Base 内容则由具体 Type 决定，例如：

```text
Memory Request
→ Requester ID / Tag / Address

Configuration Request
→ Requester ID / Tag / Destination ID / Register Number

Completion
→ Completer ID / Destination information / Tag / Byte Count / Lower Address

Message
→ Requester ID / Message Code / Message-specific content
```

因此更准确的说法不是“3DW Header Base 有哪些字段”，而是：

> **不同 TLP Type 对应不同 Header Base format；Header Base Size 只是这个 format 的一个属性。**

---

## 8. OHC：把附加 Header 信息模块化

OHC 全称：

```text
Orthogonal Header Content
```

它不是 UIO 专属，也不是某一种 TLP 专属。

OHC 的目的，是把并非每个 TLP 都需要的附加信息，从固定 Header Base 中拆出来。

可以理解成：

```text
Header Base
    │
    ├── 所有该 Type 都需要的核心信息
    │
    └── OHC presence
             │
             ▼
            OHC
             │
             └── 按需携带扩展语义
```

PCIe 6.0 还把 NFM 中原本位于 End-to-End TLP Prefix 的一些内容重新组织进 OHC；PH、Steering Tag、AMA/AV 等信息也被重新整理。

所以：

```text
NFM
3DW/4DW Header
+ TLP Prefix
       │
       │ semantic re-encoding
       ▼
FM
Header Base
+ OHC
```

这里是**语义兼容**，不是 binary format 兼容。

---

## 9. Message 也有自己的 FM Header Base

Flit Mode 并不是只给 Memory Request 和 Completion 定义新的 Header。

Message TLP 同样根据自己的 `Type[7:0]` 使用对应的 Header Base format。

NFM Message 原本使用：

```text
Msg / MsgD
+ routing r[2:0]
+ Message Code
+ Requester ID
+ message-specific fields
```

到了 FM：

```text
Type[7:0]
    ↓
选择对应 Message Header Base
    ↓
Message Code / Requester information / routing information
    ↓
必要时继续带 OHC
    ↓
Payload（若该 Message 有 Data）
```

因此所有传统 transaction 都遵循同一个 FM 框架：

```text
Type
  ↓
Header Base
  ↓
OHC
  ↓
Payload
  ↓
Trailer
```

---

## 10. UIO 与 Header Base / OHC 的关系

UIO 是另一层概念。

它不是 OHC，也不是 Flit 本身，而是 PCIe 6.x Flit Mode 下新增的一组 transaction semantics。

可以把关系画成：

```text
Transaction Layer
│
├── traditional PCIe transactions
│     ├── MRd/MWr
│     ├── Cpl
│     ├── Cfg
│     └── Message
│
└── UIO transactions
      │
      └── new ordering semantics

所有 Flit Mode TLP
        │
        ▼
 Type[7:0]
 Header Base
 + OHC
 + Payload
 + Trailer
```

所以：

- **TLP**：事务 packet；
- **UIO**：定义 transaction/ordering semantics；
- **Header Base**：该 Type 的核心 Header；
- **OHC**：按需添加的附加 Header 信息；
- **Flit**：承载这些 TLP 的 256B Data Stream 单元。

另外，一些只存在于 Flit Mode 的新 TLP Type 没有 NFM 对应形式。这类 TLP 如果需要从 FM Egress 转到 NFM Link，协议会规定无法 translation，并触发相应的 **TLP Translation Egress Blocked** 处理。

---

## 11. NFM → FM Translator 真正需要做什么

看到很多 Type 都是 1:1，很容易误以为 translator 只需要改 Type。

实际上远不止如此。

完整转换逻辑更接近：

```text
NFM TLP
   │
   ├─ Fmt + Type
   ├─ Header fields
   ├─ Prefix
   ├─ Payload
   └─ Digest
          │
          ▼
    semantic decode
          │
          ▼
FM TLP
   │
   ├─ Type[7:0]
   ├─ Header Base
   ├─ OHC
   ├─ Payload
   └─ Trailer
```

RTL 上至少需要完成：

```text
1. Fmt + Type → FM Type[7:0]
2. 根据 transaction semantics 重新生成 Header Base
3. 将 NFM Prefix / 扩展信息转换到对应 OHC
4. 重新组织 Tag、Address、Requester/Completer ID 等字段
5. 处理 FM only 类型是否允许进入 NFM Egress
```

因此：

> **FM/NFM Translation 是语义级的 Header Translation，不是字节级 Header passthrough。**

---

## 12. 从设计角度最值得记住的模型

整个 PCIe 6.0 TLP 体系可以压缩成下面这张图：

```text
                 Transaction semantics
                         │
          ┌──────────────┴──────────────┐
          │                             │
         NFM                           FM
          │                             │
     Fmt + Type                     Type[7:0]
          │                             │
   3DW/4DW Header                  Header Base
   + Prefix                        + OHC
          │                             │
          └──── semantic translation ──┘
                                        │
                                        ▼
                                  TLP byte stream
                                        │
                                        ▼
                                  packed into
                                   256B Flit
                                        │
                                        ▼
                                  PHY encoding
```

从这里也能看出：

```text
256B Flit
≠ 128b/130b Block
```

二者处在不同层次。

Flit Mode 甚至可以工作在采用 NRZ / 128b/130b PHY encoding 的较低速率下，这正说明 Flit Mode 是 Data Stream/TLP 组织机制，而不是 PHY encoding 本身。

---

## 总结

PCIe 6.0 Flit Mode 对 TLP 的核心变化可以归纳为：

1. **TLP 没有消失。**
2. NFM 使用 `Fmt[2:0] + Type[4:0]`；FM 使用 fully-decoded `Type[7:0]`。
3. FM 的 `Type[7:0]` 同时决定 TLP 类型以及对应 Header Base format/size。
4. Header Base 不是固定长度；不同 Type 使用不同的 Header Base。
5. OHC 用来按需携带扩展 Header 信息，可以为 0 DW。
6. NFM 的 Header/Prefix 信息在 FM 中被**重新编码和重新组织**，而不是原样放置。
7. `Translation Rule = 1:1` 表示事务语义不变，不表示 Header binary format 不变。
8. MRd32 是一个典型例外：NFM `0x00` 到 FM 必须改成 `0x03`，因为 FM `0x00` 被 NOP 使用。
9. UIO 是新的 transaction/ordering semantics；UIO TLP 仍然使用 FM 的 Type + Header Base + OHC 框架。
10. 完整 FM TLP 大小可以理解为：

```text
TLP Size
=
Header Base
+ OHC
+ Payload
+ TLP Trailer
```

对于 Controller / Switch RTL，实现上最重要的思维方式是：

> **先解码 transaction semantics，再生成目标 Data Stream Mode 对应的 Header；不要把 NFM↔FM Translation 理解成简单的 Header 字节搬运。**

### 协议参考

- PCI Express Base Specification Revision 5.0：Section 2.2，Non-Flit Mode `Fmt[2:0] + Type[4:0]` TLP encoding。
- PCI Express Base Specification Revision 6.0：Section 2.2.1.2，Flit Mode common packet header fields。
- PCI Express Base Specification Revision 6.0：Table 2-5，Flit Mode TLP Header Type Encodings / Translation Rule。
- PCI Express Base Specification Revision 6.0：Section 2.2.7.2，Flit Mode Header Base formats。
