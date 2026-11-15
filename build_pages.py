"""data/ranked.json → index.html (GitHub Pages에 올리는 페이지)

추천은 점수로 자동으로 고른다(오늘 새 공고 우선, 최대 10개). 숨긴 공고는 각 기기의 브라우저에만 저장된다.
"""
import html
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MIN_SCORE = 4      # '그 밖의 공고'에 넣을 최소 점수
MAX_OTHERS = 80
MAX_PICKS = 10
PICK_SCORE = 5    # 추천에 넣을 최소 점수
OLD_DAYS = 30     # 지난 공고는 최근 30일 안에 올라온 것만

e = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731
DIR_NAME = {"A": "앱 그래픽 · BX · 캐릭터", "B": "정보 · 편집 · 사회적 가치"}
WEEK = "월화수목금토일"


def chip_site(site):
    cls = {"원티드": "wt", "사람인": "sr", "잡코리아": "jk", "임팩트커리어": "ic"}.get(site, "")
    return f'<span class="site {cls}">{e(site)}</span>'


def meta_line(j):
    parts = [j.get("company"), j.get("location"), j.get("experience")]
    dl = j.get("deadline")
    if dl:
        parts.append(f"마감 {dl}" if not str(dl).startswith("~") else f"마감 {dl[1:].strip()}")
    return " · ".join(e(p) for p in parts if p)


def posted_html(j, today):
    """공고가 올라온 날: '11/13 등록 · 2일 전'"""
    p = j.get("posted")
    if not p:
        return ""
    pd = date.fromisoformat(p)
    days = (today - pd).days
    ago = "오늘" if days <= 0 else ("어제" if days == 1 else f"{days}일 전")
    kind = {"등록": "올라옴", "수정": "수정됨", "확인": "처음 확인"}.get(j.get("posted_kind"), "")
    fresh = " fresh" if days <= 2 and j.get("posted_kind") != "확인" else ""
    return (f'<span class="posted{fresh}"><time datetime="{p}">{pd.month}/{pd.day}</time> {kind}'
            f' · {ago}</span>')


def x_button(j):
    return (f'<button type="button" class="x" data-hide="{e(j["id"])}" '
            f'aria-label="이 공고 숨기기: {e(j["title"])}" title="숨기기">×</button>')


def main():
    d = json.loads((DATA / "ranked.json").read_text())
    jobs = {j["id"]: j for j in d["jobs"]}
    today = date.fromisoformat(d["date"])

    def fresh_enough(j):
        return (today - date.fromisoformat(j.get("posted") or d["date"])).days <= OLD_DAYS

    def group_of(j):
        dirs = j.get("direction", "A")
        if dirs == "B" or j["site"] == "임팩트커리어":
            return "B"
        if dirs == "AB" and len(j.get("tags_B", [])) > len(j.get("tags_A", [])):
            return "B"
        return "A"

    cand = [j for j in d["jobs"] if j["score"] >= PICK_SCORE and fresh_enough(j)]
    cand.sort(key=lambda j: (not j["is_new"], -j["score"], -int((j.get("posted") or "0").replace("-", ""))))
    chosen = cand[:MAX_PICKS]
    p = {"picks": [{"id": j["id"], "direction": group_of(j)} for j in chosen]}
    new_today = sum(1 for j in d["jobs"] if j["is_new"] and j["score"] >= MIN_SCORE)
    p["summary"] = (f"오늘 새로 올라온 관련 공고는 {new_today}개예요. 점수가 높은 공고 {len(chosen)}개를 추천으로 골랐고, "
                    "관심 없는 공고는 ×로 숨기면 이 기기에서는 다시 보이지 않아요.")
    by_site = {}
    for j in d["jobs"]:
        by_site[j["site"]] = by_site.get(j["site"], 0) + 1
    new_count = sum(1 for j in d["jobs"] if j["is_new"] and j["score"] >= MIN_SCORE)

    pick_ids, missing = set(), []
    sections = []
    for key in ("A", "B"):
        cards = []
        for pk in p["picks"]:
            if pk["direction"] != key:
                continue
            j = jobs.get(pk["id"])
            if not j:
                missing.append(pk["id"])
                continue
            pick_ids.add(pk["id"])
            new = '<span class="new">NEW</span>' if j["is_new"] else ""
            cards.append(f"""
      <article class="pick" data-id="{e(j['id'])}" data-title="{e(j['title'])}" data-company="{e(j['company'])}">
        <div class="pick-top">{chip_site(j['site'])}{new}{posted_html(j, today)}{x_button(j)}</div>
        <h3><a href="{e(j['url'])}" target="_blank" rel="noopener">{e(j['title'])}</a></h3>
        <p class="meta">{meta_line(j)}</p>
      </article>""")
        if cards:
            sections.append(f"""
    <section class="group" data-picks aria-labelledby="g{key}">
      <h2 id="g{key}"><span class="dir dir-{key}">{key}</span>{e(DIR_NAME[key])}<span class="count">{len(cards)}</span></h2>
      <div class="picks">{''.join(cards)}
      </div>
    </section>""")

    relevant = [j for j in d["jobs"] if j["id"] not in pick_ids and j["score"] >= MIN_SCORE]
    new_rel = [j for j in relevant if j["is_new"]]
    others = [j for j in relevant if not j["is_new"]
              and (today - date.fromisoformat(j.get("posted") or d["date"])).days <= OLD_DAYS][:MAX_OTHERS]
    low_count = sum(1 for j in d["jobs"] if j["score"] < MIN_SCORE)

    def new_row(j):
        return f"""
      <article class="pick slim" data-id="{e(j['id'])}" data-title="{e(j['title'])}" data-company="{e(j['company'])}">
        <div class="pick-top">{chip_site(j['site'])}<span class="new">NEW</span>{posted_html(j, today)}{x_button(j)}</div>
        <h3><a href="{e(j['url'])}" target="_blank" rel="noopener">{e(j['title'])}</a></h3>
        <p class="meta">{meta_line(j)}</p>
      </article>"""
    new_html = "".join(new_row(j) for j in new_rel) or '<p class="empty">추천 말고 오늘 새로 올라온 관련 공고는 없어요.</p>'
    rows = []
    for j in others:
        dirs = j.get("direction", "A")
        new = '<span class="new">NEW</span>' if j["is_new"] else ""
        rows.append(f"""
        <li data-id="{e(j['id'])}" data-title="{e(j['title'])}" data-company="{e(j['company'])}" data-site="{e(j['site'])}" data-dir="{e(dirs)}" data-new="{'1' if j['is_new'] else '0'}" data-posted="{e(j.get('posted',''))}">
          <div class="row-top">{chip_site(j['site'])}{''.join(f'<span class="dir dir-{c} sm">{c}</span>' for c in dirs)}{new}{posted_html(j, today)}{x_button(j)}</div>
          <a href="{e(j['url'])}" target="_blank" rel="noopener">{e(j['title'])}</a>
          <span class="meta">{meta_line(j)}</span>
        </li>""")

    errs = "".join(f"<li>{e(x)}</li>" for x in d.get("errors", []))
    err_block = f'<div class="warn"><strong>오늘 일부를 가져오지 못했어요.</strong><ul>{errs}</ul></div>' if errs else ""
    site_stats = " · ".join(
        f'{s} {by_site.get(s, 0)}개'
        for s in ("사람인", "잡코리아", "임팩트커리어"))

    page = TEMPLATE.format(
        date_label=f"{today.year}년 {today.month}월 {today.day}일 ({WEEK[today.weekday()]})",
        summary=e(p.get("summary", "")), new=new_count, pick_count=len(pick_ids), site_stats=site_stats,
        err_block=err_block, sections="".join(sections), other_count=len(others), rows="".join(rows),
        new_html=new_html, new_rel_count=len(new_rel), total=len(d["jobs"]), low_count=low_count,
    )
    doc = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
           '<meta name="robots" content="noindex,nofollow">\n</head>\n<body>\n' + page + '\n</body>\n</html>\n')
    (ROOT / "index.html").write_text(doc)
    print(json.dumps({"picks": len(pick_ids), "missing": missing, "others": len(others)}, ensure_ascii=False))


TEMPLATE = """<title>디자이너 공고 브리핑</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;700&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
/* Layout: one reading column — daily summary strip, curated picks by direction, then a filterable full list */
:root {{
  --bg: #F3F5F8; --surface: #FFFFFF; --ink: #17202E; --muted: #5B6677; --line: #DCE1E9;
  --a: #2F55D4; --a-soft: #E6ECFC; --b: #11806A; --b-soft: #DDF2EC;
  --hi: #11806A; --mid: #8A6A12; --mid-soft: #FBF1D6; --low: #5B6677; --low-soft: #ECEFF4;
  --new: #C2410C; --warn-bg: #FFF4E5;
  --wt: #3366FF; --sr: #2F6FE4; --jk: #00A0E9; --ic: #C2410C;
  --font: "IBM Plex Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #0F141C; --surface: #171E29; --ink: #E7ECF3; --muted: #9AA5B5; --line: #2A3342;
  --a: #8AA4FF; --a-soft: #1F2A4A; --b: #5CCFB2; --b-soft: #163A33;
  --hi: #5CCFB2; --mid: #E6C463; --mid-soft: #3A3218; --low: #9AA5B5; --low-soft: #242C38;
  --new: #FB923C; --warn-bg: #3A2A14; --wt: #8AA4FF; --sr: #8AB4FF; --jk: #5CCBFF; --ic: #FB923C; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #0F141C; --surface: #171E29; --ink: #E7ECF3; --muted: #9AA5B5; --line: #2A3342;
  --a: #8AA4FF; --a-soft: #1F2A4A; --b: #5CCFB2; --b-soft: #163A33;
  --hi: #5CCFB2; --mid: #E6C463; --mid-soft: #3A3218; --low: #9AA5B5; --low-soft: #242C38;
  --new: #FB923C; --warn-bg: #3A2A14; --wt: #8AA4FF; --sr: #8AB4FF; --jk: #5CCBFF; --ic: #FB923C; color-scheme: dark; }}
[hidden] {{ display: none !important; }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: var(--font); font-size: 15px; line-height: 1.6; }}
.wrap {{ max-width: 760px; margin: 0 auto; padding-block: 28px 64px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: flex; flex-direction: column; gap: 32px; }}
header {{ display: flex; flex-direction: column; gap: 10px; }}
.eyebrow {{ font-size: 13px; color: var(--muted); letter-spacing: .02em; }}
h1 {{ font-size: 26px; line-height: 1.3; margin: 0; text-wrap: balance; }}
.summary {{ margin: 0; color: var(--ink); max-width: 62ch; }}
.stats {{ display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }}
.stat {{ display: flex; flex-direction: column; padding: 10px 12px; border-left: 1px solid var(--line); min-width: 0; }}
.stat:first-child {{ border-left: 0; }}
.num {{ font-family: var(--mono); font-size: 20px; font-variant-numeric: tabular-nums; }}
.stat.newstat .num {{ color: var(--new); }}
.lbl {{ font-size: 12px; color: var(--muted); }}
.warn {{ background: var(--warn-bg); border-radius: 8px; padding: 12px 14px; font-size: 14px; }}
.warn ul {{ margin: 6px 0 0; padding-left: 18px; }}
.group {{ display: flex; flex-direction: column; gap: 12px; }}
h2 {{ font-size: 18px; margin: 0; display: flex; align-items: center; gap: 8px; }}
h2 .count {{ font-family: var(--mono); font-size: 13px; color: var(--muted); font-weight: 500; }}
.dir {{ display: inline-grid; place-items: center; width: 22px; height: 22px; border-radius: 6px; font-family: var(--mono); font-size: 12px; font-weight: 500; }}
.dir.sm {{ width: 18px; height: 18px; font-size: 11px; border-radius: 5px; }}
.dir-A {{ background: var(--a-soft); color: var(--a); }}
.dir-B {{ background: var(--b-soft); color: var(--b); }}
.picks {{ display: flex; flex-direction: column; gap: 10px; }}
.pick {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 4px; min-width: 0; }}
.pick-top, .row-top {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }}
.pick h3 {{ font-size: 16px; margin: 4px 0 0; line-height: 1.4; }}
a {{ color: var(--ink); text-decoration: none; }}
a:hover {{ color: var(--a); text-decoration: underline; text-underline-offset: 3px; }}
a:focus-visible, button:focus-visible {{ outline: 2px solid var(--a); outline-offset: 2px; border-radius: 4px; }}
.meta {{ margin: 0; font-size: 13px; color: var(--muted); }}
.why {{ margin: 6px 0 0; font-size: 14px; }}
.site {{ font-size: 12px; font-weight: 500; padding: 1px 8px; border-radius: 999px; border: 1px solid currentColor; }}
.site.wt {{ color: var(--wt); }} .site.sr {{ color: var(--sr); }} .site.jk {{ color: var(--jk); }} .site.ic {{ color: var(--ic); }}
.fit {{ font-size: 12px; padding: 1px 8px; border-radius: 999px; }}
.fit.hi {{ background: var(--b-soft); color: var(--hi); }}
.fit.mid {{ background: var(--mid-soft); color: var(--mid); }}
.fit.low {{ background: var(--low-soft); color: var(--low); }}
.new {{ font-family: var(--mono); font-size: 11px; color: var(--new); letter-spacing: .06em; }}
.filters {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.filters button {{ font: inherit; font-size: 13px; padding: 4px 12px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--ink); cursor: pointer; }}
.filters button[aria-pressed="true"] {{ background: var(--ink); color: var(--bg); border-color: var(--ink); }}
.list {{ list-style: none; margin: 0; padding: 0; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }}
.list li {{ display: flex; flex-direction: column; gap: 2px; padding: 10px 14px; border-top: 1px solid var(--line); min-width: 0; }}
.list li:first-child {{ border-top: 0; }}
.list a {{ font-weight: 500; }}
.empty {{ padding: 16px; color: var(--muted); }}
footer {{ font-size: 12px; color: var(--muted); }}
.posted {{ font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }}
.posted.fresh {{ color: var(--new); }}
.x {{ margin-left: auto; width: 32px; height: 32px; margin-block: -6px; margin-right: -8px; border: 0; border-radius: 8px;
  background: transparent; color: var(--muted); font-size: 20px; line-height: 1; cursor: pointer; }}
.x:hover {{ background: var(--low-soft); color: var(--ink); }}
.toolbar {{ display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; justify-content: space-between; }}
.hidden-bar {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }}
.linkbtn {{ font: inherit; font-size: 13px; background: none; border: 0; padding: 4px 0; color: var(--a); cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }}
.hidden-list {{ list-style: none; margin: 0; padding: 0; background: var(--surface); border: 1px dashed var(--line); border-radius: 10px; }}
.hidden-list li {{ display: flex; gap: 12px; align-items: center; justify-content: space-between; padding: 8px 14px; border-top: 1px solid var(--line); font-size: 13px; }}
.hidden-list li:first-child {{ border-top: 0; }}
.hidden-list span {{ min-width: 0; color: var(--muted); }}
.toast {{ position: fixed; left: 50%; transform: translateX(-50%); bottom: calc(20px + env(safe-area-inset-bottom, 0px));
  display: flex; gap: 14px; align-items: center; background: var(--ink); color: var(--bg); padding: 10px 16px; border-radius: 10px;
  font-size: 14px; box-shadow: 0 6px 24px rgba(0,0,0,.18); max-width: calc(100% - 32px); z-index: 20; }}
.toast button {{ font: inherit; background: none; border: 0; color: var(--bg); font-weight: 700; text-decoration: underline; cursor: pointer; }}
.pick.slim .meta {{ margin-top: 0; }}
.older > summary {{ list-style: none; cursor: pointer; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; padding: 12px 14px;
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }}
.older > summary::-webkit-details-marker {{ display: none; }}
.older > summary h2::before {{ content: "▸"; color: var(--muted); font-size: 14px; }}
.older[open] > summary h2::before {{ content: "▾"; }}
.older[open] {{ gap: 12px; }}
.hint {{ font-size: 13px; color: var(--muted); }}
.sync {{ font-size: 12px; color: var(--muted); }}
@media (max-width: 520px) {{
  h1 {{ font-size: 22px; }}
}}
</style>
<div class="wrap">
  <header>
    <span class="eyebrow">{date_label} · 서울 · 경기 · 대전</span>
    <h1>오늘의 디자이너 공고</h1>
    <p class="summary">{summary}</p>
    <div class="stats">
      <div class="stat"><span class="num">{pick_count}</span><span class="lbl">오늘의 추천</span></div>
      <div class="stat newstat"><span class="num">{new}</span><span class="lbl">오늘 새 관련 공고</span></div>
      <div class="stat"><span class="num">{other_count}</span><span class="lbl">지난 30일 관련 공고</span></div>
    </div>
  </header>
  {err_block}
  <div class="hidden-bar" id="hidden-bar" hidden>
    <span id="hidden-count"></span>
    <button type="button" class="linkbtn" id="hidden-toggle" aria-expanded="false" aria-controls="hidden-list">숨긴 공고 보기</button>
    <span class="sync" id="sync-note"></span>
  </div>
  <ul class="hidden-list" id="hidden-list" hidden></ul>
  {sections}
  <section class="group" aria-labelledby="gnew">
    <h2 id="gnew">오늘 새로 올라온 공고<span class="count">{new_rel_count}</span></h2>
    <div class="picks">{new_html}
    </div>
  </section>
  <details class="group older" id="older">
    <summary><h2 id="gall">지난 30일 관련 공고<span class="count" id="other-count">{other_count}</span></h2><span class="hint">필요할 때만 펼쳐 보세요</span></summary>
    <div class="toolbar">
      <div class="filters" role="group" aria-label="공고 거르기">
        <button type="button" id="f-all" data-f="all" aria-pressed="true">전체</button>
        <button type="button" id="f-A" data-f="A" aria-pressed="false">A 앱·BX·캐릭터</button>
        <button type="button" id="f-B" data-f="B" aria-pressed="false">B 정보·편집·사회</button>
      </div>
      <div class="filters" role="group" aria-label="정렬">
        <button type="button" id="s-fit" data-s="fit" aria-pressed="true">추천순</button>
        <button type="button" id="s-date" data-s="date" aria-pressed="false">최신순</button>
      </div>
    </div>
    <ul class="list" id="list">{rows}
    </ul>
    <p class="empty" id="empty" hidden>이 조건에 맞는 공고가 없어요.</p>
  </details>
  <footer>오늘 모은 공고 {total}개 ({site_stats}) 중 직무 관련도가 낮은 {low_count}개는 뺐어요. 사람인 · 잡코리아 · 임팩트커리어의 공개 검색 결과에서 설정한 지역·경력 조건에 맞는 공고만 모았어요. 마감일과 세부 조건은 공고 원문에서 꼭 확인하세요. 숨긴 공고는 이 기기의 브라우저에만 저장돼요. 원티드 공고는 원티드 앱의 알림으로 확인하세요.</footer>
</div>
<script>
(function () {{
  var hidden = new Map();          // id -> {{title, company}}
  var filter = 'all', sort = 'fit', db = null, usingDb = false;
  var list = document.getElementById('list');
  var original = Array.prototype.slice.call(list.children);
  function ls(get, val) {{
    try {{ if (get) return JSON.parse(localStorage.getItem(get) || 'null'); localStorage.setItem(val[0], JSON.stringify(val[1])); }} catch (e) {{ return null; }}
  }}
  var saved = ls('jobView') || {{}};
  if (['all', 'A', 'B'].indexOf(saved.filter) >= 0) filter = saved.filter;
  if (saved.sort) sort = saved.sort;
  (ls('hiddenLocal') || []).forEach(function (h) {{ hidden.set(h.id, h); }});

  function infoFor(id) {{
    var el = document.querySelector('[data-id="' + CSS.escape(id) + '"]');
    return {{ id: id, title: el ? el.dataset.title : id, company: el ? el.dataset.company : '' }};
  }}
  function render() {{
    document.querySelectorAll('.pick').forEach(function (c) {{ c.hidden = hidden.has(c.dataset.id); }});
    document.querySelectorAll('.group[data-picks]').forEach(function (g) {{
      var left = g.querySelectorAll('.pick:not([hidden])').length;
      g.hidden = left === 0; g.querySelector('.count').textContent = left;
    }});
    var items = original.slice();
    if (sort === 'date') items.sort(function (a, b) {{ return (b.dataset.posted || '').localeCompare(a.dataset.posted || ''); }});
    var shown = 0;
    items.forEach(function (li) {{
      list.appendChild(li);
      var ok = !hidden.has(li.dataset.id) && (filter === 'all' || (filter === 'new' ? li.dataset.new === '1' : li.dataset.dir.indexOf(filter) >= 0));
      li.hidden = !ok; if (ok) shown++;
    }});
    document.getElementById('empty').hidden = shown > 0;
    document.getElementById('other-count').textContent = original.filter(function (li) {{ return !hidden.has(li.dataset.id); }}).length;
    document.querySelectorAll('[data-f]').forEach(function (b) {{ b.setAttribute('aria-pressed', String(b.dataset.f === filter)); }});
    document.querySelectorAll('[data-s]').forEach(function (b) {{ b.setAttribute('aria-pressed', String(b.dataset.s === sort)); }});
    var onPage = Array.from(hidden.keys()).filter(function (id) {{ return document.querySelector('[data-id="' + CSS.escape(id) + '"]'); }});
    var bar = document.getElementById('hidden-bar');
    bar.hidden = onPage.length === 0;
    document.getElementById('hidden-count').textContent = '숨긴 공고 ' + onPage.length + '개';
    document.getElementById('hidden-toggle').hidden = onPage.length === 0;
    var hl = document.getElementById('hidden-list');
    hl.textContent = '';
    onPage.forEach(function (id) {{
      var h = hidden.get(id), li = document.createElement('li'), t = document.createElement('span'), b = document.createElement('button');
      t.textContent = (h.company ? h.company + ' · ' : '') + h.title;
      b.type = 'button'; b.className = 'linkbtn'; b.textContent = '다시 보기'; b.dataset.restore = id;
      li.appendChild(t); li.appendChild(b); hl.appendChild(li);
    }});
    if (onPage.length === 0) {{ hl.hidden = true; document.getElementById('hidden-toggle').setAttribute('aria-expanded', 'false'); }}
  }}
  function saveLocal() {{ if (!usingDb) ls(null, ['hiddenLocal', Array.from(hidden.values())]); }}
  function setHidden(id, on) {{
    if (on) hidden.set(id, infoFor(id)); else hidden.delete(id);
    render(); saveLocal();
    if (usingDb) {{
      var ref = db.collection('hidden').doc(id);
      var p = on ? ref.set({{ title: hidden.get(id).title, company: hidden.get(id).company, hiddenAt: new Date().toISOString() }}) : ref.delete();
      p.catch(function () {{ note('저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.'); }});
    }}
  }}
  var toastTimer;
  function toast(id) {{
    var t = document.getElementById('toast');
    t.querySelector('span').textContent = '공고를 숨겼어요';
    t.querySelector('button').dataset.restore = id;
    t.hidden = false; clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {{ t.hidden = true; }}, 5000);
  }}
  function note(msg) {{ document.getElementById('sync-note').textContent = msg; document.getElementById('hidden-bar').hidden = false; }}

  document.addEventListener('click', function (ev) {{
    var b = ev.target.closest('button'); if (!b) return;
    if (b.dataset.hide) {{ setHidden(b.dataset.hide, true); toast(b.dataset.hide); }}
    else if (b.dataset.restore) {{ setHidden(b.dataset.restore, false); document.getElementById('toast').hidden = true; }}
    else if (b.dataset.f) {{ filter = b.dataset.f; ls(null, ['jobView', {{ filter: filter, sort: sort }}]); render(); }}
    else if (b.dataset.s) {{ sort = b.dataset.s; ls(null, ['jobView', {{ filter: filter, sort: sort }}]); render(); }}
    else if (b.id === 'hidden-toggle') {{
      var hl = document.getElementById('hidden-list'); hl.hidden = !hl.hidden;
      b.setAttribute('aria-expanded', String(!hl.hidden)); b.textContent = hl.hidden ? '숨긴 공고 보기' : '숨긴 공고 접기';
    }}
  }});
  render();

}})();
</script>
<div class="toast" id="toast" role="status" hidden><span></span><button type="button">되돌리기</button></div>
"""

if __name__ == "__main__":
    main()
