"""사람인·원티드·잡코리아에서 디자이너 공고를 모아 1차로 거른 뒤 JSON으로 저장한다.

사용: python3 -I collect.py  →  data/today.json (새 공고 표시 포함), data/seen.json 갱신
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130 Safari/537.36")

# 방향 A: 앱 그래픽·BX·캐릭터 / 방향 B: 정보·편집·사회적 가치
KEYWORDS = {
    "A": ["그래픽디자이너", "BX디자이너", "브랜드디자이너", "캐릭터디자이너",
          "일러스트레이터", "콘텐츠디자이너", "마케팅디자이너"],
    "B": ["편집디자이너", "인포그래픽", "정보디자인", "교육콘텐츠 디자이너",
          "사회적기업 디자이너"],
}
REGIONS = ("서울", "경기", "대전")
TITLE_HINT = re.compile(r"디자인|디자이너|일러스트|그래픽|BX|브랜드|캐릭터|콘텐츠|편집|인포그래픽|Designer|Design", re.I)
EXCLUDE = re.compile(
    r"인테리어|실내|건축|조경|패션|의류|가구|제품디자인|산업디자인|CAD|텍스타일|주얼리|쥬얼리|"
    r"퍼블리셔|개발자|엔지니어|헤어|네일|메이크업|공간디자인|VMD|조명|자동차|기구설계|3D 모델러|"
    r"UX 리서처|프론트엔드|영업|MD$|웨딩|꽃|플로리스트", re.I)
BONUS = {
    "A": ["캐릭터", "아이콘", "앱", "브랜드", "BX", "일러스트", "이모티콘", "굿즈", "프로모션", "콘텐츠", "마케팅", "그래픽"],
    "B": ["인포그래픽", "정보", "편집", "출판", "교육", "공공", "사회적", "비영리", "재단", "쉬운", "접근성", "아동", "청소년"],
}


def get(url, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(2)


def exp_ok(text):
    """경력 약 4~5년인 사람이 지원 가능한지. 판단 불가면 True."""
    t = text.replace(" ", "")
    if "무관" in t or "신입·경력" in t or "신입/경력" in t:
        return True
    if "인턴" in t:
        return False
    m = re.search(r"(\d+)년~(\d+)년", t)  # 임팩트커리어 형식: '3년 ~ 8년'
    if m:
        return int(m.group(1)) <= 5 and int(m.group(2)) >= 3
    m = re.search(r"신입~(\d+)년", t)
    if m:
        return int(m.group(1)) >= 3
    if re.fullmatch(r".*신입.*", t) and "경력" not in t:
        return False
    m = re.search(r"(\d+)~(\d+)년", t)
    if m:
        return int(m.group(1)) <= 5 and int(m.group(2)) >= 3
    m = re.search(r"경력(\d+)년", t)
    if m:
        return int(m.group(1)) <= 5
    return True


def region_ok(loc):
    return any(loc.startswith(r) or r in loc[:4] for r in REGIONS)


def tags_for(title, extra=""):
    hay = f"{title} {extra}"
    return {k: [w for w in v if w.lower() in hay.lower()] for k, v in BONUS.items()}


# ---------------- 원티드 ----------------
WANTED_HEADERS = {
    "User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.wanted.co.kr/wdlist/511?country=kr&job_sort=job.latest_order&years=-1&locations=all",
    "Origin": "https://www.wanted.co.kr", "wanted-user-country": "KR", "wanted-user-language": "ko",
    "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty",
}
WANTED_LOG = []   # 어떤 주소로 접속했는지 (실행 기록에 남긴다)


def wanted_get(path_and_query):
    """원티드는 해외 서버 접속을 막을 때가 있어, 주소와 머리말을 바꿔 가며 차례로 시도한다."""
    last = None
    for host in ("https://www.wanted.co.kr", "https://wanted.co.kr"):
        url = host + path_and_query
        try:
            req = urllib.request.Request(url, headers=WANTED_HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                WANTED_LOG.append(f"ok {url[:80]}")
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:  # noqa: BLE001
            last = e
            WANTED_LOG.append(f"fail {url[:80]}: {e}")
            time.sleep(1)
    raise last


def wanted():
    out = []
    loc = "&".join(f"locations={x}" for x in ("seoul.all", "gyeonggi.all", "daejeon.all"))
    endpoints = [
        "/api/v4/jobs?country=kr&tag_type_ids=511&{loc}&years=-1&limit=100&offset={off}&job_sort=job.latest_order",
        "/api/chaos/navigation/v1/results?job_group_id=511&country=kr&{loc}&years=-1&limit=100&offset={off}&job_sort=job.latest_order",
    ]
    for ep in endpoints:
        try:
            wanted_get(ep.format(loc=loc, off=0))
            break
        except Exception:  # noqa: BLE001
            continue
    else:
        raise RuntimeError("원티드 접속이 모두 막혔어요 (" + " / ".join(WANTED_LOG[-4:]) + ")")
    for off in range(0, 600, 100):
        d = wanted_get(ep.format(loc=loc, off=off))
        rows = d.get("data") or []
        for j in rows:
            a_from, a_to = j.get("annual_from", 0), j.get("annual_to", 100)
            exp = "경력무관" if (a_from == 0 and a_to >= 100) else f"경력 {a_from}~{a_to}년"
            addr = j.get("address") or {}
            out.append({
                "site": "원티드", "id": f"w{j['id']}", "title": j.get("position", ""),
                "company": (j.get("company") or {}).get("name", ""),
                "location": f"{addr.get('location','')} {addr.get('district','')}".strip(),
                "experience": exp, "deadline": j.get("due_time") or "상시",
                "url": f"https://www.wanted.co.kr/wd/{j['id']}", "query": "디자인 전체",
                "_exp_ok": a_from <= 5 and a_to >= 3,
            })
        if len(rows) < 100:
            break
        time.sleep(0.5)
    return out


# ---------------- 사람인 ----------------
def saramin(word):
    q = urllib.parse.quote(word)
    url = (f"https://www.saramin.co.kr/zf_user/search/recruit?searchword={q}"
           f"&loc_mcd=101000%2C102000%2C105000&recruitPageCount=60&recruitSort=reg_dt")
    s = get(url)
    out = []
    for blk in s.split('class="item_recruit"')[1:]:
        rid = re.search(r'value="(\d+)"', blk)
        tit = re.search(r'<h2 class="job_tit">\s*<a[^>]*title="([^"]*)"', blk)
        corp = re.search(r'class="corp_name">\s*<a[^>]*>\s*([^<]+)', blk)
        cond = re.search(r'<div class="job_condition">(.*?)</div>', blk, re.S)
        date_ = re.search(r'<span class="date">([^<]*)</span>', blk)
        sector = re.search(r'<div class="job_sector">(.*?)<span class="job_day"', blk, re.S)
        day = re.search(r'<span class="job_day">\s*(등록일|수정일)\s*(\d{2})/(\d{2})/(\d{2})', blk)
        if not (rid and tit):
            continue
        spans = [re.sub(r"<[^>]+>", " ", x) for x in re.findall(r"<span>(.*?)</span>", cond.group(1), re.S)] if cond else []
        spans = [re.sub(r"\s+", " ", html.unescape(x)).strip() for x in spans]
        out.append({
            "site": "사람인", "id": f"s{rid.group(1)}", "title": html.unescape(tit.group(1)),
            "company": html.unescape(corp.group(1).strip()) if corp else "",
            "location": spans[0] if spans else "", "experience": spans[1] if len(spans) > 1 else "",
            "type": spans[3] if len(spans) > 3 else "",
            "deadline": html.unescape(date_.group(1)).strip() if date_ else "",
            "sector": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", sector.group(1)))).strip() if sector else "",
            "url": f"https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx={rid.group(1)}",
            "query": word,
            "posted": f"20{day.group(2)}-{day.group(3)}-{day.group(4)}" if day else "",
            "posted_kind": ("등록" if day.group(1) == "등록일" else "수정") if day else "",
        })
    return out


# ---------------- 잡코리아 ----------------
def jobkorea(word):
    q = urllib.parse.quote(word)
    s = get(f"https://www.jobkorea.co.kr/Search/?stext={q}&tabType=recruit&Page_No=1")
    out, seen = [], set()
    for c in s.split('data-sentry-component="CardJob"')[1:]:
        m = re.search(r"GI_Read/(\d+)", c)
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        t = [html.unescape(x).strip() for x in re.findall(r">([^<>]+)<", c)]
        t = [x for x in t if x and x not in ("스크랩", "즉시 지원", "AD", "홈페이지 지원")]
        if len(t) < 3:
            continue
        loc_i = next((i for i, x in enumerate(t) if re.match(r"^(서울|경기|대전|인천|부산|대구|광주|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주|전국)", x)), None)
        exp = next((x for x in t if re.search(r"경력|신입", x)), "")
        out.append({
            "site": "잡코리아", "id": f"j{m.group(1)}", "title": t[0],
            "company": t[loc_i - 1] if loc_i and loc_i >= 2 else (t[1] if len(t) > 1 else ""),
            "location": t[loc_i] if loc_i is not None else "",
            "sector": t[loc_i + 1] if loc_i is not None and loc_i + 1 < len(t) else "",
            "experience": exp, "deadline": next((x for x in t if re.search(r"~|마감|상시", x)), ""),
            "url": f"https://www.jobkorea.co.kr/Recruit/GI_Read/{m.group(1)}", "query": word,
        })
    return out


# ---------------- 임팩트커리어 (impact.career, 소셜섹터) ----------------
def impactcareer():
    """디자인 직무(28) · 서울/경기·인천/대전·세종·충청 채용 공고.

    목록에 마감된 공고가 섞여 나오므로, 마감일이 지난 공고는 빼고,
    '성사시 마감'·'상시오픈' 공고는 마감일이 180일 넘게 지난 공고가 처음 나오기 전까지만 남긴다(목록은 최신순).
    """
    base = ("https://impact.career/impactcareer/grantors/careers?career%5Btype%5D=recruitment"
            "&q%5Bjob_function_ids%5D%5B%5D=28")
    for a in ("서울", "경기/인천", "대전/세종/충청"):
        base += "&q%5Bcustom_areas%5D%5B%5D=" + urllib.parse.quote(a)
    today = date.today()
    out, seen, stale = [], set(), False
    for page in (1, 2):
        s = get(f"{base}&page={page}")
        for m in re.finditer(r'href="/impactcareer/grantors/careers/([A-Za-z0-9]{6})"', s):
            cid = m.group(1)
            if cid in seen:
                continue
            seen.add(cid)
            t = [html.unescape(x).strip() for x in re.findall(r">([^<>]+)<", s[m.start():m.start() + 3000])]
            t = [x for x in t if x]
            if len(t) < 5:
                continue
            title, company, deadline, exp, loc = t[:5]
            fields = [x for x in t[5:8] if x != t[-1] or len(t) <= 6]
            dm = re.fullmatch(r"(\d{4})\.(\d{2})\.(\d{2})", deadline)
            if dm:
                dl = date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
                if (today - dl).days > 180:
                    stale = True
                if dl < today:
                    continue
                deadline = f"{dl.month}/{dl.day}"
            elif stale:
                continue
            else:
                deadline = f"{deadline} (마감 여부 확인)"
            out.append({
                "site": "임팩트커리어", "id": f"i{cid}", "title": title, "company": company,
                "location": loc, "experience": exp, "deadline": deadline,
                "sector": "소셜섹터 사회적 가치 · " + ", ".join(fields),
                "url": f"https://impact.career/impactcareer/grantors/careers/{cid}", "query": "디자인",
                "group_hint": "B",
            })
        if stale:
            break
        time.sleep(0.7)
    return out


def fill_posted_dates(rows, errors):
    """공고가 올라온 날을 채운다. 원티드·잡코리아는 상세 페이지에서 한 번만 가져와 data/posted.json에 저장한다.

    posted_kind: 등록(사이트의 게시일) / 수정(사람인이 등록일 대신 수정일만 보여줄 때) / 확인(날짜가 없어 우리가 처음 본 날)
    """
    cache_path = DATA / "posted.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    fails = 0
    wanted_detail_fail = 0
    for r in rows:
        if r.get("posted"):
            continue
        if r["id"] in cache:
            r["posted"], r["posted_kind"] = cache[r["id"]]
            continue
        found = ""
        if r["site"] == "원티드" and wanted_detail_fail >= 3:  # 상세 페이지가 막히면 나머지는 건너뛴다
            r["posted"], r["posted_kind"] = r["first_seen"], "확인"
            continue
        try:
            if r["site"] == "원티드":
                m = re.search(r'"confirm_time":"(\d{4}-\d{2}-\d{2})', get(r["url"]))
                found = m.group(1) if m else ""
            elif r["site"] == "잡코리아":
                m = re.search(r'datePosted\\?"\s*:\s*\\?"(\d{4}-\d{2}-\d{2})', get(r["url"]))
                found = m.group(1) if m else ""
            time.sleep(0.25)
        except Exception:  # noqa: BLE001
            fails += 1
            if r["site"] == "원티드":
                wanted_detail_fail += 1
        if found:
            r["posted"], r["posted_kind"] = found, "등록"
            cache[r["id"]] = [found, "등록"]
        else:
            r["posted"], r["posted_kind"] = r["first_seen"], "확인"
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0))
    if fails:
        errors.append(f"공고 날짜 {fails}건을 가져오지 못해 처음 확인한 날로 표시했어요.")


def main():
    all_rows, errors = [], []
    for name, fn in (("원티드", wanted), ("임팩트커리어", impactcareer)):
        try:
            all_rows += fn()
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    for group, words in KEYWORDS.items():
        for w in words:
            for name, fn in (("사람인", saramin), ("잡코리아", jobkorea)):
                try:
                    rows = fn(w)
                    for r in rows:
                        r["group_hint"] = group
                    all_rows += rows
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{name}({w}): {e}")
                time.sleep(0.7)

    # 1차 필터
    uniq = {}
    for r in all_rows:
        if r["id"] in uniq:
            continue
        hay = f"{r['title']} {r.get('sector','')}"
        if not TITLE_HINT.search(hay) or EXCLUDE.search(r["title"]):
            continue
        if not region_ok(r.get("location", "")):
            continue
        ok = r.pop("_exp_ok", None)
        if ok is False or (ok is None and not exp_ok(r.get("experience", ""))):
            continue
        tg = tags_for(r["title"], r.get("sector", ""))
        r["tags_A"], r["tags_B"] = tg["A"], tg["B"]
        if not (tg["A"] or tg["B"]):
            continue
        uniq[r["id"]] = r

    seen_path = DATA / "seen.json"
    seen = json.loads(seen_path.read_text()) if seen_path.exists() else {}
    today = date.today().isoformat()
    for r in uniq.values():
        r["first_seen"] = seen.get(r["id"], today)
        r["is_new"] = r["first_seen"] == today
        seen.setdefault(r["id"], today)
    seen_path.write_text(json.dumps(seen, ensure_ascii=False, indent=0))

    fill_posted_dates(uniq.values(), errors)

    res = {"date": today, "count": len(uniq), "errors": errors, "jobs": list(uniq.values())}
    (DATA / "today.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    by = {}
    for r in uniq.values():
        by[r["site"]] = by.get(r["site"], 0) + 1
    print("원티드 접속 기록:", WANTED_LOG[:4])
    print(json.dumps({"date": today, "total": len(uniq), "by_site": by,
                      "new": sum(r["is_new"] for r in uniq.values()), "errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
