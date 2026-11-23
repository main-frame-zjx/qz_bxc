"""Build the two offline editions from the reviewed research handoff (Python 3.11+)."""
import argparse
import base64
import hashlib
import json
from html import escape
from itertools import groupby
from pathlib import Path
from string import Template

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


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
    <p>{escape(source["publisher"])} · {escape(source["published"])}</p>
    <p>{escape(source["support"])}</p>{timeline}
    <small>{escape(source["access"])} 资料复核于 {escape(source["checked"])}。</small></div>'''


def sources_panel(label, ids, sources, anchors=()):
    records = "".join(source_record(sources[sid], anchors) for sid in ids)
    return f'<details class="sources"><summary>{label}<span class="total">{len(ids)}</span></summary><div class="records">{records}</div></details>'


def figure(photo, data_uri, hero=False):
    title = "认一认两位选手" if hero else "心结卡对话现场"
    credit = escape(photo["credit"])
    caption = escape(photo["caption"])
    note = (f'<div class="names"><span><i></i>青稚 <small>张庆波</small></span>'
            f'<span><i></i>白小纯 <small>陈礼根</small></span></div>') if hero else ""
    return f'''<figure class="still" data-image="{escape(photo["id"])}">
    <button type="button" class="enlarge" aria-haspopup="dialog" aria-label="放大图片，{title}">
    <img src="{data_uri}" alt="{escape(photo["alt"])}" width="{photo["size"][0]}" height="{photo["size"][1]}">
    <span class="zoom-mark" aria-hidden="true">⤢</span></button>
    <figcaption>{note}<span class="caption">{caption}</span><small class="credit">{credit}</small></figcaption></figure>'''


def article(node, prev, nxt, sources, photos, uris):
    nid, title = escape(node["id"]), escape(node["title"])
    bg = node["kind"] == "背景"
    photo_html = "".join(figure(photos[i], uris[i]) for i in node["imageIds"])
    drawer = sources_panel("查看出处", node["sourceIds"], sources, node["anchors"])
    previous = jump(prev["id"], "← 上一条") if prev else ""
    following = jump(nxt["id"], "下一条 →", "next") if nxt else ""
    return f'''<article id="{nid}" class="node {'context' if bg else 'story'}" tabindex="-1" data-stage="{escape(node["stage"])}">
    <div class="node-meta"><span class="kind">{"背景旁注" if bg else "关系节点"}</span><span class="code">{nid}</span></div>
    <h3>{title}</h3><p class="event-time"><span>发生时间</span>{escape(node["eventTime"])}</p>
    <p class="story-text">{escape(node["text"])}</p>{photo_html}
    <div class="source-line"><span>资料公开</span> {escape(node["published"])}</div>{drawer}
    <nav class="neighbours" aria-label="{title}的前后节点">{previous}{following}</nav></article>'''


def build(data, edition, out, image_root):
    sample = edition == "sample"
    nodes = sorted((n for n in data["nodes"] if not sample or n["id"] in data["sampleIds"]), key=lambda n: n["order"])
    sources = {s["id"]: s for s in data["sources"]}
    photos = {p["id"]: p for p in data["images"]}
    uris = {}
    for pid in {i for n in nodes for i in n["imageIds"]}:
        p = photos[pid]
        raw = (image_root / p["file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != p["sha256"]:
            raise ValueError(f"Image checksum mismatch for {pid}")
        uris[pid] = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")

    photo = photos["F01"]
    articles = {n["id"]: article(n, nodes[i-1] if i else None, nodes[i+1] if i+1<len(nodes) else None, sources, photos, uris)
                for i, n in enumerate(nodes)}
    nav, chapters = [], []
    for idx, (stage, group) in enumerate(groupby(nodes, key=lambda n: n["stage"]), 1):
        members = list(group)
        target = next((n for n in members if n["kind"] != "背景"), members[0])
        count_label = f'背景 · {len(members):02}' if target["kind"] == "背景" else f'{len(members):02}'
        nav.append(f'<a href="#{target["id"]}" data-nav-stage="{escape(stage)}"><span class="nav-dot"></span>{escape(stage)}<small>{count_label}</small></a>')
        section = "".join(articles[n["id"]] for n in members)
        chapters.append(f'<section class="chapter" aria-label="{escape(stage)}"><header><span class="chapter-num">{idx:02}</span><h2>{escape(stage)}</h2></header>{section}</section>')
    ending = ""
    if not sample:
        last = data["lastInteraction"]
        ending = f'''<section class="ending"><h2>最近一次可核实的互动</h2><p>{escape(last["text"])}</p>
        {jump(last["node"], "回到这次互动 →")}{sources_panel("查看结尾出处", ["S19", "S15", "S14"], sources)}</section>'''
    identify = f'<p>{escape(photo["identityCheck"])}</p><p>{escape(photo["basis"])}</p><p>{external(sources["S22"]["url"], "查看图片引用依据")} · {external(sources[photo["source"]]["url"], "查看节目原片")}</p>'
    variables = dict(
        edition="试读版" if sample else "完整版", css=(HERE/"reader.css").read_text(encoding="utf8"),
        js=(HERE/"reader.js").read_text(encoding="utf8"), intro=escape(data["intro"]),
        portrait=figure(photo, uris["F01"], True), identify=identify, asof=escape(data["asOf"]),
        intro_sources=sources_panel("人物资料出处", data["introSources"], sources),
        first=nodes[0]["id"], nav="".join(nav), chapters="".join(chapters), ending=ending,
        count=len(nodes), stages=len(chapters), ordering=escape(data["ordering"]),
    )
    html = Template((HERE/"reader.html").read_text(encoding="utf8")).substitute(variables)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("edition", choices=["sample", "full"])
    parser.add_argument("--image-root", type=Path, help="Directory of the research handoff containing images/F01.jpg")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    data = json.loads((ROOT/"research/friendship.json").read_text(encoding="utf8"))
    image_root = args.image_root or (ROOT.parents[2] / data["images"][0]["projectFile"]).parent.parent
    build(data, args.edition, args.out or ROOT/("sample.html" if args.edition=="sample" else "index.html"), image_root)
