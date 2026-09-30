#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《周易》现代转译工程 · 静态站点构建脚本（第十四期）

用法：python3 tools/build_site.py
产出：site/ 目录（纯静态，GitHub Pages 可直接托管，可重复运行）

- hexagrams/*.md        → site/hexagrams/NN-name.html
- docs/FOREWORD.md      → site/foreword.html
- docs/GUIDE.md         → site/guide.html
- GLOSSARY.md           → site/glossary.html
- notes/examples.md     → site/examples.html
- site/index.html       首页（搜索框 + 主题簇 + 64 卦卡片墙 + 入口）
- site/search-index.js  客户端全文检索索引
- site/assets/          样式、脚本、封面等静态资源

硬约束：每一页都带「反对迷信占卜，仅解读思想」水印与声明（固定声明条 +
背景平铺水印 + 单卦页正文首行声明 + 打印样式保留声明）。
"""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path
from urllib.parse import quote

import markdown as md_lib

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

REPO_BLOB = "https://github.com/if0x522/new_yi/blob/main/"
REPO_URL = "https://github.com/if0x522/new_yi"
PAGES_URL = "https://if0x522.github.io/new_yi/"

DISCLAIMER = ("⚠️ 反对迷信占卜，仅解读思想——本项目不做任何吉凶预测与命运占断，"
              "只做文本解读与方法论研究")
INLINE_DISCLAIMER = ("小字声明：本页仅作《周易》文本解读与方法论研究，"
                     "反对迷信占卜，不作任何吉凶预测与命运占断。")

# ---------------------------------------------------------------- 主题簇
# 与 docs/GUIDE.md "主题簇阅读路径" 一致。前四簇为归属簇（每卦恰属其一）,
# 后五簇为横向子线（卡片附加标签，可与归属簇并存）。
CLUSTERS = [
    ("起步线", "起步", [3, 4, 5, 6, 9, 26, 27, 39, 46, 53],
     "创业、开蒙、等待、止损——再接积蓄、颐养、险阻、上升、渐进"),
    ("组织领导线", "组织领导", [19, 7, 8, 15, 31, 37, 57, 58, 45, 61, 13, 14, 17, 16],
     "感通、动员、结盟、谦抑——组织怎么带、人心怎么聚"),
    ("变革转型线", "变革转型", [49, 50, 18, 41, 42, 43, 40, 21, 22, 48, 59, 60, 38],
     "换轨、立制、治旧弊、成本与收益的承担方向"),
    ("处境判断线", "处境判断", [1, 2, 11, 12, 63, 64, 23, 24, 25, 28, 29, 30,
                            33, 34, 35, 36, 47, 51, 52, 54, 55, 56, 62],
     "时位、承载、通塞、完成与未完成——形势怎么判"),
    ("资源线", "资源线", [41, 42, 9, 14, 55], "减损、增益、小蓄、大有、盛极"),
    ("艰难线", "艰难线", [47, 39, 29, 36], "穷、阻、险、晦明——四种难法，四种守法"),
    ("进退线", "进退线", [33, 34, 35, 53], "退的梯度、盛的节制、进的台阶"),
    ("聚散线", "聚散线", [45, 59, 13, 37, 38], "聚人、散而后聚、同盟、内部治理、乖离求同"),
    ("信与度", "信与度", [61, 62], "孚是信，过是度，一对双尺"),
]
SUBLINES = {"消长主线": [19, 11, 12, 23, 24]}  # GUIDE：临→泰→否→剥→复

# 卦名主旨兜底（README 进度表口径；正文有「主题：」行时优先取正文）
FALLBACK_SUMMARY = {
    1: "自强不息与时机进退", 2: "承载配合与底线", 3: "创业维艰", 4: "教育启蒙",
    5: "等待与时机", 6: "争端与止损", 7: "动员组织与纪律", 8: "亲比与联盟",
    9: "小有积蓄与克制", 10: "践履与风险秩序", 11: "通泰与居安思危",
    12: "闭塞与守持待时", 13: "协作与同盟", 14: "大有与治理", 15: "谦抑与平衡",
    16: "预备与安逸", 17: "追随与随时", 18: "整治积弊", 19: "治理感通",
    20: "观察与示范", 21: "咬合除梗与惩罚次序", 22: "文饰与实质",
    23: "剥落与止损", 24: "复归与重启", 25: "不妄为与无妄之灾",
    26: "大积蓄与养贤设防", 27: "颐养与节欲", 28: "非常之举的边界",
    29: "重险行军法", 30: "依附与传承", 31: "感应与共情的层次", 32: "恒久与守变",
    33: "退避与战略撤退", 34: "强盛与节制", 35: "进取与晋升",
    36: "光明受损期的守持", 37: "内部治理", 38: "睽违与求同",
    39: "险阻与反身修德", 40: "解除险难与善后", 41: "减损与成本承担",
    42: "增益与施予下放", 43: "决断与清除积弊", 44: "相遇与防微",
    45: "聚合与凝聚", 46: "上升与台阶式成长", 47: "困境与守持出口",
    48: "供给体系与公共品", 49: "变革的方法", 50: "建制立新", 51: "震动应对",
    52: "知止与边界", 53: "渐进与次序", 54: "错位配合", 55: "盛大与蔽障",
    56: "羁旅与客场生存", 57: "渗透与申命", 58: "欣悦与说服", 59: "涣散与重聚",
    60: "节制与制度", 61: "信任与可信信号", 62: "小过与尺度",
    63: "完成态的守成", 64: "未成态的收束与再出发",
}

# ---------------------------------------------------------------- 工具


def strip_markdown(text: str) -> str:
    """把 markdown 去成纯文本，供检索索引用。"""
    t = text
    t = re.sub(r'```.*?```', ' ', t, flags=re.S)
    t = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', t)
    t = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', t)
    t = re.sub(r'^#{1,6}\s*', '', t, flags=re.M)
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
    t = re.sub(r'\*([^*]+)\*', r'\1', t)
    t = re.sub(r'`([^`]+)`', r'\1', t)
    t = re.sub(r'^\s*>\s?', '', t, flags=re.M)
    t = re.sub(r'^\s*[-*+]\s+', '', t, flags=re.M)
    t = re.sub(r'^\s*\d+\.\s+', '', t, flags=re.M)
    t = t.replace('|', ' ').replace('---', ' ')
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def md_to_html(text: str) -> str:
    return md_lib.markdown(text, extensions=['tables', 'sane_lists'])


# 站内已生成页面：md 仓库路径 → 站点页面（相对 site/ 根）
SITE_PAGE_MAP = {
    'docs/foreword.md': 'foreword.html',
    'docs/guide.md': 'guide.html',
    'glossary.md': 'glossary.html',
    'notes/examples.md': 'examples.html',
}
HEX_PATH_RE = re.compile(r'hexagrams/(\d{2})-([\w-]+)\.md$')


def rewrite_links(md_text: str, src_rel: str, prefix: str = '') -> str:
    """正文里的相对 .md 链接改写为站内页面；其余仓库文件落到 GitHub blob。

    prefix 为当前页面到 site/ 根的相对前缀（根页面 ''，hexagrams/ 下 '../'）。
    """
    src_dir = Path(src_rel).parent

    def repl(m: re.Match) -> str:
        url = m.group(1).strip()
        label = m.group(0)
        if url.startswith(('http://', 'https://', 'mailto:', '#', 'data:')):
            return label
        path_part, _, anchor = url.partition('#')
        if not path_part:
            return label
        resolved = (src_dir / path_part).as_posix()
        # 归一化 a/b/../c
        parts: list[str] = []
        for seg in resolved.split('/'):
            if seg in ('', '.'):
                continue
            if seg == '..':
                if parts:
                    parts.pop()
                continue
            parts.append(seg)
        resolved = '/'.join(parts)
        low = resolved.lower()
        href = None
        if low in SITE_PAGE_MAP:
            href = SITE_PAGE_MAP[low]
        else:
            hm = HEX_PATH_RE.search(low)
            if hm:
                href = f'hexagrams/{hm.group(1)}-{hm.group(2)}.html'
        if href is None:
            href = REPO_BLOB + resolved
        else:
            href = prefix + href
        if anchor:
            href += '#' + anchor
        return f']({href})'

    return re.sub(r'\]\(([^)]+)\)', repl, md_text)


def render_template(*, title: str, description: str, prefix: str, body: str,
                    extra_head: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<meta name="robots" content="index,follow">
<link rel="stylesheet" href="{prefix}assets/site.css">
{extra_head}
</head>
<body>
<div class="watermark-layer" aria-hidden="true"></div>
<header class="site-header">
  <a class="brand" href="{prefix}index.html"><span class="brand-seal" aria-hidden="true">译</span>《周易》现代转译</a>
  <form class="mini-search" action="{prefix}index.html" method="get" role="search">
    <input type="search" name="q" placeholder="搜卦名 / 关键词 / 句子" aria-label="站内检索">
    <button type="submit">检索</button>
  </form>
</header>
<p class="disclaimer-bar">{html.escape(DISCLAIMER)}</p>
<main class="page">
{body}
</main>
<footer class="site-footer">
  <p class="footer-disclaimer">{html.escape(DISCLAIMER)}</p>
  <p class="footer-meta">《周易》现代转译工程 · 六十四卦现代转译 ·
    <a href="{REPO_URL}">github.com/if0x522/new_yi</a> ·
    纯静态站点，可离线阅读</p>
</footer>
<script src="{prefix}assets/site.js"></script>
</body>
</html>
"""


# ---------------------------------------------------------------- 卦页


def build_hexagram_page(hx: dict, prev_hx: dict | None, next_hx: dict | None) -> str:
    tags_html = ''.join(
        f'<a class="tag" href="../index.html?tag={quote(t)}">{html.escape(t)}</a>'
        for t in hx['tags'])
    nav = []
    if prev_hx:
        nav.append(f'<a class="pager-link" href="{prev_hx["file"]}">← {prev_hx["num"]} {html.escape(prev_hx["name"])}</a>')
    nav.append('<a class="pager-link" href="../index.html#hexagrams">全部六十四卦</a>')
    if next_hx:
        nav.append(f'<a class="pager-link" href="{next_hx["file"]}">{next_hx["num"]} {html.escape(next_hx["name"])} →</a>')
    nav_html = '<nav class="pager">' + ''.join(nav) + '</nav>'

    body = f"""<article class="hex-article">
<header class="hex-head">
  <p class="hex-kicker">第 {hx['num']} 卦 · 六节全本 · 五道工序</p>
  <h1 class="hex-title">{html.escape(hx['name'])} <span class="hex-symbol">{html.escape(hx['symbol'])}</span></h1>
  <p class="hex-summary">{html.escape(hx['summary'])}</p>
  <p class="hex-tags">{tags_html}</p>
</header>
<p class="inline-disclaimer">{html.escape(INLINE_DISCLAIMER)}</p>
<div class="hex-lead">{hx['lead_html']}</div>
<div class="md-body">
{hx['body_html']}
</div>
{nav_html}
</article>"""
    return render_template(
        title=f"{hx['num']} {hx['name']} · 《周易》现代转译",
        description=f"{hx['num']} {hx['name']}：{hx['summary']}——训诂、语境、结构、现代转译、实践清单、卦际关联六节全本。",
        prefix="../", body=body)


# ---------------------------------------------------------------- 首页


def build_index(hexes: list[dict]) -> str:
    cluster_html = []
    for cname, short, nums, desc in CLUSTERS:
        cluster_html.append(
            f'<button class="cluster-chip" type="button" data-tag="{quote(cname)}">'
            f'<span class="cluster-name">{html.escape(short)}</span>'
            f'<span class="cluster-count">{len(nums)} 卦</span>'
            f'<span class="cluster-desc">{html.escape(desc)}</span></button>')
    sub_html = []
    for cname, nums in SUBLINES.items():
        sub_html.append(
            f'<button class="cluster-chip sub" type="button" data-tag="{quote(cname)}">'
            f'<span class="cluster-name">{html.escape(cname)}</span>'
            f'<span class="cluster-count">{len(nums)} 卦</span>'
            f'<span class="cluster-desc">临→泰→否→剥→复：优势窗口的完整生命周期</span></button>')

    cards = []
    for hx in hexes:
        tag_spans = ''.join(f'<span class="tag">{html.escape(t)}</span>' for t in hx['tags'])
        data_text = ' '.join([str(hx['num']), hx['name'], hx['symbol'], hx['summary'],
                              ' '.join(hx['tags']), hx['keywords']])
        cards.append(f"""<a class="card" href="{hx['rel']}" data-tags="{html.escape(' '.join(hx['tags']))}" data-text="{html.escape(data_text.lower())}">
  <span class="card-top"><span class="card-num">{hx['num']}</span><span class="card-symbol">{html.escape(hx['symbol'].split('（')[0])}</span></span>
  <h3 class="card-name">{html.escape(hx['name'])}</h3>
  <p class="card-summary">{html.escape(hx['summary'])}</p>
  <p class="card-tags">{tag_spans}</p>
</a>""")

    body = f"""
<section class="hero">
  <figure class="hero-cover">
    <img src="assets/cover.png" alt="《周易》现代转译工程封面：宣纸底、墨色书名、朱红印章与地泽临卦象" width="320" height="480">
  </figure>
  <div class="hero-text">
    <p class="hero-kicker">《周易》现代转译工程 · 可检索站点</p>
    <h1>把方法论内核，<br>接上现代认识工具</h1>
    <p class="hero-sub">六十四卦逐一过手，每卦六节：训诂 → 语境 → 结构 → 现代转译 → 实践清单 → 卦际关联。
    不神化为玄学，不贬为江湖术数——只做文本解读与方法论研究。</p>
    <p class="hero-stats">64 卦全本 · 检验实例 111+ · 术语 400+ · 血统标注逐句可核</p>
  </div>
</section>

<section class="search-section" id="search">
  <h2 class="section-title">检索全书</h2>
  <p class="section-lead">输入即搜：卦名、卦序、卦爻辞关键词、现代转译、实践清单、实例名都可以。</p>
  <div class="search-box">
    <input id="q" type="search" autocomplete="off" spellcheck="false"
           placeholder="试试「临」「消长」「履霜」「FIFA」......" aria-label="全书检索">
  </div>
  <p class="search-status" id="search-status"></p>
</section>

<section class="clusters" id="clusters">
  <h2 class="section-title">主题簇 · 按问题进入</h2>
  <p class="section-lead">不必从乾卦顺序读起。点一条主线，卡片墙随之过滤。</p>
  <div class="cluster-grid">{''.join(cluster_html)}</div>
  <div class="cluster-grid sub">{''.join(sub_html)}</div>
</section>

<section class="hexwall" id="hexagrams">
  <h2 class="section-title">六十四卦 · 卡片墙</h2>
  <p class="section-lead">按卦序 1-64 排列，卡片标主题标签；点进单卦读六节全文。</p>
  <div class="card-grid" id="cards">{''.join(cards)}</div>
  <p class="empty-state" id="cards-empty" hidden>未命中——试试「消长」「艰难」「信任」等主题词</p>
</section>

<section class="results-section" id="results-section">
  <h2 class="section-title">全文检索结果</h2>
  <div id="results"><p class="empty-state">上方输入关键词，这里显示命中的页面、片段与跳转。</p></div>
</section>

<section class="entries" id="entries">
  <h2 class="section-title">书前书后 · 四个入口</h2>
  <div class="entry-list">
    <a class="entry" href="foreword.html"><span class="entry-name">序言</span><span class="entry-desc">把方法论内核接上现代认识工具——缘起、主张、来历</span></a>
    <a class="entry" href="guide.html"><span class="entry-name">导读</span><span class="entry-desc">怎么读这本书：六节模板、三遍阅读法、主题簇、自检清单</span></a>
    <a class="entry" href="glossary.html"><span class="entry-name">术语表</span><span class="entry-desc">易学概念 ↔ 现代概念对照，400+ 条，标注血统类型</span></a>
    <a class="entry" href="examples.html"><span class="entry-name">实例索引</span><span class="entry-desc">111+ 条真实可溯源现代实例——检验材料，不是预测论据</span></a>
  </div>
</section>
"""
    return render_template(
        title="《周易》现代转译 · 可检索站点",
        description="《周易》现代转译工程可检索静态站点：六十四卦六节全本、术语表、实例索引。反对迷信占卜，仅解读思想。",
        prefix="", body=body)


# ---------------------------------------------------------------- 资源文件

CSS = """/* 《周易》现代转译 · 素雅纸感学术小册子 */
:root {
  --paper: #F7F3E8;
  --paper-deep: #EFE8D4;
  --ink: #33302A;
  --ink-soft: #6E675B;
  --vermilion: #B03A2E;
  --line: #D9CDB2;
  --serif: "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", "STSong",
           "SimSun", "Noto Serif", Georgia, serif;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--serif);
  font-size: 17px;
  line-height: 1.85;
  text-rendering: optimizeLegibility;
}
/* -- 背景平铺斜向水印（透明度 0.05 ≤ 0.06，不干扰阅读）-- */
.watermark-layer {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background-repeat: repeat;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='260' height='180'%3E%3Ctext x='-10' y='110' transform='rotate(-24 0 110)' font-family='serif' font-size='15' fill='%2333302A' fill-opacity='0.05'%3E%E5%8F%8D%E5%AF%B9%E8%BF%B7%E4%BF%A1%E5%8D%9C%E5%8D%A0%20%E4%BB%85%E8%A7%A3%E8%AF%BB%E6%80%9D%E6%83%B3%3C/text%3E%3C/svg%3E");
}
.site-header, .disclaimer-bar, .page, .site-footer {
  position: relative;
  z-index: 1;
}
a { color: var(--ink); text-decoration: none; }
a:hover { color: var(--vermilion); }
img { max-width: 100%; height: auto; }

/* -- 页头 -- */
.site-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.1rem clamp(1.1rem, 4vw, 3rem);
  border-bottom: 1px solid var(--line);
}
.brand {
  font-size: 1.02rem;
  letter-spacing: 0.12em;
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
}
.brand-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  background: var(--vermilion);
  color: var(--paper);
  font-size: 0.95rem;
  letter-spacing: 0;
  border-radius: 2px;
}
.mini-search { display: flex; gap: 0.45rem; }
.mini-search input {
  width: clamp(9rem, 26vw, 15rem);
  padding: 0.42rem 0.75rem;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.45);
  font: inherit;
  font-size: 0.9rem;
  color: var(--ink);
  border-radius: 2px;
}
.mini-search button {
  padding: 0.42rem 0.9rem;
  border: 1px solid var(--vermilion);
  background: transparent;
  color: var(--vermilion);
  font: inherit;
  font-size: 0.9rem;
  cursor: pointer;
  border-radius: 2px;
}
.mini-search button:hover { background: var(--vermilion); color: var(--paper); }

/* -- 固定声明条（每页、显眼、打印保留）-- */
.disclaimer-bar {
  margin: 0;
  padding: 0.55rem clamp(1.1rem, 4vw, 3rem);
  background: var(--paper-deep);
  border-bottom: 1px solid var(--line);
  color: var(--vermilion);
  font-size: 0.92rem;
  letter-spacing: 0.03em;
}

/* -- 页面容器 -- */
.page {
  max-width: 68rem;
  margin: 0 auto;
  padding: 2.4rem clamp(1.1rem, 4vw, 3rem) 3.5rem;
}
.section-title {
  font-size: 1.35rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  margin: 2.8rem 0 0.4rem;
}
.section-lead { color: var(--ink-soft); margin: 0 0 1.4rem; }

/* -- 首页 hero：不对称构图 -- */
.hero {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.6fr);
  gap: clamp(1.5rem, 5vw, 4rem);
  align-items: center;
  padding-bottom: 1rem;
}
.hero-cover img {
  width: 100%;
  max-width: 21rem;
  border: 1px solid var(--line);
  box-shadow: 0.7rem 0.7rem 0 rgba(51, 48, 42, 0.07);
}
.hero-kicker {
  color: var(--vermilion);
  letter-spacing: 0.18em;
  font-size: 0.92rem;
  margin: 0 0 0.8rem;
}
.hero h1 {
  font-size: clamp(2rem, 5.2vw, 3.15rem);
  line-height: 1.35;
  font-weight: 600;
  letter-spacing: 0.06em;
  margin: 0 0 1.1rem;
}
.hero-sub { margin: 0 0 1.2rem; max-width: 34rem; }
.hero-stats { color: var(--ink-soft); font-size: 0.92rem; letter-spacing: 0.05em; margin: 0; }

/* -- 搜索 -- */
.search-box input {
  width: 100%;
  padding: 1.05rem 1.3rem;
  font: inherit;
  font-size: 1.25rem;
  color: var(--ink);
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid var(--ink-soft);
  border-radius: 3px;
  outline: none;
}
.search-box input:focus {
  border-color: var(--vermilion);
  box-shadow: 0 0 0 3px rgba(176, 58, 46, 0.12);
}
.search-status { color: var(--ink-soft); font-size: 0.92rem; min-height: 1.5em; margin: 0.8rem 0 0; }
.search-status strong { color: var(--vermilion); font-weight: 600; }

/* -- 主题簇 -- */
.cluster-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(15.5rem, 1fr));
  gap: 0.85rem;
  margin-bottom: 0.85rem;
}
.cluster-chip {
  text-align: left;
  font: inherit;
  cursor: pointer;
  padding: 0.85rem 1.05rem;
  background: rgba(255, 255, 255, 0.4);
  border: 1px solid var(--line);
  border-left: 3px solid var(--vermilion);
  border-radius: 2px;
  color: var(--ink);
  transition: background 0.18s ease, border-color 0.18s ease;
}
.cluster-chip:hover { background: rgba(255, 255, 255, 0.85); }
.cluster-chip.active { border-color: var(--vermilion); background: rgba(176, 58, 46, 0.08); }
.cluster-chip.sub { border-left-color: var(--ink-soft); }
.cluster-name { display: block; font-size: 1.05rem; letter-spacing: 0.06em; }
.cluster-count { color: var(--vermilion); font-size: 0.82rem; letter-spacing: 0.08em; }
.cluster-desc { display: block; color: var(--ink-soft); font-size: 0.85rem; line-height: 1.65; margin-top: 0.25rem; }

/* -- 卡片墙（编辑感：多列瀑布式，克制）-- */
.card-grid {
  column-count: 3;
  column-gap: 1.15rem;
}
.card {
  display: block;
  break-inside: avoid;
  margin: 0 0 1.15rem;
  padding: 1.15rem 1.25rem 1.05rem;
  background: rgba(255, 255, 255, 0.42);
  border: 1px solid var(--line);
  border-radius: 3px;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}
.card:hover {
  transform: translateY(-2px);
  border-color: var(--vermilion);
  background: rgba(255, 255, 255, 0.8);
  color: var(--ink);
}
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  color: var(--ink-soft);
}
.card-num { letter-spacing: 0.14em; font-size: 0.88rem; }
.card-symbol { font-size: 1.15rem; }
.card-name { margin: 0.35rem 0 0.25rem; font-size: 1.22rem; letter-spacing: 0.07em; }
.card-summary { margin: 0 0 0.65rem; color: var(--ink-soft); font-size: 0.93rem; line-height: 1.7; }
.card-tags { margin: 0; display: flex; flex-wrap: wrap; gap: 0.35rem; }

.tag {
  display: inline-block;
  padding: 0.1rem 0.55rem;
  border: 1px solid var(--line);
  color: var(--ink-soft);
  font-size: 0.78rem;
  letter-spacing: 0.06em;
  border-radius: 2px;
}
a.tag:hover { border-color: var(--vermilion); color: var(--vermilion); }

.empty-state {
  color: var(--ink-soft);
  font-style: italic;
  padding: 1.5rem 0;
  margin: 0;
}

/* -- 检索结果 -- */
.result-item {
  padding: 1.05rem 0 1.05rem 1.15rem;
  border-left: 2px solid var(--line);
  margin-bottom: 0.8rem;
}
.result-item:hover { border-left-color: var(--vermilion); }
.result-title { margin: 0 0 0.3rem; font-size: 1.08rem; }
.result-title a { color: var(--ink); }
.result-title a:hover { color: var(--vermilion); }
.result-snippet { margin: 0; color: var(--ink-soft); font-size: 0.94rem; line-height: 1.75; }
mark {
  background: rgba(176, 58, 46, 0.14);
  color: var(--vermilion);
  padding: 0 0.12em;
  border-radius: 2px;
}

/* -- 四入口 -- */
.entry-list { border-top: 1px solid var(--line); }
.entry {
  display: grid;
  grid-template-columns: minmax(5.5rem, 0.4fr) minmax(0, 1.6fr);
  gap: 1.2rem;
  align-items: baseline;
  padding: 1.15rem 0.2rem;
  border-bottom: 1px solid var(--line);
  transition: background 0.18s ease, padding-left 0.18s ease;
}
.entry:hover { background: rgba(255, 255, 255, 0.55); padding-left: 0.75rem; color: var(--ink); }
.entry-name { font-size: 1.18rem; letter-spacing: 0.12em; }
.entry-desc { color: var(--ink-soft); font-size: 0.95rem; }

/* -- 卦页 -- */
.hex-head { border-bottom: 1px solid var(--line); padding-bottom: 1.35rem; margin-bottom: 1.6rem; }
.hex-kicker {
  color: var(--vermilion);
  letter-spacing: 0.2em;
  font-size: 0.86rem;
  margin: 0 0 0.55rem;
}
.hex-title {
  font-size: clamp(2rem, 5vw, 2.9rem);
  letter-spacing: 0.08em;
  font-weight: 600;
  margin: 0 0 0.65rem;
}
.hex-symbol { font-size: 0.62em; color: var(--ink-soft); letter-spacing: 0.12em; }
.hex-summary { color: var(--ink-soft); margin: 0 0 0.85rem; max-width: 40rem; }
.hex-tags { margin: 0; display: flex; flex-wrap: wrap; gap: 0.45rem; }
.inline-disclaimer {
  color: var(--vermilion);
  font-size: 0.86rem;
  letter-spacing: 0.03em;
  border-left: 3px solid var(--vermilion);
  padding: 0.15rem 0 0.15rem 0.85rem;
  margin: 0 0 1.6rem;
}
.hex-lead {
  font-size: 1.02rem;
  color: var(--ink);
  background: rgba(255, 255, 255, 0.42);
  border-left: 3px solid var(--line);
  padding: 0.95rem 1.25rem;
  margin: 0 0 1.9rem;
}
.hex-lead p { margin: 0.35rem 0; }

/* -- markdown 正文 -- */
.md-body { max-width: 46rem; }
.md-body h2 {
  font-size: 1.42rem;
  letter-spacing: 0.1em;
  margin: 2.9rem 0 1rem;
  padding-top: 0.4rem;
}
.md-body h3 {
  font-size: 1.14rem;
  letter-spacing: 0.07em;
  margin: 2.1rem 0 0.75rem;
  color: var(--ink);
}
.md-body p { margin: 0.95rem 0; }
.md-body strong { font-weight: 600; color: #26231E; }
.md-body ul, .md-body ol { padding-left: 1.55rem; margin: 0.95rem 0; }
.md-body li { margin: 0.32rem 0; }
.md-body blockquote {
  margin: 1.35rem 0;
  padding: 0.35rem 0 0.35rem 1.35rem;
  border-left: 3px solid var(--vermilion);
  color: var(--ink);
  background: rgba(255, 255, 255, 0.35);
}
.md-body blockquote p { margin: 0.55rem 0; }
.md-body code {
  background: var(--paper-deep);
  padding: 0.08em 0.35em;
  border-radius: 2px;
  font-size: 0.9em;
}
.md-body hr { border: 0; border-top: 1px solid var(--line); margin: 2.4rem 0; }
.md-body table {
  border-collapse: collapse;
  width: 100%;
  margin: 1.35rem 0;
  font-size: 0.95rem;
  line-height: 1.7;
  background: rgba(255, 255, 255, 0.35);
}
.md-body th, .md-body td {
  border: 1px solid var(--line);
  padding: 0.55rem 0.75rem;
  text-align: left;
  vertical-align: top;
}
.md-body th { background: var(--paper-deep); font-weight: 600; }
.md-body tr:nth-child(even) td { background: rgba(239, 232, 212, 0.32); }

/* -- 文档页（序言/导读/术语/实例）-- */
.doc-body { max-width: 48rem; }
.doc-head { margin-bottom: 1.7rem; }
.doc-kicker { color: var(--vermilion); letter-spacing: 0.2em; font-size: 0.86rem; margin: 0 0 0.55rem; }
.doc-head h1 {
  font-size: clamp(1.85rem, 4.5vw, 2.55rem);
  letter-spacing: 0.08em;
  margin: 0 0 0.75rem;
}
.doc-head .inline-disclaimer { margin-bottom: 0; }

/* -- 页脚 -- */
.site-footer {
  border-top: 1px solid var(--line);
  padding: 1.9rem clamp(1.1rem, 4vw, 3rem) 2.6rem;
  background: var(--paper-deep);
}
.footer-disclaimer {
  color: var(--vermilion);
  margin: 0 0 0.65rem;
  font-size: 0.95rem;
}
.footer-meta { color: var(--ink-soft); margin: 0; font-size: 0.9rem; }
.footer-meta a { text-decoration: underline; text-underline-offset: 3px; }

/* -- 页内翻页 -- */
.pager {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  border-top: 1px solid var(--line);
  margin-top: 3.2rem;
  padding-top: 1.25rem;
  font-size: 0.95rem;
}
.pager-link { color: var(--ink-soft); }
.pager-link:hover { color: var(--vermilion); }

/* -- 响应式 -- */
@media (max-width: 60rem) {
  .card-grid { column-count: 2; }
}
@media (max-width: 42rem) {
  body { font-size: 16px; }
  .site-header { flex-direction: column; align-items: stretch; }
  .mini-search input { width: 100%; }
  .hero { grid-template-columns: 1fr; }
  .hero-cover img { max-width: 14.5rem; }
  .card-grid { column-count: 1; }
  .entry { grid-template-columns: 1fr; gap: 0.25rem; }
  .page { padding-top: 1.7rem; }
}

/* -- 打印：声明与水印文字保留，去交互装饰 -- */
@media print {
  body { background: #fff; font-size: 11.5pt; }
  .watermark-layer { display: none; }
  .site-header, .mini-search, .pager { display: none; }
  .disclaimer-bar, .footer-disclaimer, .inline-disclaimer {
    display: block !important;
    color: #000;
    border: 1px solid #000;
    padding: 4pt 8pt;
    margin: 6pt 0;
  }
  .page { padding: 0 8pt; }
  .site-footer { border-top: 1px solid #000; background: #fff; }
  .card-grid { column-count: 2; }
  a { color: #000; }
}
"""

JS = """// 《周易》现代转译 · 客户端检索（即时过滤：卡片墙 + 全文结果）
(function () {
  'use strict';
  var qInput = document.getElementById('q');
  var cardsWrap = document.getElementById('cards');
  var cardsEmpty = document.getElementById('cards-empty');
  var resultsWrap = document.getElementById('results');
  var statusEl = document.getElementById('search-status');
  var INDEX = window.SEARCH_INDEX || [];
  var activeTag = '';
  var MAX_RESULTS = 30;

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function highlight(text, q) {
    if (!q) return esc(text);
    var lower = text.toLowerCase();
    var needle = q.toLowerCase();
    var out = '';
    var i = 0;
    while (true) {
      var hit = lower.indexOf(needle, i);
      if (hit === -1) { out += esc(text.slice(i)); break; }
      out += esc(text.slice(i, hit)) + '<mark>' + esc(text.slice(hit, hit + q.length)) + '</mark>';
      i = hit + q.length;
    }
    return out;
  }

  function applyCards(q) {
    if (!cardsWrap) return;
    var cards = cardsWrap.querySelectorAll('.card');
    var shown = 0;
    var lq = q.toLowerCase();
    for (var i = 0; i < cards.length; i++) {
      var el = cards[i];
      var text = el.getAttribute('data-text') || '';
      var tags = el.getAttribute('data-tags') || '';
      var okQ = !lq || text.indexOf(lq) !== -1;
      var okTag = !activeTag || tags.indexOf(activeTag) !== -1;
      var show = okQ && okTag;
      el.style.display = show ? '' : 'none';
      if (show) shown++;
    }
    if (cardsEmpty) cardsEmpty.hidden = shown !== 0;
    return shown;
  }

  function snippetFor(entry, q) {
    var text = entry.text || '';
    var lower = text.toLowerCase();
    var hit = q ? lower.indexOf(q.toLowerCase()) : -1;
    if (hit === -1) {
      return text.slice(0, 120) + (text.length > 120 ? '......' : '');
    }
    var start = Math.max(0, hit - 45);
    var end = Math.min(text.length, hit + q.length + 85);
    return (start > 0 ? '......' : '') + text.slice(start, end) +
      (end < text.length ? '......' : '');
  }

  function applyResults(q) {
    if (!resultsWrap) return;
    if (!q) {
      resultsWrap.innerHTML = '<p class="empty-state">上方输入关键词，这里显示命中的页面、片段与跳转。</p>';
      return 0;
    }
    var lq = q.toLowerCase();
    var hits = [];
    for (var i = 0; i < INDEX.length; i++) {
      var e = INDEX[i];
      var hay = ((e.title || '') + ' ' + (e.keywords || '') + ' ' + (e.text || '')).toLowerCase();
      if (hay.indexOf(lq) !== -1) hits.push(e);
      if (hits.length >= 200) break;
    }
    if (!hits.length) {
      resultsWrap.innerHTML = '<p class="empty-state">未命中——试试「消长」「艰难」「信任」等主题词</p>';
      return 0;
    }
    var htmlParts = [];
    for (var j = 0; j < Math.min(hits.length, MAX_RESULTS); j++) {
      var en = hits[j];
      htmlParts.push(
        '<article class="result-item">' +
        '<h3 class="result-title"><a href="' + esc(en.url) + '">' + highlight(en.title, q) + '</a></h3>' +
        '<p class="result-snippet">' + highlight(snippetFor(en, q), q) + '</p>' +
        '</article>');
    }
    resultsWrap.innerHTML = htmlParts.join('');
    return hits.length;
  }

  function run() {
    var q = qInput ? qInput.value.trim() : '';
    var nCards = applyCards(q);
    var nResults = applyResults(q);
    if (statusEl) {
      if (!q && !activeTag) {
        statusEl.textContent = '';
      } else {
        var parts = [];
        if (q) parts.push('「' + q + '」');
        if (activeTag) parts.push('主题簇「' + activeTag + '」');
        statusEl.innerHTML = parts.join(' × ') + ' -- 卡片命中 <strong>' + nCards +
          '</strong> 卦 · 全文命中 <strong>' + nResults + '</strong> 页';
      }
    }
  }

  if (qInput) {
    qInput.addEventListener('input', run);
    qInput.addEventListener('search', run);
    var params = new URLSearchParams(window.location.search);
    var q0 = params.get('q');
    var tag0 = params.get('tag');
    if (q0) qInput.value = q0;
    if (tag0) {
      activeTag = tag0;
      var chips = document.querySelectorAll('.cluster-chip');
      for (var k = 0; k < chips.length; k++) {
        if (chips[k].getAttribute('data-tag') === tag0) chips[k].classList.add('active');
      }
    }
    run();
    if (q0) {
      var sec = document.getElementById('search');
      if (sec) sec.scrollIntoView({ block: 'start' });
    }
  }

  var chips = document.querySelectorAll('.cluster-chip');
  for (var c = 0; c < chips.length; c++) {
    chips[c].addEventListener('click', function (ev) {
      var tag = ev.currentTarget.getAttribute('data-tag');
      if (activeTag === tag) {
        activeTag = '';
        ev.currentTarget.classList.remove('active');
      } else {
        activeTag = tag;
        for (var m = 0; m < chips.length; m++) chips[m].classList.remove('active');
        ev.currentTarget.classList.add('active');
      }
      var wall = document.getElementById('hexagrams');
      if (wall) wall.scrollIntoView({ behavior: 'smooth', block: 'start' });
      run();
    });
  }
})();
"""


# ---------------------------------------------------------------- 主流程

def parse_hexagrams() -> list[dict]:
    hexes = []
    for path in sorted((ROOT / 'hexagrams').glob('*.md')):
        text = path.read_text(encoding='utf-8')
        lines = text.splitlines()
        m = re.match(r'^#\s*(\d+)\s*/\s*([^/]+?)\s*/\s*(.*)$', lines[0].strip())
        if not m:
            raise SystemExit(f'无法解析卦标题： {path}')
        num = int(m.group(1))
        name = m.group(2).strip()
        symbol = m.group(3).strip()

        # 首个标题后的连续引用行 = 提要/主题
        i = 1
        lead_lines = []
        while i < len(lines):
            s = lines[i].strip()
            if s.startswith('>'):
                lead_lines.append(s.lstrip('>').strip())
                i += 1
            elif s == '':
                j = i
                while j < len(lines) and lines[j].strip() == '':
                    j += 1
                if j < len(lines) and lines[j].strip().startswith('>'):
                    i = j
                    continue
                break
            else:
                break
        lead_text = ' '.join(lead_lines).strip()

        summary = FALLBACK_SUMMARY.get(num, '')
        tm = re.match(r'^主题：\s*(.+)$', lead_text)
        if tm:
            s = tm.group(1)
            s = re.split(r'——|（', s)[0].strip().rstrip('。')
            if s:
                summary = s[:24]

        # 主题标签：归属簇 + 横向子线
        tags = []
        for cname, _short, nums, _desc in CLUSTERS:
            if num in nums:
                if cname in ('起步线', '组织领导线', '变革转型线', '处境判断线'):
                    tags.append(cname)
        for cname, nums in list(SUBLINES.items()):
            if num in nums:
                tags.append(cname)
        for cname, _short, nums, _desc in CLUSTERS:
            if cname not in ('起步线', '组织领导线', '变革转型线', '处境判断线') and num in nums:
                tags.append(cname)

        body_src = '\n'.join(lines[i:])
        body_src = rewrite_links(body_src, f'hexagrams/{path.name}', prefix='../')
        lead_html = md_to_html(rewrite_links('> ' + lead_text, f'hexagrams/{path.name}', prefix='../')) if lead_text else ''

        plain = strip_markdown(text)
        kw = f"{num} {name} {symbol} {summary} {' '.join(tags)} {path.stem}"

        hexes.append({
            'num': num, 'name': name, 'symbol': symbol, 'summary': summary,
            'tags': tags, 'keywords': kw, 'text': plain,
            'body_html': md_to_html(body_src), 'lead_html': lead_html,
            'file': f'{num:02d}-{path.stem.split("-", 1)[1]}.html',
            'rel': f'hexagrams/{num:02d}-{path.stem.split("-", 1)[1]}.html',
        })
    hexes.sort(key=lambda h: h['num'])
    for hx in hexes:
        hx['rel'] = f"hexagrams/{hx['file']}"
    return hexes


def build_doc_page(src_rel: str, out_name: str, kicker: str, title: str) -> tuple[str, dict]:
    text = (ROOT / src_rel).read_text(encoding='utf-8')
    lines = text.splitlines()
    # 首个 H1 作为页面标题，正文从其后开始
    start = 0
    if lines and lines[0].startswith('# '):
        start = 1
    body_src = '\n'.join(lines[start:])
    body_src = rewrite_links(body_src, src_rel)
    body = f"""<header class="doc-head">
  <p class="doc-kicker">{html.escape(kicker)}</p>
  <h1>{html.escape(title)}</h1>
  <p class="inline-disclaimer">{html.escape(INLINE_DISCLAIMER)}</p>
</header>
<div class="md-body doc-body">
{md_to_html(body_src)}
</div>"""
    page = render_template(
        title=f"{title} · 《周易》现代转译",
        description=f"{title}——《周易》现代转译工程。反对迷信占卜，仅解读思想。",
        prefix="", body=body)
    entry = {
        'id': out_name.replace('.html', ''),
        'title': title,
        'url': out_name,
        'keywords': f"{title} {kicker}",
        'text': strip_markdown(text),
    }
    return page, entry


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / 'hexagrams').mkdir(parents=True)
    (SITE / 'assets').mkdir(parents=True)

    # 静态资源：封面 + 插图
    shutil.copy2(ROOT / 'assets' / 'cover.png', SITE / 'assets' / 'cover.png')
    if (ROOT / 'assets' / 'figs').is_dir():
        shutil.copytree(ROOT / 'assets' / 'figs', SITE / 'assets' / 'figs')
    (SITE / 'assets' / 'site.css').write_text(CSS, encoding='utf-8')
    (SITE / 'assets' / 'site.js').write_text(JS, encoding='utf-8')

    hexes = parse_hexagrams()
    assert len(hexes) == 64, f'卦数不对： {len(hexes)}'

    index_entries = []
    for idx, hx in enumerate(hexes):
        prev_hx = hexes[idx - 1] if idx > 0 else None
        next_hx = hexes[idx + 1] if idx + 1 < len(hexes) else None
        page = build_hexagram_page(hx, prev_hx, next_hx)
        out = SITE / 'hexagrams' / hx['file']
        out.write_text(page, encoding='utf-8')
        index_entries.append({
            'id': f"hex-{hx['num']:02d}",
            'title': f"{hx['num']:02d} {hx['name']} {hx['symbol'].split('（')[0]}",
            'num': hx['num'],
            'url': hx['rel'],
            'keywords': hx['keywords'],
            'text': hx['text'],
        })

    # 文档页
    docs = [
        ('docs/FOREWORD.md', 'foreword.html', '书前 · 序言', '序：把《周易》的方法论内核接上现代认识工具'),
        ('docs/GUIDE.md', 'guide.html', '书前 · 导读', '导读：怎么读这本书'),
        ('GLOSSARY.md', 'glossary.html', '工具 · 术语', '术语对照表'),
        ('notes/examples.md', 'examples.html', '工具 · 实例', '现代实例索引'),
    ]
    for src, out, kicker, title in docs:
        page, entry = build_doc_page(src, out, kicker, title)
        (SITE / out).write_text(page, encoding='utf-8')
        index_entries.append(entry)

    # 首页 + 检索索引
    (SITE / 'index.html').write_text(build_index(hexes), encoding='utf-8')

    import json
    payload = json.dumps(index_entries, ensure_ascii=False, separators=(',', ':'))
    (SITE / 'search-index.js').write_text(
        'window.SEARCH_INDEX = ' + payload + ';\n', encoding='utf-8')

    print(f'生成完成： {len(hexes)} 卦 + 4 文档页 + 首页， 索引条目 {len(index_entries)}')
    print(f'输出目录： {SITE}')


if __name__ == '__main__':
    main()
