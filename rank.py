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
    (r"콘텐츠\s*디자이너|컨텐츠\s*디자이너", 2, "A"), (r"마케팅\s*디자이너|프로모션", 1, "A"),
    (r"인포그래픽", 5, "B"), (r"정보\s*디자인|쉬운\s*정보|접근성", 5, "B"),
    (r"편집\s*디자이너|편집디자인|출판|북\s*디자인", 3, "B"),
    (r"교육|에듀|아동|어린이|청소년", 2, "B"),
    (r"공공|재단|협회|사회적|비영리|NGO|복지|장애", 3, "B"),
]
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
    for pat, pts, d in STRONG:
        if re.search(pat, r["title"], re.I):
            s += pts
            dirs.add(d)
        elif re.search(pat, r.get("sector", ""), re.I):
            s += pts // 2
            dirs.add(d)
    if re.search(CONTEXT_PLUS, t, re.I):
        s += 1
    for pat, pts in MINUS:
        if re.search(pat, r["title"], re.I):
            s += pts
    if r.get("site") == "임팩트커리어":  # 소셜섹터 전문 사이트라 방향 B에 가산
        s += 3
        dirs.add("B")
    exp = r.get("experience", "").replace(" ", "")
    m = re.search(r"(\d+)~(\d+)년", exp)
    if m and int(m.group(1)) in (2, 3, 4, 5):
        s += 1
    return s, "".join(sorted(dirs)) or "A"


def main():
    d = json.loads((DATA / "today.json").read_text())
    for r in d["jobs"]:
        r["score"], r["direction"] = score(r)
    d["jobs"].sort(key=lambda r: (-r["score"], not r["is_new"]))
    (DATA / "ranked.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
    for i, r in enumerate(d["jobs"][:90]):
        print(i, r["score"], r["direction"], r["site"][:2], "|", r["id"], "|", r["company"][:16], "|",
              r["title"][:50], "|", r["location"][:9], "|", r["experience"][:10], "|", r.get("sector", "")[:40])


if __name__ == "__main__":
    main()
