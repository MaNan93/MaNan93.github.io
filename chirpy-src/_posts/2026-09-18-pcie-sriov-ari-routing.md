---
title: PCIe SR-IOV 与 ARI：VF Routing ID、Bus Number 与端口职责
date: 2026-09-18 13:50:00 +0800
categories: [PCIe, Virtualization]
tags: [PCIe, SR-IOV, ARI, VF, PF, Routing ID, Bus Number]
permalink: /pcie-sriov-ari-routing/
description: 梳理 PCIe SR-IOV 中 VF Routing ID 的生成方式，以及 non-ARI / ARI hierarchy 下 Bus Number 的消耗差异，并说明 EP、Root Port、Switch DSP、USP 各自与 ARI Capability / ARI Forwarding 的关系。
toc: true
---

SR-IOV 里一个很容易混淆的问题是：

> VF 很多时，为什么有时会占用额外 Bus Number，而有时又可以全部留在同一个 Bus？

核心取决于两件事：

1. **VF Routing ID 如何生成**
2. **当前 PCIe hierarchy 是否启用了 ARI（Alternative Routing-ID Interpretation）**

---

## 1. Routing ID 的基本格式

PCIe 的 Routing ID / Requester ID / Completer ID 都是 16 bit。

### Non-ARI

传统解释方式：

```text
15             8 7             3 2       0
+---------------+---------------+---------+
|  Bus Number   | Device Number | Function|
+---------------+---------------+---------+
      8 bit          5 bit        3 bit
```

即：

```text
Bus[7:0] + Device[4:0] + Function[2:0]
```

### ARI

ARI 并没有增加 Routing ID 的位宽，仍然是 16 bit，只是重新解释低 8 bit：

```text
15             8 7                         0
+---------------+---------------------------+
|  Bus Number   |      Function Number      |
+---------------+---------------------------+
      8 bit                 8 bit
```

即：

```text
Bus[7:0] + Function[7:0]
```

所以同一个数值，例如：

```text
RID = 0x0325
```

在两种模式下的解释不同：

| 模式 | 解释 |
|---|---|
| Non-ARI | Bus 03, Device 04, Function 5 |
| ARI | Bus 03, Function 0x25 = 37 |

**Routing ID 的 16-bit 数值没变，变的是低 8 bit 的解释方式。**

---

## 2. SR-IOV 的 VF Routing ID 怎么算

SR-IOV Capability 中有两个关键字段：

- `First VF Offset`
- `VF Stride`

VF Routing ID 按下面的方式计算：

```text
VF1 RID = PF RID + First VF Offset

VFn RID = PF RID
        + First VF Offset
        + (n - 1) * VF Stride
```

所有运算都是 16-bit Routing ID 运算。

因此是否跨 Bus，真正应该看：

```text
PF RID + First VF Offset + (NumVFs - 1) * VF Stride
```

是否让 RID 从：

```text
xxFF
```

进入：

```text
(xx+1)00
```

所以不能简单地只看 VF 数量。

例如即使 VF 很少，如果：

```text
VF Stride = 64
```

也可能很快跨到下一个 Bus。

---

## 3. Non-ARI SR-IOV：为什么 VF 多了必须占 Bus Number

对于位于 Downstream Port 后面的 SR-IOV Endpoint，在 non-ARI hierarchy 下，其 Device Number 必须保持为 0。

也就是说同一个 Bus 上，这个 Endpoint 实际可用的是：

```text
xx:00.0
xx:00.1
...
xx:00.7
```

一共只有 8 个 Function RID。

不能继续使用：

```text
xx:01.0
xx:01.1
...
```

来表示同一个 SR-IOV Device 的更多 VF。

因此：

```text
PF + VF > 8
```

时，如果没有 ARI，就需要进入后续 Bus Number：

```text
Bus n:
n:00.0 ~ n:00.7

Bus n+1:
(n+1):00.0 ~ (n+1):00.7

Bus n+2:
(n+2):00.0 ~ (n+2):00.7
```

所以 non-ARI SR-IOV 的代价之一，就是可能大量消耗 Bus Number。

---

## 4. ARI SR-IOV：为什么同一 Bus 可以有 256 个 Function

启用 ARI 后：

```text
Device[4:0] + Function[2:0]
```

被整体解释成：

```text
Function[7:0]
```

于是一个 Bus 内可以使用：

```text
Function 0 ~ 255
```

例如：

```text
RID 0x0300 -> Bus 03, Function 0
RID 0x0301 -> Bus 03, Function 1
...
RID 0x0308 -> Bus 03, Function 8
...
RID 0x03FF -> Bus 03, Function 255
```

因此，在 Routing ID 分配足够紧凑的情况下：

```text
PF + VF <= 256
```

可以全部放在同一个 Bus。

如果继续增加，Routing ID 会自然跨过：

```text
03FF -> 0400
```

此时仍然需要额外 Bus Number。

PCIe 规范给出的典型例子是：

```text
PF0 + VF0~VF255   -> 第一个 Bus
VF256~VF511       -> 第二个 Bus
VF512~            -> 第三个 Bus
```

但要注意：

> “256 个才跨 Bus”只适用于 First VF Offset / VF Stride 足够紧凑的情况。

---

## 5. 2 PF × 32 VF 的例子

假设：

```text
PF0 + PF1
每个 PF 32 VF

总数 = 2 + 64 = 66 Functions
```

### Non-ARI

每个 Bus 对该 Device 最多只有 8 个 Function：

```text
Bus n     : 8
Bus n+1   : 8
Bus n+2   : 8
...
```

因此需要多个 Bus Number。

### ARI

如果 VF RID 分配紧凑：

```text
Bus n:
Function 0 ~ 65
```

66 个 PF/VF Routing ID 可以全部放在同一个 Bus。

---

## 6. ARI 到底是谁支持：EP、DSP、Root Port、USP？

这里要区分两个概念：

- **ARI Device**
- **ARI Downstream Port / ARI Forwarding**

它们不是一回事。

---

## 7. Endpoint / PF：ARI Extended Capability

一个 ARI Device 的 Function 会实现 **ARI Extended Capability**。ARI Extended Capability ID 为 `000Eh`，结构很小：一个 Extended Capability Header、一个 ARI Capability Register，以及一个 ARI Control Register。

下面这个 Explorer 可以直接点字段查看含义。默认先展示 Capability Register；切到 Control 可以看可编程控制项。

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

> **规范上的一个关键点：** ARI Extended Capability 通常是可选能力，但对于 **不在 Root Complex 内的 SR-IOV Device**，规范要求它的每个 Function 都实现 ARI Extended Capability。这个“必须实现”不等于 hierarchy 必须开启 ARI；软件仍可以让设备工作在 non-ARI hierarchy 下。

### Next Function Number

对于非 VF Function：

```text
Next Function Number
```

形成一个 Function 链，用来帮助软件发现 Function > 7 的 Extended Functions。

例如：

```text
Function 0
   |
   +-- Next Function Number = 4
                              |
                              v
                         Function 4
                              |
                              +-- Next = 10
                                       |
                                       v
                                  Function 10
```

但 VF 不依赖这个字段发现。

VF 的位置由：

```text
First VF Offset
VF Stride
```

决定。

### ARI Capability 中的其他功能

ARI Capability 还包含与 Function Group 有关的功能，例如：

- MFVC Function Groups Capability
- ACS Function Groups Capability
- Function Group

这些主要用于多 Function 设备中的 VC / ACS Function Group 管理。

因此：

> EP 侧的 ARI Extended Capability 描述的是“这个 Device 如何作为 ARI Device 工作”。

---

## 8. DSP / Root Port：ARI Forwarding

真正决定能不能访问 Function 8~255 的关键，是 **EP 正上方的 Downstream Port**。

这个 Downstream Port 可以是：

- Root Port
- Switch Downstream Port（DSP）

PCIe 对 ARI Downstream Port 的定义就是：

> 支持 ARI Forwarding 的 Root Port 或 Switch Downstream Port。

DSP / Root Port 的关键控制是：

```text
ARI Forwarding Supported
ARI Forwarding Enable
```

当 ARI Forwarding Enable 打开后，它允许下面的 ARI Device 使用 Extended Functions。

---

## 9. 为什么 DSP 必须支持 ARI Forwarding

假设收到：

```text
RID = 0x0341
```

ARI 解释：

```text
Bus      = 03
Function = 0x41 = 65
```

但传统解释会变成：

```text
Bus      = 03
Device   = 08
Function = 1
```

所以如果 DSP 不支持 / 没打开 ARI Forwarding，它会按传统 Device/Function 规则处理。

对于一个直接位于 Downstream Port 后面的 Endpoint：

```text
Device Number 必须 = 0
```

因此这种 `Device=8` 的解释就是非法的。

ARI Forwarding 的核心作用就是：

> 让 Downstream Port 不再把 RID[7:3] 强制解释成传统 Device Number，而允许它属于 8-bit ARI Function Number。

---

# 10. ARI Forwarding 并不是 Bus Number 路由功能

这一点很重要。

Switch / Root Port 对 Bus Number 的路由仍然依靠：

```text
Secondary Bus Number
Subordinate Bus Number
```

例如：

```text
DSP:
Secondary   = 03
Subordinate = 07
```

意味着：

```text
Bus 03 ~ 07
```

都应该从该 Downstream Port 路由下去。

所以 ARI 并不是解决“Bus Number 往哪里走”。

ARI 真正解决的是：

```text
RID[7:0]
```

在目标 Bus 内应该解释成：

```text
Device[4:0] + Function[2:0]
```

还是：

```text
Function[7:0]
```

---

# 11. DSP 的 Secondary / Subordinate Bus Number

如果 SR-IOV Device 的 VF 跨多个 Bus，软件需要给 DSP 留出足够的 Bus Number 范围。

例如：

```text
EP PF 所在 Bus       = 03
最后一个 VF 所在 Bus = 07
```

则可以配置为：

```text
Secondary Bus Number   = 03
Subordinate Bus Number = 07
```

其中：

- **Secondary Bus Number**：该 DSP 下游的第一个 Bus
- **Subordinate Bus Number**：该 DSP 下游允许路由到的最大 Bus Number

VF 增多时，通常需要扩大的是：

```text
Subordinate Bus Number
```

而不是不断修改 Secondary Bus Number。

---

# 12. USP 是否需要 ARI Capability？

这是最容易混淆的一点。

对于一个普通 Switch：

```text
        Switch USP
             |
         Switch Fabric
        /     |      \
      DSP    DSP     DSP
       |      |
      EP     EP
```

**ARI Forwarding 是 Downstream Port 的能力。**

因为 Extended Function 所在的 ARI Device 是挂在某个 DSP 下面的，真正需要解除传统 Device Number 限制的是这个 DSP。

因此：

| 组件 | ARI 相关职责 |
|---|---|
| EP / PF | 作为 ARI Device，实现 ARI Extended Capability |
| VF | 通过 SR-IOV First VF Offset / VF Stride 定位，不依赖 Next Function Number |
| Root Port | 如果下面直接挂 ARI Device，需要支持并 Enable ARI Forwarding |
| Switch DSP | 如果下面直接挂 ARI Device，需要支持并 Enable ARI Forwarding |
| Switch USP | 不承担“下面某个 EP Extended Function”的直接 ARI Forwarding 角色；上游主要看到正常的 Requester/Completer ID |
| Switch Fabric | 正常根据 Bus Number / 路由规则转发 |

因此判断 ARI Forwarding 时最重要的一句话是：

> 看 **ARI Device immediately above/below 的相邻 Downstream Port**。

PCIe 对 Extended Function 的定义也明确指出：

> Function Number > 7 的 Extended Function，只有在 ARI Device 正上方的 Downstream Port 开启 ARI Forwarding 后才能访问。

---

# 13. Root Port 与 Switch DSP 本质相同

从 ARI 角度看：

```text
Root Port
   |
  EP
```

和：

```text
Switch DSP
   |
  EP
```

作用类似。

只要这个 Port 是：

```text
immediately above the ARI Device
```

它就必须支持：

```text
ARI Forwarding Supported
```

并由软件设置：

```text
ARI Forwarding Enable = 1
```

之后 EP 才能合法使用 Function 8~255。

---

# 14. SR-IOV Capability 中的 ARI Capable Hierarchy

SR-IOV PF 中还有：

```text
ARI Capable Hierarchy
```

这个 bit 的意义不是“EP 自己有没有 ARI Capability”。

它表示：

> 软件已经确认当前 PCIe hierarchy 可以支持这个 SR-IOV Device 按 ARI 方式分配 VF Routing ID。

因此 Device 可以根据这个 bit 决定：

```text
First VF Offset
VF Stride
```

应该采用适合 ARI hierarchy 还是 non-ARI hierarchy 的布局。

一些 PCIe Controller IP 会分别准备：

```text
ARI hierarchy:
  First VF Offset
  VF Stride

Non-ARI hierarchy:
  First VF Offset
  VF Stride
```

两套值。

---

# 15. 两种模式最终对比

| 项目 | Non-ARI SR-IOV | ARI SR-IOV |
|---|---|---|
| RID 低 8 bit | Device[4:0] + Function[2:0] | Function[7:0] |
| 同 Bus 最大 Function 空间 | 8 | 256 |
| Device Number | 必须为 0 | 不再单独解释 Device Number |
| VF 多时 | 较早跨 Bus | 最多 256 个 RID 可留在一个 Bus |
| DSP ARI Forwarding | 不需要 | Function > 7 时必须支持并 Enable |
| Bus Number 路由 | Secondary/Subordinate Bus | Secondary/Subordinate Bus |
| VF RID 生成 | First VF Offset + VF Stride | First VF Offset + VF Stride |

---

# 16. 最终可以这样记

### Non-ARI

```text
SR-IOV EP
Device Number 必须 = 0

每 Bus：
Function 0~7

超过 8 个 PF/VF
        |
        v
占用新的 Bus Number
        |
        v
DSP Subordinate Bus Number 必须覆盖所有 VF Bus
```

### ARI

```text
SR-IOV + ARI

Bus[7:0] + Function[7:0]

同 Bus：
Function 0~255
        |
        v
EP 正上方 Root Port / DSP
必须支持 ARI Forwarding
        |
        v
Function > 255 或 RID 因 Offset/Stride 跨 xxFF
        |
        v
进入新的 Bus Number
        |
        v
DSP Subordinate Bus Number 继续覆盖
```

---

## 17. 一个容易遗漏的结论

**ARI 与 SR-IOV 是两个不同机制。**

SR-IOV 并不强制 ARI。

但是：

- 没有 ARI，大规模 VF 会很快消耗 Bus Number
- 有 ARI，可以把 Routing ID 的低 8 bit 全部作为 Function Number
- VF 是否真正跨 Bus，最终仍取决于 `First VF Offset` 和 `VF Stride`

因此最准确的理解是：

> **ARI 决定一个 Bus 内 Routing ID 低 8 bit 如何解释；SR-IOV 的 First VF Offset / VF Stride 决定每个 VF 最终拿到哪个 16-bit Routing ID。**

---

## 参考

- PCI Express Base Specification Revision 6.4
  - ARI / ARI Device / ARI Downstream Port / ARI Forwarding 定义
  - Section 7.8.8, ARI Extended Capability
  - Section 9.2.1.2, VF Discovery
  - Section 9.4.3, SR-IOV Capability registers
- Synopsys DesignWare PCI Express Controller Databook
  - SR-IOV and ARI Capable Hierarchy
  - Programmable Virtual Function Allocation
  - Routing ID Generation Examples
