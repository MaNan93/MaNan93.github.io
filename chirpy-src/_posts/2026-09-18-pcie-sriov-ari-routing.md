---
title: PCIe SR-IOV 与 ARI：VF Routing ID、Bus Number 与 ARI Forwarding
date: 2026-09-18 13:50:00 +0800
categories: [PCIe, Virtualization]
tags: [PCIe, SR-IOV, ARI, VF, PF, Routing ID, Bus Number]
permalink: /pcie-sriov-ari-routing/
description: 梳理 SR-IOV 的 PF/VF Routing ID、First VF Offset/VF Stride、ARI Extended Capability、ARI Forwarding、ARI Capable Hierarchy，以及 Type 0/Type 1 Configuration Request 和 Bus Number 消耗之间的关系。
toc: true
---

SR-IOV 和 ARI 放在一起看时，最容易混淆的是下面三件事：

1. **ARI Extended Capability**
2. **ARI Forwarding**
3. **SR-IOV Control.ARI Capable Hierarchy**

它们不是同一个东西。

这篇文章从 Routing ID 出发，把 PF/VF 的地址生成、Configuration Request 类型、Bus Number 消耗，以及 ARI 的真正作用串起来。

---

## 1. 先把三个 ARI 概念分开

### ARI Extended Capability

这是 **ARI Device 内部 Function 自己实现的 Extended Capability**。

对于不在 Root Complex 内的 SR-IOV Device，PCIe 规范要求每个 Function 都实现 ARI Extended Capability。

它的主要内容包括：

- `Next Function Number`
- MFVC Function Group Capability / Enable
- ACS Function Group Capability / Enable
- Function Group

其中：

> `Next Function Number` 对 non-VF Function 有意义；对 VF 是 undefined，因为 VF 不是靠它发现的。

### ARI Forwarding

这是 **ARI Device 正上方 Root Port / Switch Downstream Port 的能力和开关**。

关键字段：

```text
Device Capabilities 2
  ARI Forwarding Supported

Device Control 2
  ARI Forwarding Enable
```

它决定 Downstream Port 是否允许访问 ARI Extended Function，也就是 Function Number > 7。

### SR-IOV Control.ARI Capable Hierarchy

这是 **最低编号 PF 的 SR-IOV Extended Capability 中的控制位**。

它是 Device 的一个 hint：

> 软件已经确认上一级 Root Port / Switch DSP 的 ARI Forwarding 已经开启。

规范要求软件让它与正上方 Downstream Port 的 `ARI Forwarding Enable` 匹配。

因此，后文统一使用下面的术语：

```text
ARI Extended Capability implemented
    = Function 实现了 ARI capability

ARI Forwarding Enable = 1
    = 上游 Root Port / DSP 真正开启 ARI forwarding

ARI Capable Hierarchy = 1
    = SR-IOV Device 按 ARI hierarchy 分配 VF RID
```

不要把这三件事都简称为“ARI enabled”。

---

## 2. Routing ID：ARI 没有增加位宽

PCIe Routing ID 仍然是 16 bit。

### 传统解释

```text
15             8 7             3 2       0
+---------------+---------------+---------+
|  Bus Number   | Device Number | Function|
+---------------+---------------+---------+
      8 bit          5 bit        3 bit
```

也就是：

```text
Bus[7:0] | Device[4:0] | Function[2:0]
```

### ARI 解释

ARI 把低 8 bit 合并为一个 Function Number：

```text
15             8 7                         0
+---------------+---------------------------+
|  Bus Number   |      Function Number      |
+---------------+---------------------------+
      8 bit                 8 bit
```

即：

```text
Bus[7:0] | Function[7:0]
```

例如：

```text
RID = 0x0325
```

传统解释：

```text
Bus      = 03
Device   = 04
Function = 5
```

ARI 解释：

```text
Bus      = 03
Function = 0x25 = 37
```

注意：在 ARI Device 中，Device Number 是 **implied 0**，不能把 `RID[7:3]` 再解释成真实 Device Number。

---

## 3. VF Routing ID 的核心公式

SR-IOV 中，VF 的位置不是靠 ARI `Next Function Number` 找出来的。

每个 PF 自己的 SR-IOV Extended Capability 中都有：

- `First VF Offset`
- `VF Stride`

它们都是 **16-bit Routing ID offset**。

公式为：

```text
VF1_RID = PF_RID + FirstVFOffset

VFn_RID = PF_RID
        + FirstVFOffset
        + (n - 1) * VFStride
```

所有运算都是 16-bit unsigned arithmetic，carry 丢弃。

例如：

```text
PF0 RID          = 0x0300
First VF Offset  = 0x0002
VF Stride        = 0x0002
```

那么：

```text
PF0.VF0 = 0x0302 -> 03:00.2
PF0.VF1 = 0x0304 -> 03:00.4
PF0.VF2 = 0x0306 -> 03:00.6
```

---

## 4. 不同 PF 的 First VF Offset 不要求相同

`First VF Offset` 和 `VF Stride` 都属于 **各自 PF 的 SR-IOV Capability**。

协议没有要求所有 PF 必须使用相同的值。

例如：

```text
PF0:
  First VF Offset = 4
  VF Stride       = 3

PF1:
  First VF Offset = 7
  VF Stride       = 5
```

都是可以的。

真正必须满足的是：

> 所有 PF 和 VF 最终计算出来的 16-bit Routing ID 必须唯一，不能发生重叠。

另外，最低编号 PF 的 `ARI Capable Hierarchy` 状态可以影响各 PF 返回的 `First VF Offset` / `VF Stride`。

---

## 5. 一个 2 PF 的同 Bus 例子

假设 captured Bus 是 03：

```text
03:00.0  PF0
03:00.1  PF1
```

希望 VF 交错排列：

```text
03:00.2  PF0.VF0
03:00.3  PF1.VF0
03:00.4  PF0.VF1
03:00.5  PF1.VF1
03:00.6  PF0.VF2
03:00.7  PF1.VF2
```

可以配置为：

```text
PF0 RID = 03:00.0
First VF Offset = 2
VF Stride       = 2

PF1 RID = 03:00.1
First VF Offset = 2
VF Stride       = 2
```

计算结果：

```text
PF0.VF0 = 03:00.2
PF1.VF0 = 03:00.3

PF0.VF1 = 03:00.4
PF1.VF1 = 03:00.5

PF0.VF2 = 03:00.6
PF1.VF2 = 03:00.7
```

这时传统一个 Device 的 8 个 Function 槽位已经全部用完。

---

## 6. Type 0 CFG 到达 EP 后，谁负责区分 PF / VF

对于直接挂在 Root Port / Switch DSP 后面的 Endpoint：

```text
Root Port / DSP
      |
      | PCIe Link
      v
      EP
```

在没有开启 ARI Forwarding 的传统配置路由下，Downstream Port 会先处理 Device Number。

对于这个 Link：

```text
Device = 0
    -> 可以向下游 Device 发出 Type 0 CFG

Device = 1~31
    -> Downstream Port 自己返回 UR
```

因此：

> 一个合法到达 EP 的 Type 0 Configuration Request，本质上已经是在访问这个 EP 内部某个 Function。

EP 真正需要 decode 的是：

```text
Function -> PF ?
         -> enabled VF ?
         -> unimplemented Function ?
```

例如：

```text
Function 0 -> PF0
Function 1 -> PF1
Function 2 -> PF0.VF0
Function 3 -> PF1.VF0
...
```

如果 Function 不存在，则按 Unsupported Request 处理。

---

## 7. PF 全部在 captured Bus，VF 可以去额外 Bus

PCIe SR-IOV 有一个重要规则：

> 所有 PF 必须位于 Device 的 captured Bus Number。

但 VF 可以位于额外 Bus Number。

因此完全可以设计成：

```text
Bus 03:
03:00.0  PF0
03:00.1  PF1
03:00.2  PF2
03:00.3  PF3

Bus 04 / 05 / 06 / ...:
只放 VF
```

一个非常直观的做法就是：

```text
First VF Offset = 0x0100
VF Stride       = 0x0100
```

注意这里是 `0x0100`，不是 `0x10000`。

因为字段本身只有 16 bit。

`0x0100` 的含义正好是：

```text
RID += 0x0100
    -> Bus Number + 1
    -> 低 8 bit DevFn 保持不变
```

---

## 8. 例子：每个 VF 单独占一个 Bus

假设：

```text
PF0 RID          = 03:00.0
First VF Offset  = 0x0100
VF Stride        = 0x0100
```

那么：

```text
PF0      = 03:00.0
PF0.VF0  = 04:00.0
PF0.VF1  = 05:00.0
PF0.VF2  = 06:00.0
PF0.VF3  = 07:00.0
...
```

从公式看：

```text
VF0 = 0x0300 + 0x0100 = 0x0400
VF1 = 0x0300 + 0x0100 + 0x0100 = 0x0500
VF2 = 0x0600
...
```

这种布局协议上是可行的。

但代价也非常明显：

> 一个 VF 就消耗一个额外 Bus Number。

如果一个 PF 有 64 个 VF，就可能快速吃掉几十个 Bus Number。

---

## 9. VF 跨 Bus 后，Configuration Request 不会被转成 Type 0

这是理解 SR-IOV 多 Bus 最关键的一点。

### captured Bus 上的 Function

例如：

```text
03:00.0 PF0
03:00.1 PF1
03:00.2 VF...
```

访问 Bus 03 时，上一级 Downstream Port可以把对应 Configuration Request 转成 Type 0：

```text
RC
 -> Type 1 CFG to Bus 03
 -> Root Port / DSP
 -> Type 0 CFG
 -> EP
```

### additional Bus 上的 VF

例如：

```text
04:00.0 PF0.VF0
```

访问它时：

```text
RC
 -> Type 1 CFG, Bus = 04
 -> Root Port / DSP
 -> 仍然作为 Type 1 CFG 向下转发
 -> SR-IOV Device
 -> 内部根据 VF RID 规则命中 VF
```

协议明确要求：

- captured Bus 上的 enabled VF 可以处理 Type 0 Configuration Request
- 不在 captured Bus 上的 enabled VF 必须能够处理针对它的 Type 1 Configuration Request

因此不能把 SR-IOV Endpoint 简化为“只处理 Type 0 CFG”。

---

## 10. EP 如何判断一个 Type 1 CFG 是不是自己的 VF

核心还是完整的 VF RID 算法。

对于每个 PF：

```text
VF_RID(n)
=
PF_RID
+ FirstVFOffset
+ n * VFStride
```

Device 可以根据：

- Target Bus
- Target Device/Function
- PF 的 Routing ID
- First VF Offset
- VF Stride
- NumVFs / VF Enable

判断请求是否命中某个 enabled VF。

如果命中：

```text
正常访问 VF Configuration Space
```

如果没有任何 enabled VF 对应这个 RID：

```text
UR
```

同时，针对 Device captured Bus 的 Type 1 Configuration Request 本身也不是正常的 PF/VF 访问路径，应按协议的 Unsupported Request 规则处理。

---

## 11. 为什么 ARI Forwarding 能显著节省 Bus Number

如果没有利用 ARI 8-bit Function Number 空间，一个 Bus 内传统 Function Number 只有：

```text
Function 0 ~ 7
```

当 PF/VF 数量很多时，VF 很容易被 First VF Offset / VF Stride 推到额外 Bus。

而当：

```text
上游 Root Port / DSP:
ARI Forwarding Enable = 1

最低编号 PF:
ARI Capable Hierarchy = 1
```

时，Device 可以把低 8 bit 当成：

```text
Function[7:0]
```

于是同一个 captured Bus 上可以容纳：

```text
Function 0 ~ 255
```

例如：

```text
Bus 03:
Function 0
Function 1
...
Function 255
```

只要 First VF Offset / VF Stride 的布局足够紧凑，大量 PF/VF 就可以共用同一个 Bus。

---

## 12. ARI Forwarding 的准确作用

ARI Forwarding 不是 Bus Number 路由功能。

Bus Number 的转发仍然由：

```text
Secondary Bus Number
Subordinate Bus Number
```

决定。

ARI Forwarding 真正改变的是：

> Downstream Port 在判断 Type 1 Configuration Request 是否可以转换成 Type 0 时，不再要求传统 Device Number 字段必须等于 0。

例如目标低 8 bit：

```text
0x25
```

传统解释：

```text
Device   = 4
Function = 5
```

如果 ARI Forwarding 没开，这种传统 Device Number 非 0 的访问不会被当成直连 Endpoint 的正常 Function 访问。

如果 ARI Forwarding 已开，则：

```text
0x25 -> ARI Function Number 37
```

此时 Device Number 不再单独存在，ARI Device 的 implied Device Number 仍然是 0。

---

## 13. ARI Extended Capability 到底有什么用

ARI Extended Capability 和 ARI Forwarding 不是一回事。

它主要提供两类功能。

### 13.1 non-VF Function 的快速枚举

ARI Device 的 Function Number 可以是 sparse / non-sequential：

```text
Function 0
Function 8
Function 32
Function 100
```

这时软件不必扫完 0~255。

可以利用：

```text
Next Function Number
```

形成链：

```text
F0 -> F8 -> F32 -> F100 -> End
```

这对多个 PF / 普通 non-VF Function 的枚举尤其有价值。

### 13.2 Function Group

ARI Capability / Control 还提供：

- MFVC Function Group
- ACS Function Group
- Function Group Number

这些机制可以同时适用于 PF 和 VF。

### VF 不靠 Next Function Number 枚举

VF 的发现依赖：

```text
First VF Offset
VF Stride
NumVFs
```

因此：

> ARI 的 8-bit Function Number 空间对 VF 很重要，但 ARI Capability 里的 `Next Function Number` 链表对 VF discovery 并不重要。

---

## 14. ARI Extended Capability Explorer

<div id="ari-cap-explorer" class="ari-cap-explorer">
  <div class="ari-explorer-top">
    <div>
      <div class="ari-explorer-name">ARI Extended Capability</div>
      <div class="ari-explorer-meta">ID <code>000Eh</code> · PCIe Base Spec 6.4 §7.8.8</div>
    </div>
    <div class="ari-tabs" role="tablist" aria-label="ARI register selector">
      <button type="button" class="ari-tab is-active" data-reg="cap" role="tab" aria-selected="true">Capability</button>
      <button type="button" class="ari-tab" data-reg="ctl" role="tab" aria-selected="false">Control</button>
    </div>
  </div>

  <div class="ari-register-head">
    <span id="ari-reg-name">ARI Capability Register</span>
    <code id="ari-reg-offset">+04h</code>
  </div>

  <div id="ari-cap-view" class="ari-register" aria-label="ARI Capability Register">
    <button type="button" class="ari-field ari-next" style="grid-column:1 / span 8" data-field="next-fn">
      <span class="ari-bits">15:8</span><span>Next Function Number</span>
    </button>
    <button type="button" class="ari-field ari-rsvd" style="grid-column:9 / span 6" data-field="cap-rsvd">
      <span class="ari-bits">7:2</span><span>Reserved</span>
    </button>
    <button type="button" class="ari-field ari-acs" style="grid-column:15" data-field="acs-cap">
      <span class="ari-bits">1</span><span>A</span>
    </button>
    <button type="button" class="ari-field ari-mfvc" style="grid-column:16" data-field="mfvc-cap">
      <span class="ari-bits">0</span><span>M</span>
    </button>
  </div>

  <div id="ari-ctl-view" class="ari-register" aria-label="ARI Control Register" hidden>
    <button type="button" class="ari-field ari-rsvd" style="grid-column:1 / span 9" data-field="ctl-rsvd-hi">
      <span class="ari-bits">15:7</span><span>Reserved</span>
    </button>
    <button type="button" class="ari-field ari-group" style="grid-column:10 / span 3" data-field="function-group">
      <span class="ari-bits">6:4</span><span>Function Group</span>
    </button>
    <button type="button" class="ari-field ari-rsvd" style="grid-column:13 / span 2" data-field="ctl-rsvd-mid">
      <span class="ari-bits">3:2</span><span>Rsvd</span>
    </button>
    <button type="button" class="ari-field ari-acs" style="grid-column:15" data-field="acs-en">
      <span class="ari-bits">1</span><span>A En</span>
    </button>
    <button type="button" class="ari-field ari-mfvc" style="grid-column:16" data-field="mfvc-en">
      <span class="ari-bits">0</span><span>M En</span>
    </button>
  </div>

  <div class="ari-legend">
    <span><i class="ari-dot ari-next-dot"></i>Function discovery</span>
    <span><i class="ari-dot ari-group-dot"></i>Function Group</span>
    <span><i class="ari-dot ari-acs-dot"></i>ACS</span>
    <span><i class="ari-dot ari-mfvc-dot"></i>MFVC</span>
  </div>

  <div class="ari-role-strip">
    <button type="button" data-topic="endpoint"><b>EP / PF</b><small>ARI Extended Capability</small></button>
    <span>→</span>
    <button type="button" data-topic="dsp"><b>Root Port / DSP</b><small>ARI Forwarding</small></button>
    <span>→</span>
    <button type="button" data-topic="usp"><b>Switch USP</b><small>normal upstream forwarding</small></button>
  </div>

  <div id="ari-tooltip" class="ari-tooltip" role="tooltip" hidden>
    <div class="ari-tooltip-meta"></div>
    <div class="ari-tooltip-title"></div>
    <div class="ari-tooltip-body"></div>
  </div>
</div>

<style>
#ari-cap-explorer{position:relative;margin:1rem 0 1.4rem;padding:.9rem 1rem 1rem;border:1px solid var(--main-border-color,#d7dce1);border-radius:.7rem;background:var(--main-bg,#fff)}
#ari-cap-explorer .ari-explorer-top{display:flex;justify-content:space-between;gap:1rem;align-items:center;margin-bottom:.8rem}
#ari-cap-explorer .ari-explorer-name{font-weight:750;font-size:1rem}
#ari-cap-explorer .ari-explorer-meta{margin-top:.12rem;font-size:.76rem;color:var(--text-muted-color,#777)}
#ari-cap-explorer .ari-tabs{display:flex;padding:.16rem;border:1px solid var(--main-border-color,#d7dce1);border-radius:.48rem;background:rgba(127,169,199,.05)}
#ari-cap-explorer .ari-tab{border:0;border-radius:.34rem;padding:.36rem .62rem;background:transparent;color:var(--text-muted-color,#777);font-size:.78rem;font-weight:650;cursor:pointer}
#ari-cap-explorer .ari-tab.is-active{background:var(--main-bg,#fff);color:#2f75a8;box-shadow:0 1px 4px rgba(0,0,0,.10)}
#ari-cap-explorer .ari-register-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:.3rem;font-size:.8rem;color:var(--text-muted-color,#777)}
#ari-cap-explorer .ari-register-head code{font-size:.74rem}
#ari-cap-explorer .ari-register{display:grid;grid-template-columns:repeat(16,minmax(0,1fr));height:4.7rem;border:1px solid var(--main-border-color,#d7dce1);border-radius:.48rem;overflow:hidden}
#ari-cap-explorer .ari-field{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.22rem;min-width:0;border:0;border-right:1px solid var(--main-border-color,#d7dce1);padding:.38rem .25rem;background:rgba(127,169,199,.08);color:inherit;cursor:help;line-height:1.1}
#ari-cap-explorer .ari-field:last-child{border-right:0}
#ari-cap-explorer .ari-field:hover,#ari-cap-explorer .ari-field:focus-visible,#ari-cap-explorer .ari-field.is-pinned{outline:2px solid rgba(75,134,180,.60);outline-offset:-2px;z-index:2}
#ari-cap-explorer .ari-field .ari-bits{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.67rem;color:var(--text-muted-color,#777)}
#ari-cap-explorer .ari-field>span:last-child{font-size:.76rem;font-weight:670;overflow-wrap:anywhere}
#ari-cap-explorer .ari-rsvd{background:rgba(120,120,120,.055);color:var(--text-muted-color,#777)}
#ari-cap-explorer .ari-next{background:rgba(75,134,180,.13)}
#ari-cap-explorer .ari-group{background:rgba(149,117,205,.12)}
#ari-cap-explorer .ari-acs{background:rgba(91,192,190,.13)}
#ari-cap-explorer .ari-mfvc{background:rgba(240,173,78,.14)}
#ari-cap-explorer .ari-legend{display:flex;flex-wrap:wrap;gap:.8rem;margin:.52rem .05rem 0;font-size:.7rem;color:var(--text-muted-color,#777)}
#ari-cap-explorer .ari-legend span{display:flex;align-items:center;gap:.28rem}
#ari-cap-explorer .ari-dot{display:inline-block;width:.48rem;height:.48rem;border-radius:50%}
#ari-cap-explorer .ari-next-dot{background:rgba(75,134,180,.65)}
#ari-cap-explorer .ari-group-dot{background:rgba(149,117,205,.65)}
#ari-cap-explorer .ari-acs-dot{background:rgba(91,192,190,.7)}
#ari-cap-explorer .ari-mfvc-dot{background:rgba(240,173,78,.75)}
#ari-cap-explorer .ari-role-strip{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:.35rem;align-items:center;margin-top:.85rem;padding-top:.75rem;border-top:1px dashed var(--main-border-color,#d7dce1)}
#ari-cap-explorer .ari-role-strip>button{border:0;background:transparent;color:inherit;padding:.3rem .2rem;cursor:help;text-align:center}
#ari-cap-explorer .ari-role-strip b{display:block;font-size:.78rem}
#ari-cap-explorer .ari-role-strip small{display:block;margin-top:.12rem;color:var(--text-muted-color,#777);font-size:.67rem}
#ari-cap-explorer .ari-role-strip>span{color:var(--text-muted-color,#777);font-size:.72rem}
#ari-cap-explorer .ari-tooltip{position:fixed;z-index:9999;width:min(360px,calc(100vw - 24px));padding:.72rem .8rem;border:1px solid rgba(75,134,180,.48);border-radius:.55rem;background:var(--main-bg,#fff);color:var(--text-color,#2a2a2a);box-shadow:0 12px 34px rgba(0,0,0,.18);pointer-events:none}
#ari-cap-explorer .ari-tooltip-meta{font-size:.68rem;color:var(--text-muted-color,#777);margin-bottom:.16rem}
#ari-cap-explorer .ari-tooltip-title{font-size:.88rem;font-weight:750;color:#2f75a8;margin-bottom:.28rem}
#ari-cap-explorer .ari-tooltip-body{font-size:.78rem;line-height:1.48}
@media(max-width:720px){
  #ari-cap-explorer{padding:.75rem}
  #ari-cap-explorer .ari-explorer-top{align-items:flex-start;flex-direction:column}
  #ari-cap-explorer .ari-register{height:auto;grid-template-columns:1fr}
  #ari-cap-explorer .ari-field{grid-column:1!important;min-height:2.75rem;flex-direction:row;justify-content:flex-start;gap:.55rem;padding:.5rem .6rem;border-right:0;border-bottom:1px solid var(--main-border-color,#d7dce1);text-align:left}
  #ari-cap-explorer .ari-field:last-child{border-bottom:0}
  #ari-cap-explorer .ari-role-strip{grid-template-columns:1fr}
  #ari-cap-explorer .ari-role-strip>span{transform:rotate(90deg)}
}
</style>

<script>
(()=>{
const root=document.getElementById('ari-cap-explorer');
if(!root||root.dataset.ready)return;
root.dataset.ready='1';
const tip=root.querySelector('#ari-tooltip');
const capView=root.querySelector('#ari-cap-view');
const ctlView=root.querySelector('#ari-ctl-view');
const regName=root.querySelector('#ari-reg-name');
const regOffset=root.querySelector('#ari-reg-offset');
let pinned=null;
const info={
  'next-fn':['ARI Capability · bits 15:8 · RO','Next Function Number','用于 non-VF Function 的 ARI Function 链表发现。Function 0 是链表起点；00h 表示没有更高编号的 Function。对 VF 此字段未定义，因为 VF 由 SR-IOV 的 First VF Offset / VF Stride 定位。'],
  'mfvc-cap':['ARI Capability · bit 0 · RO','MFVC Function Groups Capability (M)','仅 Function 0 有意义，其他 Function 必须为 0。置 1 表示支持以 Function Group 粒度进行 MFVC Function Arbitration。'],
  'acs-cap':['ARI Capability · bit 1 · RO','ACS Function Groups Capability (A)','仅 Function 0 有意义，其他 Function 必须为 0。置 1 表示支持以 Function Group 粒度进行 ACS P2P Egress Control。'],
  'function-group':['ARI Control · bits 6:4 · RW','Function Group','给当前 Function 分配 3-bit Function Group Number。只有 Function 0 宣告 MFVC/ACS Function Group 能力时才有实际用途，否则该字段固定为 000b。'],
  'mfvc-en':['ARI Control · bit 0 · RW','MFVC Function Groups Enable','仅 Function 0 可编程。置 1 后，MFVC Function Arbitration Table 的表项按 Function Group Number 而不是单个 Function Number 解释。'],
  'acs-en':['ARI Control · bit 1 · RW','ACS Function Groups Enable','仅 Function 0 可编程。置 1 后，ACS Egress Control Vector 按 Function Group Number 而不是单个 Function Number 关联。'],
  'cap-rsvd':['ARI Capability','Reserved','保留字段。'],
  'ctl-rsvd-hi':['ARI Control','Reserved','保留字段。'],
  'ctl-rsvd-mid':['ARI Control','Reserved','保留字段。'],
  endpoint:['组件职责','ARI Device / EP','对于不在 Root Complex 内的 SR-IOV Device，规范要求每个 Function 都实现 ARI Extended Capability。注意：实现 ARI Capability 不等于当前 hierarchy 已启用 ARI；系统仍可按 non-ARI 方式运行。'],
  dsp:['组件职责','Root Port / Switch DSP','ARI Device 正上方的 Downstream Port 通过 Device Capabilities 2 宣告 ARI Forwarding 支持，并由 Device Control 2 的 ARI Forwarding Enable 控制。Extended Function > 7 要被访问，这里必须启用。'],
  usp:['组件职责','Switch USP','USP 不承担紧邻 Endpoint 的 ARI Extended Function 解码；负责解除传统 Device Number 限制的是 ARI Device 正上方的 Root Port 或 Switch DSP。']
};
function place(el){
  const r=el.getBoundingClientRect();
  const tw=360, gap=10;
  let left=Math.min(window.innerWidth-tw-12,Math.max(12,r.left+r.width/2-tw/2));
  let top=r.bottom+gap;
  if(top+180>window.innerHeight) top=Math.max(12,r.top-170-gap);
  tip.style.left=left+'px'; tip.style.top=top+'px';
}
function show(key,el){
  const x=info[key]; if(!x)return;
  tip.querySelector('.ari-tooltip-meta').textContent=x[0];
  tip.querySelector('.ari-tooltip-title').textContent=x[1];
  tip.querySelector('.ari-tooltip-body').textContent=x[2];
  tip.hidden=false; place(el);
}
function hide(){if(!pinned)tip.hidden=true}
root.querySelectorAll('[data-field],[data-topic]').forEach(el=>{
  const key=el.dataset.field||el.dataset.topic;
  el.addEventListener('mouseenter',()=>{if(!pinned)show(key,el)});
  el.addEventListener('mouseleave',hide);
  el.addEventListener('focus',()=>{if(!pinned)show(key,el)});
  el.addEventListener('blur',hide);
  el.addEventListener('click',e=>{
    e.preventDefault();
    if(pinned===el){el.classList.remove('is-pinned');pinned=null;tip.hidden=true;return}
    if(pinned)pinned.classList.remove('is-pinned');
    pinned=el;el.classList.add('is-pinned');show(key,el);
  });
});
document.addEventListener('click',e=>{
  if(!root.contains(e.target)&&pinned){pinned.classList.remove('is-pinned');pinned=null;tip.hidden=true}
});
window.addEventListener('scroll',()=>{if(pinned)place(pinned)},{passive:true});
window.addEventListener('resize',()=>{if(pinned)place(pinned)});
root.querySelectorAll('.ari-tab').forEach(tab=>tab.addEventListener('click',()=>{
  if(pinned){pinned.classList.remove('is-pinned');pinned=null;tip.hidden=true}
  const ctl=tab.dataset.reg==='ctl';
  root.querySelectorAll('.ari-tab').forEach(x=>{const on=x===tab;x.classList.toggle('is-active',on);x.setAttribute('aria-selected',String(on))});
  capView.hidden=ctl;ctlView.hidden=!ctl;
  regName.textContent=ctl?'ARI Control Register':'ARI Capability Register';
  regOffset.textContent=ctl?'+06h':'+04h';
}));
})();
</script>

> **规范上的关键点：** 对于不在 Root Complex 内的 SR-IOV Device，每个 Function 都必须实现 ARI Extended Capability。但“实现 ARI Capability”不等于“当前 hierarchy 已经开启 ARI Forwarding”。

---

## 15. 三个 ARI 机制的关系

可以把整个链路理解成：

```text
SR-IOV Endpoint / ARI Device
        |
        | ARI Extended Capability
        | - Function 描述
        | - Next Function Number
        | - Function Group
        |
======== PCIe Link =================
        |
Root Port / Switch DSP
        |
        | Device Capabilities 2
        |   ARI Forwarding Supported
        |
        | Device Control 2
        |   ARI Forwarding Enable
        |
======== software state ============
        |
Lowest-numbered PF
        |
        | SR-IOV Control
        |   ARI Capable Hierarchy
        |
        v
First VF Offset / VF Stride
可以选择更适合 ARI hierarchy 的 RID 布局
```

一句话：

> **ARI Capability 描述 Device；ARI Forwarding 控制上一级 Port 是否真的按 ARI Function Number 转发；ARI Capable Hierarchy 告诉 SR-IOV Device 当前 hierarchy 已经具备这个条件。**

---

## 16. Bus Number 为什么会变成稀缺资源

一个 PCIe Segment 的 Bus Number 是 8 bit：

```text
00h ~ FFh
```

总共只有 256 个值。

这些 Bus Number 还要分给：

- Root Port 下的 Endpoint
- Switch
- Switch 下游的其他 Endpoint
- 其他 Bridge hierarchy
- SR-IOV Device 的额外 VF Bus

所以像下面这种配置：

```text
First VF Offset = 0x0100
VF Stride       = 0x0100
```

虽然合法，但非常浪费 Bus Number：

```text
PF   -> Bus 03
VF0  -> Bus 04
VF1  -> Bus 05
VF2  -> Bus 06
...
```

大量 VF 会压缩整个 hierarchy 留给其他设备的 Bus Number 空间。

PCIe 规范也明确强调 Bus Number 是 constrained resource，并建议 SR-IOV Device 尽量避免不必要的 Bus Number 洞。

---

## 17. ARI 对 SR-IOV 的现实价值

ARI 对 SR-IOV 的意义，不是“没有 ARI 就不能有 VF”。

更准确地说：

> **ARI Forwarding + ARI Capable Hierarchy 允许 SR-IOV Device 更充分利用一个 Bus 内的 8-bit Function Number 空间，从而减少 VF 对额外 Bus Number 的消耗。**

例如同样有大量 Function：

### ARI Forwarding 未开启，SR-IOV 按传统 hierarchy 布局

```text
captured Bus:
传统 Function 空间有限

更多 VF
   -> First VF Offset / VF Stride
   -> additional Bus Number
   -> Type 1 CFG 直接访问跨 Bus VF
```

### ARI Forwarding 已开启，ARI Capable Hierarchy = 1

```text
captured Bus:
Function 0 ~ 255

大量 PF / VF
   -> 可以继续留在一个 Bus
   -> 显著减少额外 Bus Number 消耗
```

注意：最终是否跨 Bus，仍然取决于实际的 `First VF Offset` / `VF Stride`。

ARI 并不会强制所有 VF 都留在一个 Bus。

---

## 18. 最终总结

把整个问题浓缩成几句话：

1. **PF 必须在 SR-IOV Device 的 captured Bus Number。**
2. **VF RID 由 PF RID + First VF Offset + VF Stride 算出来。**
3. **不同 PF 的 First VF Offset / VF Stride 不要求相同。**
4. **VF 可以位于 captured Bus，也可以位于额外 Bus。**
5. **captured Bus 上的 PF/VF 走 Type 0 Configuration Request。**
6. **额外 Bus 上的 VF 可以直接由 SR-IOV Device 接收 Type 1 Configuration Request。**
7. **ARI Extended Capability 不等于 ARI Forwarding。**
8. **ARI Capability 的 Next Function Number 主要用于 non-VF Function 的快速枚举，VF 用 First VF Offset / VF Stride 发现。**
9. **ARI Forwarding Enable=1 后，低 8 bit 可以按 ARI Function[7:0] 使用。**
10. **ARI Capable Hierarchy 是 SR-IOV Device 对 hierarchy ARI 状态的 hint，并影响 VF RID 布局。**
11. **First VF Offset = 0x0100、VF Stride = 0x0100 会让每个 VF 跳到下一个 Bus。**
12. **这种布局会快速消耗 Bus Number，因此 ARI 的一个重要现实价值就是节省 Bus Number 资源。**

最终最值得记住的一句话是：

> **SR-IOV 决定 VF 的 16-bit Routing ID 怎么生成；ARI Forwarding 决定上游 Port 能否把 Routing ID 的低 8 bit 当作扩展 Function Number 使用。二者结合后，系统可以在 VF 数量和 Bus Number 消耗之间取得更高效的布局。**

---

## 参考

- PCI Express Base Specification Revision 6.4
  - §6.13 Alternative Routing-ID Interpretation (ARI)
  - §7.3 Configuration Transaction Rules
  - §7.8.8 ARI Extended Capability
  - §9.2.1 SR-IOV Configuration / VF Discovery
  - §9.4.3 SR-IOV Extended Capability
