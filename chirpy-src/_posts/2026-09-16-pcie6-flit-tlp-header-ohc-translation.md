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

<div id="nfm-fm-structure" class="nfm-fm-structure">
  <div class="nfm-fm-head nfm-fm-head-left">Non-Flit Mode</div>
  <div class="nfm-fm-head nfm-fm-head-mid">结构变化</div>
  <div class="nfm-fm-head nfm-fm-head-right">Flit Mode</div>

  <button type="button" class="nfm-fm-cell nfm-fm-cell-key" data-detail="nfm-dw0">
    <strong>NFM DW0</strong>
    <span class="nfm-fm-code"><b>Fmt[2:0]</b> + <b>Type[4:0]</b></span>
    <small>同时编码 Header 长度 / Data 属性与事务类型</small>
  </button>
  <div class="nfm-fm-link">类型编码重构 →</div>
  <button type="button" class="nfm-fm-cell nfm-fm-cell-key" data-detail="fm-hb">
    <strong>FM Header Base</strong>
    <span class="nfm-fm-code">DW0: <b>Type[7:0]</b></span>
    <small>fully-decoded Type，Header Base format/size 由 Type 决定</small>
  </button>

  <button type="button" class="nfm-fm-cell" data-detail="nfm-dw13">
    <strong>NFM DW1~3</strong>
    <small>Requester ID / Tag / Address / Byte Enable 等固定 Header 内容</small>
  </button>
  <button type="button" class="nfm-fm-link nfm-fm-expand-toggle" id="nfm-fm-expand-toggle" aria-expanded="false" aria-controls="nfm-fm-expand-panel">字段重组 ↓</button>
  <button type="button" class="nfm-fm-cell" data-detail="fm-ohc">
    <strong>FM Header Base (DW1+) + OHC</strong>
    <small>核心字段留在 Header Base；条件式 / 正交扩展语义进入 OHC</small>
  </button>

  <div id="nfm-fm-expand-panel" class="nfm-fm-expand" hidden>
    <div class="nfm-fm-expand-title">NFM 后续 Header / Prefix 语义如何重组到 FM</div>
    <div class="nfm-fm-expand-grid">
      <div class="nfm-fm-expand-col">
        <strong>NFM：DW1~3 / End-End Prefix</strong>
        <span>Requester ID</span>
        <span>Tag[7:0] + T8/T9</span>
        <span>Address</span>
        <span>First / Last DW Byte Enable</span>
        <span>AT</span>
        <span>PASID / TPH / IDE / Segment 等扩展语义</span>
      </div>
      <div class="nfm-fm-expand-arrow">→</div>
      <div class="nfm-fm-expand-col">
        <strong>FM：仍在 Header Base</strong>
        <span>Requester ID</span>
        <span>Tag[13:0]</span>
        <span>Address</span>
        <span>family-specific 核心字段</span>
        <span>Memory/Atomic 的 AT → 最后一个 Address DWORD[1:0]</span>
      </div>
      <div class="nfm-fm-expand-col">
        <strong>FM：进入 OHC</strong>
        <span>Byte Enable（按 family 使用 OHC-A）</span>
        <span>PASID</span>
        <span>TPH</span>
        <span>IDE / Segment</span>
        <span>其他按条件出现的 orthogonal header content</span>
      </div>
    </div>
    <p>这里是<strong>语义重组</strong>，不是固定的 bit-for-bit 或 DWORD-for-DWORD 映射；具体字段位置取决于 TLP family。</p>
  </div>

  <button type="button" class="nfm-fm-cell" data-detail="nfm-payload">
    <strong>Payload</strong>
    <small>存在 Data 时的事务数据</small>
  </button>
  <div class="nfm-fm-link">语义保持 →</div>
  <button type="button" class="nfm-fm-cell" data-detail="fm-payload">
    <strong>Payload</strong>
    <small>仍是 TLP 的 Data Payload</small>
  </button>

  <button type="button" class="nfm-fm-cell" data-detail="nfm-ecrc">
    <strong>TLP Digest / ECRC</strong>
    <small><code>TD=1</code> 时位于 NFM TLP 尾部</small>
  </button>
  <div class="nfm-fm-link">尾部机制扩展 →</div>
  <button type="button" class="nfm-fm-cell" data-detail="fm-trailer">
    <strong>TLP Trailer</strong>
    <small>由 <code>TS[2:0]</code> 指示类型 / 长度</small>
  </button>

  <div id="nfm-fm-detail" class="nfm-fm-detail" aria-live="polite" hidden>
    <button type="button" class="nfm-fm-detail-close" aria-label="关闭字段说明">×</button>
    <h4 id="nfm-fm-detail-title"></h4>
    <div id="nfm-fm-detail-body"></div>
  </div>
</div>

<style>
#nfm-fm-structure{position:relative;display:grid;grid-template-columns:minmax(0,1fr) 8.5rem minmax(0,1fr);gap:.55rem;align-items:stretch;margin:1rem 0 1.1rem}
#nfm-fm-structure .nfm-fm-head{padding:.52rem .7rem;text-align:center;font-weight:700;border:1px solid var(--main-border-color,#d7dce1);background:rgba(127,169,199,.18)}
#nfm-fm-structure .nfm-fm-head-left,#nfm-fm-structure .nfm-fm-head-right{border-radius:.65rem .65rem 0 0}
#nfm-fm-structure .nfm-fm-head-mid{border:0;background:transparent;color:var(--text-muted-color,#777);font-size:.8rem;font-weight:600}
#nfm-fm-structure .nfm-fm-cell{appearance:none;width:100%;padding:.72rem .75rem;border:1px solid var(--main-border-color,#d7dce1);border-radius:.5rem;background:var(--main-bg,#fff);color:inherit;text-align:center;cursor:pointer;line-height:1.3}
#nfm-fm-structure .nfm-fm-cell:hover,#nfm-fm-structure .nfm-fm-cell:focus-visible{border-color:#4b86b4;background:rgba(127,169,199,.08);outline:2px solid rgba(75,134,180,.42);outline-offset:-2px}
#nfm-fm-structure .nfm-fm-cell.is-active{border-color:#6ba66e;background:rgba(107,166,110,.16);outline:2px solid rgba(107,166,110,.42);outline-offset:-2px}
#nfm-fm-structure .nfm-fm-cell strong{display:block;font-size:.95rem}
#nfm-fm-structure .nfm-fm-cell small{display:block;margin-top:.26rem;color:var(--text-muted-color,#777);font-size:.78rem}
#nfm-fm-structure .nfm-fm-cell-key{background:rgba(127,169,199,.08)}
#nfm-fm-structure .nfm-fm-code{display:block;margin-top:.3rem;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.9rem}
#nfm-fm-structure .nfm-fm-code b{color:#2f75a8}
#nfm-fm-structure .nfm-fm-link{display:flex;align-items:center;justify-content:center;padding:.4rem;color:var(--text-muted-color,#777);font-size:.76rem;text-align:center;border:0;background:transparent}
#nfm-fm-structure .nfm-fm-expand-toggle{cursor:pointer;border-radius:.4rem;font:inherit}
#nfm-fm-structure .nfm-fm-expand-toggle:hover,#nfm-fm-structure .nfm-fm-expand-toggle:focus-visible{color:#2f75a8;background:rgba(127,169,199,.08);outline:none}
#nfm-fm-structure .nfm-fm-expand{grid-column:1/-1;padding:.9rem 1rem;border:1px solid var(--main-border-color,#d7dce1);border-radius:.65rem;background:rgba(127,169,199,.045)}
#nfm-fm-structure .nfm-fm-expand-title{text-align:center;font-weight:700;margin-bottom:.7rem}
#nfm-fm-structure .nfm-fm-expand-grid{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr) minmax(0,1fr);gap:.65rem;align-items:stretch}
#nfm-fm-structure .nfm-fm-expand-col{display:flex;flex-direction:column;gap:.3rem;padding:.7rem;border:1px solid var(--main-border-color,#e1e5e8);border-radius:.5rem;background:var(--main-bg,#fff)}
#nfm-fm-structure .nfm-fm-expand-col strong{text-align:center;margin-bottom:.15rem}
#nfm-fm-structure .nfm-fm-expand-col span{font-size:.82rem;line-height:1.35}
#nfm-fm-structure .nfm-fm-expand-arrow{display:flex;align-items:center;justify-content:center;font-size:1.35rem;color:#4b86b4}
#nfm-fm-structure .nfm-fm-expand p{margin:.65rem 0 0;text-align:center;font-size:.82rem;color:var(--text-muted-color,#777)}
#nfm-fm-structure .nfm-fm-detail{grid-column:1/-1;position:relative;margin-top:.25rem;padding:.85rem 1rem;border:1px solid #7fa9c7;border-radius:.6rem;background:var(--main-bg,#fff);box-shadow:0 8px 24px rgba(0,0,0,.12)}
#nfm-fm-structure .nfm-fm-detail h4{margin:0 2rem .35rem 0;font-size:.95rem;color:#2f75a8}
#nfm-fm-structure .nfm-fm-detail p{margin:.35rem 0;line-height:1.55}
#nfm-fm-structure .nfm-fm-detail-close{position:absolute;right:.6rem;top:.45rem;border:0;background:transparent;color:var(--text-muted-color,#777);font-size:1.35rem;cursor:pointer}
@media(max-width:720px){#nfm-fm-structure{grid-template-columns:1fr;gap:.45rem}#nfm-fm-structure .nfm-fm-head-mid{display:none}#nfm-fm-structure .nfm-fm-link{padding:.15rem}#nfm-fm-structure .nfm-fm-expand{grid-column:1}#nfm-fm-structure .nfm-fm-expand-grid{grid-template-columns:1fr}#nfm-fm-structure .nfm-fm-expand-arrow{transform:rotate(90deg)}}
</style>

<script>
(()=>{
const root=document.getElementById('nfm-fm-structure');
if(!root||root.dataset.ready)return;
root.dataset.ready='1';
const detail=root.querySelector('#nfm-fm-detail');
const title=root.querySelector('#nfm-fm-detail-title');
const body=root.querySelector('#nfm-fm-detail-body');
const expandToggle=root.querySelector('#nfm-fm-expand-toggle');
const expandPanel=root.querySelector('#nfm-fm-expand-panel');
const explanations={
  'nfm-dw0':{title:'NFM DW0：Fmt + Type',body:'NFM 的第一个 DWORD 同时包含 Fmt[2:0] 与 Type[4:0]。Fmt 负责表达 3DW/4DW 以及是否带 Data，Type 再与 Fmt 一起确定具体 TLP 类型。因此 NFM 的事务类型解码依赖 Fmt + Type 的组合。'},
  'fm-hb':{title:'FM Header Base：Type[7:0]',body:'Flit Mode 不再使用独立的 Fmt 字段，而是在 Header Base DW0 中使用 fully-decoded Type[7:0]。Type 直接选择 transaction type，并决定对应 Header Base 的 format/size。MRd32 是典型例外：NFM Byte0=0x00，而 FM 中 0x00 用作 NOP，因此 FM MRd32 改为 0x03。'},
  'nfm-dw13':{title:'NFM DW1~3：固定 Header 的主要事务字段',body:'NFM 后续 DWORD 根据 TLP family 承载 Requester ID、Tag、Address、Byte Enable、Configuration Register Number、Completion 信息等。这里的“DW1~3”是结构归纳；这些字段到 FM 后会被拆分到 Header Base 与 OHC，而不是整体搬进 OHC。'},
  'fm-ohc':{title:'FM Header Base (DW1+) + OHC',body:'Requester ID、Tag、Address 等事务核心字段仍保留在 FM Header Base 的后续 DWORD；Byte Enable、PASID、TPH、IDE、Segment 等条件式或扩展语义则按 TLP family 进入 OHC-A/B/C/E。NFM 的 End-End TLP Prefix 语义也会在 FM 中重组进 Header/OHC。'},
  'nfm-payload':{title:'NFM Payload',body:'当 TLP 类型带 Data 时，Payload 位于 Header（以及适用的 Prefix）之后。Length 字段描述 Data Payload 的 DWORD 数量，Header 和 Prefix 本身不计入 Payload。'},
  'fm-payload':{title:'FM Payload',body:'Flit Mode 中 Payload 的事务语义保持不变，仍然是 TLP 的 Data Payload。Header Base、OHC 与 Trailer 均不属于 Payload；整个 TLP 再被装入 256B Flit 的 TLP 区域。'},
  'nfm-ecrc':{title:'NFM TLP Digest / ECRC',body:'Non-Flit Mode 中 TD 位指示 TLP Digest 是否存在。TD=1 时，32-bit ECRC 作为 TLP Digest 附加在 TLP 尾部，用于端到端完整性检查。'},
  'fm-trailer':{title:'FM TLP Trailer',body:'Flit Mode 将尾部机制统一为 TLP Trailer，并由 Header Base 中的 TS[2:0] 指示是否存在以及对应长度/类型。Trailer 可以承载 ECRC，也支持 IDE 等机制所需要的尾部内容，因此它比 NFM 的单一 TLP Digest 机制更通用。'}
};
function closeDetail(){detail.hidden=true;root.querySelectorAll('.nfm-fm-cell.is-active').forEach(x=>x.classList.remove('is-active'))}
root.querySelectorAll('.nfm-fm-cell').forEach(btn=>btn.addEventListener('click',()=>{
  const x=explanations[btn.dataset.detail];
  if(!x)return;
  root.querySelectorAll('.nfm-fm-cell.is-active').forEach(y=>y.classList.remove('is-active'));
  btn.classList.add('is-active');
  title.textContent=x.title;
  body.innerHTML=`<p>${x.body}</p>`;
  detail.hidden=false;
}));
root.querySelector('.nfm-fm-detail-close').addEventListener('click',closeDetail);
expandToggle.addEventListener('click',()=>{
  const open=expandPanel.hidden;
  expandPanel.hidden=!open;
  expandToggle.setAttribute('aria-expanded',String(open));
  expandToggle.textContent=open?'收起字段重组 ↑':'字段重组 ↓';
});
})();
</script>

> **Prefix 仍需单独看待：** Flit Mode 仍可保留 Local Vendor-Defined TLP Prefix；NFM 中的 End-End TLP Prefix 内容则在 FM 中重组进 Header/OHC。因此不能理解成“FM 把所有 Prefix 都替换成 OHC”。

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