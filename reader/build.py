"""Build an offline reader using the reviewed story, copy and public visual manifest."""
import argparse
import base64
import json
import mimetypes
import re
from html import escape
from pathlib import Path
from string import Template

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESEARCH = ROOT / "research"


def clock(seconds):
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return (f"{hours:02}:" if hours else "") + f"{minutes:02}:{seconds:02}"


def external(url, label):
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(label)} <span aria-hidden="true">↗</span></a>'


def jump(target, label, cls=""):
    return f'<a class="{cls}" href="#{escape(target)}">{escape(label)}</a>'


def source_record(source, anchors):
    sid = escape(source["id"])
    positions = "".join(
        f'<li data-start="{a["start"]}" data-end="{a["end"]}"><b>{clock(a["start"])}–{clock(a["end"])}</b> {escape(a["label"])}</li>'
        for a in anchors if a["source"] == sid
    )
    timeline = f'<p class="seek-hint">打开此版本原片后，拖至以下时间</p><ul class="clips">{positions}</ul>' if positions else ""
    return f'''<div class="source" data-source="{sid}">
    <div class="source-head"><span class="code">{sid}</span>{external(source["url"], source["title"])}</div>
    <p>{escape(source["publisher"])} · {escape(source["published"])}</p>{timeline}
    <small>{escape(source["access"])} 资料复核于 {escape(source["checked"])}。</small></div>'''


def sources_panel(label, ids, sources, anchors=()):
    records = "".join(source_record(sources[sid], anchors) for sid in ids)
    return f'<details class="sources"><summary>{label}<span class="total">{len(ids)}</span></summary><div class="records">{records}</div></details>'


def picture(visual, position, title, asset_root, caption=""):
    if position not in visual["positions"]:
        raise ValueError(f'{visual["imageId"]} cannot be used for {position}')
    file = asset_root / visual["file"]
    mime = mimetypes.guess_type(file.name)[0]
    if mime not in {"image/svg+xml", "image/jpeg", "image/png", "image/webp"}:
        raise ValueError(f'Unsupported reader image format: {file}')
    uri = f'data:{mime};base64,' + base64.b64encode(file.read_bytes()).decode("ascii")
    img = f'<img src="{uri}" alt="{escape(visual["alt"])}">'
    if position != "轮播" and "放大" in visual["positions"]:
        img = f'''<button type="button" class="enlarge" aria-haspopup="dialog" aria-label="放大图片，{escape(title)}">{img}
        <span class="zoom-mark" aria-hidden="true">⤢</span></button>'''
    kind = escape(visual["type"])
    caption = "原创示意" if kind == "原创示意" else caption
    label = f'<figcaption>{escape(caption)}</figcaption>' if caption else ""
    return f'<figure class="still" data-image="{escape(visual["imageId"])}" data-title="{escape(title)}" data-kind="{kind}">{img}{label}</figure>'


def article(node, prev, nxt, sources, visual, asset_root):
    nid, title = escape(node["id"]), escape(node["title"])
    bg = node["kind"] == "背景"
    image = picture(visual, "正文", node["title"], asset_root)
    drawer = sources_panel("查看出处", node["sourceIds"], sources, node["anchors"])
    previous = jump(prev["id"], "← 上一条") if prev else ""
    following = jump(nxt["id"], "下一条 →", "next") if nxt else ""
    return f'''<article id="{nid}" class="node {'context' if bg else 'story'}" tabindex="-1" data-stage="{escape(node["stage"])}">
    <div class="node-meta"><span class="kind">{"背景旁注" if bg else "关系节点"}</span><span class="code">{nid}</span></div>
    <h3>{title}</h3><p class="event-time"><span>发生时间</span>{escape(node["eventTime"])}</p>
    <p class="story-text">{escape(node["text"])}</p>{image}
    <div class="source-line"><span>资料公开</span> {escape(node["published"])}</div>{drawer}
    <nav class="neighbours" aria-label="{title}的前后节点">{previous}{following}</nav></article>'''


def carousel(frames, visuals, asset_root):
    slides = []
    for i, frame in enumerate(frames):
        visual = visuals[frame["imageId"]]
        if visual["nodeId"] != frame["nodeId"]:
            raise ValueError(f'Carousel image does not match {frame["nodeId"]}')
        image = picture(visual, "轮播", frame["title"], asset_root)
        more = jump(frame["continueNodeId"], frame["continueLabel"] + " →") if "continueNodeId" in frame else ""
        slides.append(f'''<section class="slide" aria-label="第 {i+1} 幕" {"" if i == 0 else "hidden"}>
        {image}<div class="slide-copy"><p class="frame-time">{escape(frame["timeLabel"])}</p>
        <h3>{escape(frame["title"])}</h3><p>{escape(frame["text"])}</p>
        <div class="frame-links">{jump(frame["nodeId"], "阅读本幕正文 ↘")}{more}</div></div></section>''')
    return f'''<section class="reel" aria-label="五幕回顾" aria-roledescription="轮播">
    <header><h2>五幕回顾</h2><span class="counter" aria-live="off">1 / {len(slides)}</span>
    <div class="controls"><button type="button" class="play" aria-pressed="false">播放</button>
    <button type="button" class="prev-frame" aria-label="上一幕">←</button><button type="button" class="next-frame" aria-label="下一幕">→</button></div></header>
    <div class="slides">{"".join(slides)}</div></section>'''


def build(data, copy, visuals, edition, out, asset_root):
    sample = edition == "sample"
    nodes = sorted((n for n in data["nodes"] if not sample or n["id"] in data["sampleIds"]), key=lambda n: n["order"])
    sources = {s["id"]: s for s in data["sources"]}
    card_images = {v["nodeId"]: v for v in visuals if "正文" in v["positions"]}
    articles = {n["id"]: article(n, nodes[i-1] if i else None, nodes[i+1] if i+1 < len(nodes) else None,
                                  sources, card_images[n["id"]], asset_root) for i, n in enumerate(nodes)}
    nav, chapters, ordered = [], [], []
    for group in copy["chapters"]:
        members = [nid for nid in group["nodeIds"] if nid in articles]
        if not members:
            continue
        ordered.extend(members)
        first = next(n for n in nodes if n["id"] == members[0])
        title = escape(group["title"])
        nav.append(f'<a href="#{first["id"]}" data-nav-stage="{escape(first["stage"])}"><span class="nav-dot"></span><span>{title}</span></a>')
        section = "".join(articles[nid] for nid in members)
        chapters.append(f'''<section class="chapter"><header><span class="chapter-num">{group["chapter"]:02}</span><h2>{title}</h2></header>
        <p class="time-basis">{escape(group["timeBasis"])}</p>{section}</section>''')
    if ordered != [n["id"] for n in nodes]:
        raise ValueError("Chapter contents differ from the reviewed story order")

    ending = ""
    reel = ""
    if not sample:
        reel = carousel(copy["frames"], {v["imageId"]: v for v in visuals}, asset_root)
        ending_parts = []
        for part in copy["ending"]["parts"]:
            ending_parts.append(f'''<div><h3>{escape(part["timeLabel"])}</h3><p>{escape(part["text"])}</p>
            {jump(part["nodeId"], "回到这条记录 →")}{sources_panel("查看出处", part["sourceIds"], sources)}</div>''')
        ending = f'''<section class="ending"><h2>{escape(copy["ending"]["title"])}</h2>{"".join(ending_parts)}
        <p>11 月 20 日抢鲜版的完整对白仍待核实。</p>{sources_panel("抢鲜版节目页", ["S15"], sources)}</section>'''

    header = copy["header"]
    portraits = []
    for visual in (v for v in visuals if "封面" in v["positions"]):
        quote = header.get("portraitQuotes", {}).get(visual["imageId"])
        if visual["type"] == "节目单帧" and not quote:
            raise ValueError(f'Missing commentary for {visual["imageId"]}')
        portraits.append(picture(visual, "封面", visual["alt"], asset_root, quote["caption"] if quote else ""))
        if quote:
            source = sources[quote["sourceId"]]
            reference = external(source["url"], quote["linkLabel"])
            portraits.append(f'<details class="portrait-source"><summary>人物资料出处</summary>'
                             f'<p>{escape(source["publisher"])} · {reference}</p></details>')
    # Common copy and pictures are rendered into static HTML. The internal image ledger is never an input.
    variables = dict(
        edition="试读版" if sample else "完整版", css=(HERE/"reader.css").read_text(encoding="utf8"),
        js=(HERE/"reader.js").read_text(encoding="utf8"), intro=escape(data["intro"]),
        years=re.sub(r"\d{4} 年 \d{1,2} 月 \d{1,2} 日", r"<time>\g<0></time>", escape(header["timeLabel"])),
        time_note=escape(header["text"]), portrait="".join(portraits), reel=reel,
        asof=escape(copy["asOf"]), intro_sources=sources_panel("人物与队籍依据", list(dict.fromkeys(data["introSources"] + header["sourceIds"])), sources),
        first=nodes[0]["id"], nav="".join(nav), chapters="".join(chapters), ending=ending,
        count=len(nodes), stages=len(chapters), ordering=escape(data["ordering"]),
    )
    html = Template((HERE/"reader.html").read_text(encoding="utf8")).substitute(variables)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edition", choices=["sample", "full"])
    parser.add_argument("--image-root", type=Path, default=RESEARCH, help="Directory containing the public image files")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    def read(name):
        return json.loads((RESEARCH / name).read_text(encoding="utf8"))
    build(read("friendship.json"), read("reader-copy.json"), read("reader-visuals.json")["images"],
          args.edition, args.out or ROOT/("sample.html" if args.edition == "sample" else "index.html"), args.image_root)
