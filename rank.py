"""data/today.json의 공고에 적합도 점수를 매겨 data/ranked.json으로 저장한다.

점수는 1차 정렬용이다. 최종 추천 이유는 매일 실행하는 Claude가 상위 공고를 읽고 쓴다.
"""
import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

STRONG = [  # (패턴, 점수, 방향)
    (r"캐릭터", 4, "A"), (r"일러스트", 4, "A"), (r"이모티콘", 4, "A"), (r"\bBX\b|BX", 4, "A"),
    (r"브랜드\s*디자이너|브랜드\s*디자인|브랜딩", 3, "A"), (r"그래픽", 3, "A"), (r"아이콘", 3, "A"),
    (r"비주얼\s*디자이너|비주얼\s*디자인|시각\s*디자이너|시각\s*디자인", 3, "A"),
    (r"콘텐츠\s*디자이너|컨텐츠\s*디자이너", 2, "A"), (r"마케팅\s*디자이너|프로모션", 1, "A"),
    (r"인포그래픽", 5, "B"), (r"정보\s*디자인|쉬운\s*정보|접근성", 5, "B"),
    (r"편집\s*디자이너|편집디자인|출판|북\s*디자인", 3, "B"),
    (r"교육|에듀|아동|어린이|청소년", 2, "B"),
    (r"공공|재단|협회|사회적|비영리|NGO|복지|장애", 3, "B"),
    (r"식물|정원|가드닝|가든|원예|화훼|꽃|수목원|식물원|보태니컬|조경", 5, "C"),
]
# 제목에 디자인 일이라는 단서가 하나도 없으면 크게 깎는다 (예: '출판 개발', '교재 기획')
DESIGN_WORD = r"디자인|디자이너|일러스트|그래픽|BX|BI|브랜딩|캐릭터|이모티콘|아트워크|인포그래픽|비주얼|Designer|Design|Illustrat"
PLANT_COMPANY = r"꾸까|kukka|수목원|식물원|수목정원|가든|garden|원예|화훼|농원|보태니컬|botanic"
CONTEXT_PLUS = r"앱|App|플랫폼|IT|서비스|스타트업|테크|커플|라이프"
MINUS = [
    (r"마케터|크리에이터|PD\b|에디터", -4), (r"아티스트|원화|컨셉\s*아트|3D|모델러", -3),
    (r"리더|팀장|Lead|헤드|Head|디렉터|Director|파트장|실장", -4),
    (r"촬영|영상|모션그래픽|포토", -2), (r"퍼포먼스|광고\s*소재|상세페이지|쇼핑몰|웹\s*디자이너|웹디자이너", -2),
    (r"신입", -1), (r"인턴", -3), (r"프로덕트\s*디자이너|Product Designer|UX", -1),
    (r"패키지|VMD|공간|전시", -1),
]


def score(r):
    t = f"{r['title']} {r.get('sector','')}"
    s, dirs = 0, set()
    weight = {"A": 0, "B": 0, "C": 0}  # 방향별 근거 점수 (제목은 2배로 친다) → 대표 방향을 고른다
    for pat, pts, d in STRONG:
        if re.search(pat, r["title"], re.I):
            s += pts
            dirs.add(d)
            weight[d] += pts * 2
        elif re.search(pat, r.get("sector", ""), re.I):
            s += pts // 2
            dirs.add(d)
            weight[d] += pts // 2
    if re.search(CONTEXT_PLUS, t, re.I):
        s += 1
    for pat, pts in MINUS:
        if re.search(pat, r["title"], re.I):
            s += pts
    if r.get("site") == "잡알리오":  # 공공기관: 제목이 '제3차 직원 채용'처럼 뭉뚱그려져 있어 제목 감점 대신 가산
        s += 3 + (2 if re.search(DESIGN_WORD, r["title"], re.I) else 0)
        dirs.add("B")
        weight["B"] += 3
    elif not re.search(DESIGN_WORD, r["title"], re.I):
        s -= 4
    if "C" not in dirs and re.search(PLANT_COMPANY, r.get("company", ""), re.I):  # 회사가 식물 관련
        s += 4
        dirs.add("C")
    if r.get("site") == "임팩트커리어":  # 소셜섹터 전문 사이트라 방향 B에 가산
        s += 3
        dirs.add("B")
        weight["B"] += 3
    exp = r.get("experience", "").replace(" ", "")
    m = re.search(r"(\d+)~(\d+)년", exp)
    if m and int(m.group(1)) in (2, 3, 4, 5):
        s += 1
    # 대표 방향: 식물 단서가 있으면 C, 아니면 근거 점수가 큰 쪽 (같으면 B, 정보·편집 쪽이 더 드물어서)
    if "C" in dirs:
        main = "C"
    elif dirs:
        main = max(sorted(dirs, reverse=True), key=lambda d: weight[d])
    else:
        main = "A"
    return s, "".join(sorted(dirs)) or "A", main


def _norm(t):
    t = re.sub(r"\[[^\]]*\]|\([^)]*(주|株)[^)]*\)|㈜", "", t)
    t = re.sub(r"채용|모집|담당자|구인|정규직|계약직|경력직?|신입|급구|\d+명", "", t)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", t).lower()


def dedupe(jobs):
    """같은 자리를 여러 회사·사이트가 올린 공고를 하나로 합친다 (점수가 높은 쪽만 남김).

    제목이 짧고 흔하면('그래픽디자이너') 다른 회사 공고일 수 있으니, 그때는 회사 이름도 같아야 합친다.
    """
    keep, seen = [], set()
    for r in jobs:
        t = _norm(r["title"])
        c = _norm(r.get("company", ""))
        key = ("t", t) if len(t) >= 12 else ("tc", t, c)
        if key in seen:
            continue
        seen.add(key)
        keep.append(r)
    return keep


def main():
    d = json.loads((DATA / "today.json").read_text())
    for r in d["jobs"]:
        r["score"], r["direction"], r["main"] = score(r)
    d["jobs"].sort(key=lambda r: (-r["score"], not r["is_new"]))
    before = len(d["jobs"])
    d["jobs"] = dedupe(d["jobs"])
    d["merged"] = before - len(d["jobs"])
    (DATA / "ranked.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
    for i, r in enumerate(d["jobs"][:90]):
        print(i, r["score"], r["direction"], r["site"][:2], "|", r["id"], "|", r["company"][:16], "|",
              r["title"][:50], "|", r["location"][:9], "|", r["experience"][:10], "|", r.get("sector", "")[:40])


if __name__ == "__main__":
    main()
