#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
travel-guide-generator · 渲染器
读取出行配置 (YAML/JSON) + 图片目录，套用 template.html，输出自包含攻略 HTML。
图片以 base64 内嵌，保证手机离线可显示。

用法:
  python build.py --config config.yaml --out guide.html [--imgdir assets/img] [--template assets/template.html]
"""
import argparse
import base64
import html
import io
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

# ---------- 配置加载 ----------
def load_config(path: Path):
    txt = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(txt)
    try:
        import yaml
        return yaml.safe_load(txt)
    except ImportError:
        raise SystemExit("缺少 PyYAML，请运行: pip install pyyaml  或改用 .json 配置")

# ---------- 日期/星期 ----------
WEEK = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
def parse_date(s):
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None
def date_label(s):
    d = parse_date(s)
    if not d:
        return s
    return f"{d.month}月{d.day}日 {WEEK[d.weekday()]}"

# ---------- 城市代码/ID 映射 ----------
CITY_CODE = {  # 机票 3 字码
    "天津": "TSN", "上海": "SHA", "北京": "PEK", "杭州": "HGH", "南京": "NKG",
    "广州": "CAN", "深圳": "SZX", "成都": "CTU", "重庆": "CKG", "西安": "XIY",
    "武汉": "WUH", "厦门": "XMN", "昆明": "KMG", "三亚": "SYX", "青岛": "TAO",
    "苏州": "SZV", "长沙": "CSX", "哈尔滨": "HRB", "沈阳": "SHE", "大连": "DLC",
}
CITY_ID = {  # 携程酒店城市 ID
    "上海": 2, "杭州": 27, "北京": 1, "天津": 31, "南京": 11, "广州": 32,
    "深圳": 30, "成都": 9, "重庆": 8, "西安": 43, "武汉": 21, "厦门": 37,
    "昆明": 36, "三亚": 41, "苏州": 14, "长沙": 16, "青岛": 36, "哈尔滨": 53,
}
CITY_BADGE = {  # 时间轴城市标签配色
    "上海": ("city-sh", "上海"),
    "杭州": ("city-hz", "杭州"),
    "返程": ("city-back", "返程"),
    "天津": ("city-back", "返程"),
    "中国香港": ("city-hk", "香港"),
    "中国澳门": ("city-mo", "澳门"),
}

# 城际交通：route 类型图标（标题已用 🚄，此处按交通方式区分每条路线）
ROUTE_ICON = {
    "flight": "✈️",   # 去程/返程/备选 航班
    "bus": "🚌",      # 跨境巴士 / 金巴
    "train": "🚄",    # 高铁动车
}

def budget_cat_icon(cat):
    """预算类别前缀图标：交通✈️ 住宿🏨 门票🎫 餐饮🍜 伴手礼/杂项🛍️"""
    c = cat or ""
    if "交通" in c:
        return "✈️ "
    if "住宿" in c:
        return "🏨 "
    if "门票" in c:
        return "🎫 "
    if "餐饮" in c:
        return "🍜 "
    if "伴手" in c or "杂项" in c:
        return "🛍️ "
    return ""

# ---------- 图片内嵌 ----------
def img_b64(img_dir: Path, key: str, max_side: int = None):
    """按 key 在 img_dir 找 png/jpg，转 JPEG base64 返回完整 data URI；缺失返回空串。
    max_side 指定则等比缩放到最长边 <= max_side（用于汇总/美食等小图，控制体积）。"""
    if not key:
        return ""
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = img_dir / f"{key}{ext}"
        if p.exists():
            break
    else:
        print(f"  [warn] 图片缺失: {img_dir}/{key}.*")
        return ""
    try:
        from PIL import Image
        im = Image.open(p)
        if im.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            im = im.convert("RGBA")
            bg.paste(im, mask=im.split()[-1])
            im = bg
        if max_side:
            im.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=82, optimize=True)
        data = buf.getvalue()
    except Exception:
        data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"

# ---------- 小工具 ----------
def esc(s):
    return html.escape(str(s)) if s is not None else ""

def badge(confirmed, draft=False):
    # 三态：None=未填(待确认) / False=候选(备选) / True=已订(确定出行)
    if confirmed is None:
        return '<span class="badge-pending">⏳ 待确认</span>'
    if draft:
        return '<span class="badge-pending">⏳ 待确认</span>'
    return '<span class="badge-ok">✅ 确定出行</span>' if confirmed else '<span class="badge-alt">备选</span>'

def auto_ticketed(cfg, frm, to, lk_type):
    """route 连线 ticketed 自动取对应 transport 项的 confirmed（任一已订即已出票）。
    配置 route.links[].ticketed 可显式覆盖，省略时由 transport 同步。"""
    for it in cfg.get("transport", []):
        if it.get("type") == lk_type and it.get("from") == frm and it.get("to") == to:
            if it.get("confirmed"):
                return True
    return False

def city_badge(city):
    c = city[2:] if city and city.startswith("中国") else city
    cls, label = CITY_BADGE.get(c, ("city-back", c))
    return f'<span class="city-badge {cls}">{esc(label)}</span>'

def fmt_ymd(s):
    """2026-08-17 -> 2026/08/17（携程酒店链接用）"""
    d = parse_date(s)
    return d.strftime("%Y/%m/%d") if d else s

def ctrip_btn(it_type, link, override=None):
    """携程按钮：按类型分派文案；非携程域名去 🟧 并降级为「查看详情 ›」"""
    is_ctrip = "ctrip.com" in link
    if override:
        text = override
    elif it_type == "train":
        text = "携程购高铁票 ›"
    elif it_type == "flight":
        text = "携程比价下单 ›"
    else:
        text = "携程看房下单 ›"
    icon = "🟧 " if is_ctrip else ""
    return f'<a class="ctrip-btn" href="{esc(link)}" target="_blank" rel="noopener">{icon}{esc(text)}</a>'

def sec_note(cfg, key):
    n = cfg.get("notes", {}).get(key)
    return f'<p class="note">{esc(n)}</p>' if n else ""

def sec_tip(cfg, key):
    t = cfg.get("tips_box", {}).get(key)
    return f'<div class="tip">{esc(t)}</div>' if t else ""

# ---------- 各模块渲染 ----------
def render_transport(cfg, img_dir, draft=False):
    if not cfg.get("modules", {}).get("transport", True):
        return ""
    items = cfg.get("transport", [])
    if not items:
        return ""
    codes = {**CITY_CODE, **cfg.get("meta", {}).get("city_codes", {})}
    cards = []
    for it in items:
        frm, to = it.get("from"), it.get("to")
        confirmed = it.get("confirmed", False)
        img_key = it.get("img") or to
        img_uri = img_b64(img_dir, img_key)
        img_tag = f'<img class="rec-img" src="{img_uri}" alt="{esc(to)}地标"/>' if img_uri else ""
        dt = it.get("date", "")
        date_tag = f'<div class="rec-date">📅 {esc(date_label(dt))}</div>' if dt else ""
        # 携程链接
        link = it.get("ctrip")
        if not link:
            if it.get("type") == "train":
                link = (f"https://trains.ctrip.com/trainbooking/search?"
                        f"from={esc(frm)}&to={esc(to)}&day={esc(dt)}")
            else:
                fc = codes.get(frm, frm)
                tc = codes.get(to, to)
                link = (f"https://flights.ctrip.com/online/list/oneway-{fc}-{tc}"
                        f"?depdate={esc(dt)}")
        # meta 内容（字段前加对应图标，更直观）
        parts = []
        if it.get("flight_no"):
            parts.append(f'✈️ <b>航班</b> {esc(it["flight_no"])}')
        if it.get("cabin"):
            parts.append(f'🎫 <b>舱位</b> {esc(it["cabin"])}')
        if it.get("duration"):
            parts.append(f'⏱️ <b>时长</b> {esc(it["duration"])}')
        if it.get("price"):
            parts.append(f'💰 <b>参考价</b> {esc(it["price"])}')
        if it.get("note"):
            parts.append(esc(it["note"]))
        meta = "<br/>".join(parts)
        ico = ROUTE_ICON.get(it.get("type", "flight"), "🚌")
        role_prefix = f'{esc(it.get("role"))} · ' if it.get("role") else ""
        cards.append(f"""    <div class="rec-card">
{img_tag}
{date_tag}
      <div class="route">{ico} {role_prefix}{esc(frm)} → {esc(to)} {badge(confirmed, draft)}</div>
      <div class="meta">{meta}</div>
      {ctrip_btn(it.get("type", "flight"), link, it.get("btn_text"))}
    </div>""")
    return ('<section>\n<h2>🚄 城际交通推荐</h2>\n'
            + sec_note(cfg, "transport")
            + '<div class="rec-grid">\n' + "\n".join(cards) + "\n</div>\n"
            + sec_tip(cfg, "transport")
            + "</section>\n")

def render_hotels(cfg, img_dir, draft=False):
    if not cfg.get("modules", {}).get("hotels", True):
        return ""
    items = cfg.get("hotels", [])
    if not items:
        # 混合策略：酒店留空(未联网查) -> 初稿态显示待确认占位卡
        if draft:
            return ('<section>\n<h2>🏨 酒店推荐</h2>\n'
                    + '<div class="rec-grid"><div class="rec-card">'
                    + '<div class="route">🏨 酒店待确认 <span class="badge-pending">⏳ 待确认</span></div>'
                    + '<div class="meta">出行前将根据行程与预算补充，可携程搜索页自选（已附城市搜索直链）。</div></div></div>\n'
                    + "</section>\n")
        return ""
    city_ids = {**CITY_ID, **cfg.get("meta", {}).get("city_ids", {})}
    meta = cfg.get("meta", {})
    # 按城市分组
    groups = {}
    for it in items:
        groups.setdefault(it.get("city", "其他"), []).append(it)
    blocks = []
    for city, lst in groups.items():
        cards = []
        for it in lst:
            confirmed = it.get("confirmed", False)
            img_key = it.get("img") or it.get("name")
            img_uri = img_b64(img_dir, img_key)
            img_tag = f'<img class="rec-img" src="{img_uri}" alt="{esc(it.get("name"))}"/>' if img_uri else ""
            link = it.get("ctrip")
            if not link:
                hid = it.get("hotel_id")
                cid = city_ids.get(city, "")
                hci = fmt_ymd(it.get("checkin") or meta.get("start_date", ""))
                hco = fmt_ymd(it.get("checkout") or meta.get("end_date", ""))
                kw = quote(it.get("keyword") or it.get("name", ""))
                if hid:
                    link = (f"https://hotels.ctrip.com/hotels/{esc(hid)}.html"
                            f"?checkIn={hci}&checkOut={hco}")
                else:
                    link = (f"https://hotels.ctrip.com/hotels/list?city={esc(cid)}"
                            f"&checkin={hci}&checkout={hco}&keyword={kw}")
            parts = []
            if it.get("area"):
                parts.append(f'📍 <b>位置</b> {esc(it["area"])}')
            if it.get("price"):
                parts.append(f'💰 <b>参考价</b> {esc(it["price"])}')
            if it.get("note"):
                parts.append(esc(it["note"]))
            meta_html = "<br/>".join(parts)
            cards.append(f"""    <div class="rec-card">
{img_tag}
      <div class="route">🏨 {esc(it.get("name"))} {badge(confirmed, draft)}</div>
      <div class="meta">{meta_html}</div>
      {ctrip_btn("hotel", link, it.get("btn_text"))}
    </div>""")
        city_short = city[2:] if city.startswith("中国") else city
        blocks.append(f'<div class="rec-sub">{esc(city_short)}</div>\n<div class="rec-grid">\n'
                      + "\n".join(cards) + "\n</div>")
    return ('<section>\n<h2>🏨 酒店推荐</h2>\n'
            + sec_note(cfg, "hotels")
            + "\n".join(blocks) + "\n"
            + sec_tip(cfg, "hotels")
            + "</section>\n")

def render_budget(cfg):
    if not cfg.get("modules", {}).get("budget", True):
        return ""
    rows = cfg.get("budget")
    if not rows:
        return ""
    trs = []
    total = 0
    for r in rows:
        amt = r.get("amount", "")
        cat = r.get("cat", "")
        cat_icon = budget_cat_icon(cat)
        trs.append(f"<tr><td>{cat_icon}{esc(cat)}</td><td>{esc(amt)}</td><td>{esc(r.get('note',''))}</td></tr>")
        # 试着累加数字区间下限
        import re
        m = re.search(r"[\d,]+", str(amt))
        if m:
            try:
                total += int(m.group().replace(",", ""))
            except ValueError:
                pass
    total_html = f"¥{total:,}" if total else "—"
    return ('<section>\n<h2>💰 预算估算</h2>\n'
            + sec_note(cfg, "budget")
            + '<table>\n'
            '<tr><th>类别</th><th>估算</th><th>说明</th></tr>\n'
            + "\n".join(trs)
            + f"\n<tr><td><b>合计</b></td><td><b>{total_html}</b></td><td></td></tr>\n"
            + "</table>\n"
            + sec_tip(cfg, "budget")
            + "</section>\n")

def render_timeline(cfg, img_dir):
    if not cfg.get("modules", {}).get("timeline", True):
        return ""
    days = cfg.get("timeline", [])
    if not days:
        return ""
    out = ['<section>\n<h2>🗓️ 完整时间轴</h2>']
    out.append(sec_note(cfg, "timeline"))
    for d in days:
        city = d.get("city", "")
        city_short = city[2:] if city.startswith("中国") else city
        weather = d.get("weather", "")
        wtag = f'<span class="weather">{esc(weather)}</span>' if weather else ""
        out.append(f'  <div class="day-title">DAY {esc(d.get("day"))} · {esc(date_label(d.get("date","")))} {esc(city_short)} {wtag}</div>')
        out.append('  <div class="timeline">')
        for it in d.get("items", []):
            photo = it.get("photo")
            img_uri = img_b64(img_dir, photo) if photo else ""
            img_line = f'        <img src="{img_uri}" alt="{esc(it.get("title"))}"/>\n' if img_uri else ""
            cb = city_badge(it.get("city", city)) if it.get("city") else ""
            tags_html = "".join(f'<span class="tag">{esc(t)}</span>' for t in it.get("tags", []))
            price = f' <span class="price">{esc(it["price"])}</span>' if it.get("price") else ""
            booking = it.get("booking")
            booking_html = f'<div class="booking">需预约 · {esc(booking)}</div>' if booking else ""
            out.append(f"""    <div class="tl-item">
      <div class="time">{esc(it.get("time"))}</div>
      <div class="tl-card">
{img_line}        <div class="t">{esc(it.get("title"))}{cb}{tags_html}</div>
        <div class="d">{esc(it.get("desc"))}{price}</div>
        {booking_html}
      </div>
    </div>""")
        out.append("  </div>")
    out.append(sec_tip(cfg, "timeline"))
    out.append("</section>\n")
    return "\n".join(out)

def render_tips(cfg):
    if not cfg.get("modules", {}).get("tips", True):
        return ""
    tips = cfg.get("tips")
    if not tips:
        return ""
    blocks = {
        "kids": ("🎒 行前准备（重要）", tips.get("kids", [])),
        "booking": ("🎫 预约提醒（重要）", tips.get("booking", [])),
        "heat": ("☀️ 8月防暑", tips.get("heat", [])),
        "pitfalls": ("⚠️ 避坑", tips.get("pitfalls", [])),
    }
    lis = []
    for key, (title, lst) in blocks.items():
        if not lst:
            continue
        items = "\n".join(f"<li>{esc(x)}</li>" for x in lst)
        lis.append(f'  <h3>{title}</h3>\n  <ul>\n{items}\n  </ul>')
    if not lis:
        return ""
    return ('<section>\n<h2>📌 实用贴士</h2>\n'
            + sec_note(cfg, "tips")
            + '<div class="tips-block">\n'
            + "\n".join(lis) + "\n</div>\n"
            + sec_tip(cfg, "tips")
            + "</section>\n")

def render_food(cfg, img_dir):
    if not cfg.get("modules", {}).get("food", True):
        return ""
    food = cfg.get("food")
    if not food:
        return ""
    # 每项渲染为独立卡片（上图下文）；item.img 优先，缺省回退分组 img
    secs = []
    for sec in food:
        title = sec.get("title", "")
        group_img = sec.get("img")
        cards = []
        for i in sec.get("items", []):
            name = i.get("name", "")
            desc = i.get("desc", "")
            em = i.get("emoji", "")
            img_key = i.get("img") or group_img
            # 不传 max_side：保留原始分辨率（仅转 JPEG 容器压缩，视觉无损，体积可控）
            img_uri = img_b64(img_dir, img_key) if img_key else ""
            img_tag = f'<img src="{img_uri}" alt="{esc(name)}"/>' if img_uri else ""
            emoji_tag = f'<span class="fe">{esc(em)}</span>' if em else ""
            cards.append(
                f'<div class="food-card">{img_tag}'
                f'<div class="food-body"><div class="fn">{emoji_tag}{esc(name)}</div>'
                f'<div class="fd">{esc(desc)}</div></div></div>'
            )
        secs.append(f'  <h3>{esc(title)}</h3>\n  <div class="food-grid">\n'
                    + "\n".join(cards) + "\n  </div>")
    if not secs:
        return ""
    return ('<section class="food">\n<h2>🍜 美食购物推荐</h2>\n'
            + sec_note(cfg, "food")
            + "\n".join(secs) + "\n"
            + sec_tip(cfg, "food")
            + "</section>\n")

# ---------- 新增模块：整体路线图 / 亲子景点汇总 ----------
def render_route(cfg, img_dir):
    if not cfg.get("modules", {}).get("route", True):
        return ""
    r = cfg.get("route")
    if not r:
        return ""
    out = ['<section>\n<h2>🗺️ 整体路线图</h2>']
    # 副标题：优先 notes.route，否则用 route.note
    note = sec_note(cfg, "route") or (f'<p class="note">{esc(r.get("note",""))}</p>' if r.get("note") else "")
    if note:
        out.append(note)

    # 节点-连线可视化（移动端可横向滚动/换行）
    nodes = r.get("nodes", [])
    links = r.get("links", [])
    if nodes:
        flow = []
        for idx, n in enumerate(nodes):
            ring_cls = "rt-ring hz" if n.get("accent") == "hz" else "rt-ring"
            img_key = n.get("img")
            img_uri = img_b64(img_dir, img_key, max_side=160) if img_key else ""
            img_tag = f'<img alt="{esc(n.get("city",""))}" src="{img_uri}"/>' if img_uri else ""
            flow.append(
                f'<div class="rt-node"><div class="{ring_cls}">{img_tag}</div>'
                f'<div class="rt-city">{esc(n.get("city",""))}</div>'
                f'<div class="rt-code">{esc(n.get("code",""))}</div>'
                f'<div class="rt-when">{esc(n.get("when",""))}</div></div>'
            )
            if idx < len(links):
                lk = links[idx]
                lcls = lk.get("line_cls", "")
                lcls = f' {lcls}' if lcls else ""
                carrier = lk.get("carrier", "")
                mode = lk.get("mode", "🚄")
                dur = lk.get("dur", "")
                # ticketed：显式覆盖优先；否则自动取对应 transport 项的 confirmed
                tk = lk.get("ticketed")
                if tk is None:
                    frm, to = n.get("city"), nodes[idx + 1].get("city") if idx + 1 < len(nodes) else n.get("city")
                    lk_type = "train" if mode == "🚄" else "flight"
                    tk = auto_ticketed(cfg, frm, to, lk_type)
                ticket = '<div class="rt-ticket">✅ 已出票</div>' if tk else ""
                flow.append(
                    f'<div class="rt-link"><div class="rt-line{lcls}"></div>'
                    f'<div class="rt-mode">{mode} {esc(carrier)}</div>'
                    f'<div class="rt-dur">{esc(dur)}</div>{ticket}</div>'
                )
        out.append('<div class="rt-flow">' + "".join(flow) + "</div>")

    # 统计条（可选）：km / 天数 / 城市数 / 打卡点
    stats = r.get("stats", [])
    if stats:
        cells = "".join(
            f'<div><b>{esc(s.get("value",""))}</b><span>{esc(s.get("label",""))}</span></div>'
            for s in stats
        )
        out.append(f'<div class="rt-stat">{cells}</div>')

    # 兼容旧版：纯文本路线 + 城市胶囊（无 nodes 时使用）
    if not nodes:
        line = r.get("line", "")
        districts = r.get("districts", [])
        if line:
            out.append(f'<div class="route-line">{esc(line)}</div>')
        if districts:
            out.append('<div class="districts">' + "".join(f'<span>{esc(d)}</span>' for d in districts) + '</div>')

    tip = sec_tip(cfg, "route") or (f'<div class="tip">{esc(r.get("tip",""))}</div>' if r.get("tip") else "")
    if tip:
        out.append(tip)
    out.append("</section>\n")
    return "\n".join(out)

def render_highlights(cfg, img_dir):
    if not cfg.get("modules", {}).get("highlights", True):
        return ""
    hs = cfg.get("highlights")
    if not hs:
        return ""
    out = ['<section>\n<h2>🎡 亲子景点推荐汇总</h2>']
    out.append(sec_note(cfg, "highlights"))
    cards = []
    for h in hs:
        img_key = h.get("img")
        img_uri = img_b64(img_dir, img_key, max_side=960) if img_key else ""
        img_tag = f'<img class="card-img" src="{img_uri}" alt="{esc(h.get("name",""))}"/>' if img_uri else ""
        cards.append(f"""    <div class="card">
{img_tag}      <div class="ci">
        <div class="e">{esc(h.get("emoji",""))}</div>
        <div class="c">{esc(h.get("name",""))}</div>
        <div>{esc(h.get("desc",""))}</div>
      </div>
    </div>""")
    out.append('<div class="summary">\n' + "\n".join(cards) + "\n</div>")
    out.append(sec_tip(cfg, "highlights"))
    out.append("</section>\n")
    return "\n".join(out)

# ---------- 主流程 ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--template", default=None)
    ap.add_argument("--imgdir", default="assets/img")
    args = ap.parse_args()

    base = Path(args.config).parent
    cfg = load_config(Path(args.config))
    tmpl_path = Path(args.template) if args.template else (base / "assets" / "template.html")
    if not tmpl_path.exists():
        tmpl_path = Path(__file__).parent.parent / "assets" / "template.html"
    img_dir = Path(args.imgdir)
    if not img_dir.is_absolute():
        img_dir = base / img_dir

    tpl = tmpl_path.read_text(encoding="utf-8")
    meta = cfg.get("meta", {})
    draft = bool(meta.get("draft", False))
    # 自动推断初稿态：未显式 draft 时，酒店留空 或 交通全为候选(无已订项) -> 初稿横幅 + 待确认
    if not draft:
        hotels = cfg.get("hotels") or []
        trans = cfg.get("transport") or []
        draft = (not hotels) or (trans and not any(t.get("confirmed") for t in trans))

    # header 背景
    header_key = meta.get("header_bg", "header_airplane")
    header_uri = img_b64(img_dir, header_key)

    # tabs
    tabs = meta.get("tabs")
    if not tabs:
        tabs = []
        for c in meta.get("cities", []):
            tabs.append(f"📍 {c}")
        if meta.get("return_note"):
            tabs.append(meta["return_note"])
    tabs_html = "".join(f'<span class="hl">{esc(t)}</span>' for t in tabs)

    sd, ed = meta.get("start_date", ""), meta.get("end_date", "")
    date_range = sd and ed and f"{sd}—{ed}" or meta.get("date_range", "")
    travel_mode = meta.get("travel_mode", "飞机往返")
    travelers = meta.get("travelers", "")
    sub = f"{esc(date_range)} · {esc(travel_mode)} · {esc(travelers)}"
    weather_note = meta.get("weather_note", "天气为客观预报，临近出发请以实时预报为准")
    footer = meta.get("footer", "本攻略由 travel-guide-generator 生成")

    repl = {
        "{{TITLE}}": esc(meta.get("title", "旅行攻略")),
        "{{SUB}}": sub,
        "{{WEATHER_NOTE}}": esc(weather_note),
        "{{TABS}}": tabs_html,
        "{{HEADER_BG}}": header_uri,
        "{{DRAFT}}": ('<div class="draft-banner">📝 本攻略为初稿 · 交通 / 酒店 / 行程均为「待确认」，确定出行后我会更新状态为「✅ 确定出行」。</div>' if draft else ""),
        "{{TRANSPORT_SECTION}}": render_transport(cfg, img_dir, draft),
        "{{HOTELS_SECTION}}": render_hotels(cfg, img_dir, draft),
        "{{BUDGET_SECTION}}": render_budget(cfg),
        "{{TIMELINE_SECTION}}": render_timeline(cfg, img_dir),
        "{{TIPS_SECTION}}": render_tips(cfg),
        "{{FOOD_SECTION}}": render_food(cfg, img_dir),
        "{{ROUTE_SECTION}}": render_route(cfg, img_dir),
        "{{HIGHLIGHTS_SECTION}}": render_highlights(cfg, img_dir),
        "{{FOOTER}}": esc(footer),
    }
    for k, v in repl.items():
        tpl = tpl.replace(k, v)

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = base / out_path
    out_path.write_text(tpl, encoding="utf-8")
    print(f"✅ 攻略已生成: {out_path}  ({out_path.stat().st_size/1024/1024:.2f} MB)")

if __name__ == "__main__":
    main()
