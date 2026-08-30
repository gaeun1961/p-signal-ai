"""
FR-02 표기 판별 — 공정위 협찬 표기 + 제휴 마케팅형 표기를 정규식으로 확정 판별.

두 카테고리:
  - sponsorship : 협찬형("원고료/제품을 제공받아 작성", "협찬받아", "광고비를 받고")
  - affiliate   : 제휴 마케팅형("쿠팡 파트너스 활동", "쇼핑 커넥트", "구매 시 수수료 발생")

8/24 회의 결정(3,4번): 기존 협찬형 정규식만으로는 제휴형 문구를 놓치므로 affiliate 패턴을
추가하고, 부정문("~파트너스 활동이 아닌...")에서 키워드만 보고 오탐하지 않도록
문장 단위로 부정어를 확인한다. 부정어가 매칭 키워드 "뒤"에 오는 한국어 어순 때문에
raw N-char window가 아니라 문장 경계로 잘라서 판단한다.

공개 API:
  classify_disclosure(text) -> dict   본문 전체 최종 판정
  find_disclosure_matches(text) -> list[dict]   매칭별 상세(FR-04 evidence 구조와 호환)
  split_sentences(text) -> list[(sentence, offset)]   R1 마스킹에서 재사용
"""

import re

# ── 1. 제휴 마케팅형 표기 패턴 ────────────────────────────────────────────
AFFILIATE_PATTERNS = [
    r"쿠팡\s*파트너스",
    r"쿠팡파트너스",
    r"네이버\s*쇼핑\s*커넥트",
    r"쇼핑\s*커넥트",
    r"쇼핑\s*파트너스",
    r"제휴\s*마케팅",
    r"어필리에이트",
    r"판매\s*수수료",
    r"수수료를?\s*(제공|지급)\s*받",
    r"수수료를?\s*받(는|습니다|아|을|게)",
    r"수수료가?\s*발생",
    r"구매\s*시\s*(일정액?|소정의?)?\s*(의\s*)?수수료",
]

# ── 2. 협찬형 표기 패턴 ──────────────────────────────────────────────────
SPONSORSHIP_PATTERNS = [
    r"소정의?\s*원고료를?\s*(지급|제공)\s*받",
    r"업체로부터\s*(제품|서비스)?\s*(을|를)?\s*(지원|제공)\s*받",
    r"(제품|서비스|원고료)\s*(을|를)?\s*(제공|지원)\s*받(아|고|았)",
    r"협찬을?\s*받",
    r"협찬\s*(제품|받아|받고)",
    r"광고비를?\s*받",
    r"광고\s*원고료",
    r"소정의?\s*(수수료|대가|금액)를?\s*(지급|제공)\s*받",
]

ALL_PATTERNS = [(p, "affiliate") for p in AFFILIATE_PATTERNS] + \
               [(p, "sponsorship") for p in SPONSORSHIP_PATTERNS]

# ── 3. 부정어 패턴 ──────────────────────────────────────────────────────
# 매칭 키워드가 속한 문장에 이게 있으면 "표기"가 아니라 "부정문"으로 본다.
# ponytail: 문장 내 부정어 존재 여부만 본다(위치·수식 관계 무시). 실제 표기를
#   부정문으로 오판할 수 있으나, 라벨링을 안전하게 "미표기"로 기울이는 게 팀 결정이라
#   허용 오차. 정밀도가 문제되면 의존구문 분석으로 업그레이드.
NEGATION_PATTERNS = [
    r"아닙?니(다|까)",
    r"아니(라|며|고|어|에)",
    r"아닌",
    r"않(다|은|았|고|습니다)",
    r"없(다|이|는|었|습니다|어요|음)",
    r"(은|는)\s*아",
    r"절대\s*아",
    r"광고\s*아님",
    r"내돈내산",
    r"제외",
]


def split_sentences(text: str):
    """
    문장 단위로 쪼개서 (문장, 문장의 원문 내 시작 offset) 리스트를 반환.
    경계 = 문장부호(.!?。) 또는 빈 줄(문단 구분). 이어붙이면 원문 그대로 복원된다.

    ponytail: 네이버 블로그 본문은 한 줄 = 한 문장인 경우가 많아 빈 줄 분리로 충분.
      단일 개행 중간에 문장이 끊긴 경우는 잡지 못하지만, byline 같은 노이즈는
      r1_masking.strip_byline으로 먼저 걷어내는 걸 전제로 한다.
    """
    sentences = []
    start = 0
    for m in re.finditer(r"[.!?。]+[\s​]*|\n[\s​]*\n", text):
        end = m.end()
        sentences.append((text[start:end], start))
        start = end
    if start < len(text):
        sentences.append((text[start:], start))
    return sentences


def _sentence_at(text: str, pos: int):
    """pos(문자 위치)가 속한 문장 전체를 반환. 못 찾으면 안전하게 전체 텍스트."""
    for sentence, offset in split_sentences(text):
        if offset <= pos < offset + len(sentence):
            return sentence
    return text


def find_disclosure_matches(text: str):
    """
    본문에서 협찬/제휴 표기 후보를 찾고, 각 매칭에 대해 부정문 여부를 함께 판단해 반환.

    반환: [{"pattern": str, "matched_text": str, "span": (start, end),
            "category": "affiliate" | "sponsorship", "negated": bool,
            "sentence": str, "context": str}]
    """
    results = []
    for pattern, category in ALL_PATTERNS:
        for m in re.finditer(pattern, text):
            start, end = m.span()
            sentence = _sentence_at(text, start)
            negated = any(re.search(neg, sentence) for neg in NEGATION_PATTERNS)
            results.append({
                "pattern": pattern,
                "matched_text": m.group(),
                "span": (start, end),
                "category": category,
                "negated": negated,
                "sentence": sentence.strip(),
                "context": text[max(0, start - 20):min(len(text), end + 20)],
            })
    return results


def classify_disclosure(text: str):
    """
    본문 전체 최종 판정: 부정문을 제외하고 유효한 표기가 하나라도 있으면 disclosed=True.

    반환:
      {"disclosed": True,  "categories": ["affiliate"|"sponsorship", ...],
       "valid_matches": [...], "negated_matches": [...]}
      {"disclosed": False, "reason": "no_match"|"all_matches_negated",
       "valid_matches": [], "negated_matches": [...]}
    """
    matches = find_disclosure_matches(text)
    valid = [m for m in matches if not m["negated"]]
    negated = [m for m in matches if m["negated"]]

    if not valid:
        return {
            "disclosed": False,
            "reason": "no_match" if not matches else "all_matches_negated",
            "valid_matches": [],
            "negated_matches": negated,
        }

    return {
        "disclosed": True,
        "categories": sorted({m["category"] for m in valid}),
        "valid_matches": valid,
        "negated_matches": negated,
    }
