"""
R1 마스킹 — KoBERT 학습 데이터에서 협찬/제휴 표기 문장을 삭제.

R1: KoBERT가 문체 대신 표기 문구 자체("쿠팡 파트너스" 등)를 학습해버리는 문제.
대응: 토큰 치환(마스크 토큰이 새 누수 신호가 됨)이 아니라 "문장 삭제"로 결정(8월 회의).

절차:
  1. strip_byline  — 네이버 블로그 크롬(작성자·URL 복사·이웃추가 등)을 먼저 제거.
     byline의 날짜("2026. 8. 7.")가 문장 경계를 오염시켜서 마스킹 범위를 망가뜨리므로
     마스킹 전에 반드시 걷어낸다. (직접 실측 확인 — test_r1_masking.py 참고)
  2. split_sentences(fr02_disclosure) 로 문장 분리.
  3. 표기 패턴이 매칭된 문장 + 앞뒤 context개 문장을 통째로 삭제.
     - 부정문("~파트너스 활동이 아닌")도 삭제한다. 표기 여부(disclosed)가 아니라
       "표기 문구가 텍스트에 있는가"가 R1 누수의 기준이기 때문. → find_disclosure_matches 사용.

  mask_disclosure(text, context=1) -> str

context 기본값: 회의 결정은 앞뒤 2문장이었으나 골든셋 3건 실측 결과 context=2는
표기와 무관한 "📌 3줄 요약", 소제목, 본문 문장까지 삭제(test_r1_masking.py show_before_after).
표기는 대개 독립된 한 줄이라 context=1이면 표기 문장 + 꼬리 조각(")" 등)만 정리되고
누수도 없음(1/2 모두 leak 0). 넓은 마진이 필요하면 호출부에서 context=2로 덮어쓸 것.
"""

import re

from fr02_disclosure import find_disclosure_matches, split_sentences

# ── 네이버 블로그 byline / UI 크롬 라인 ─────────────────────────────────
# ponytail: 네이버 PC 블로그 붙여넣기 결과에 나타나는 고정 문구만 대상. 다른 플랫폼
#   포맷이 들어오면 여기 패턴을 늘려야 함(현재 골든셋은 전부 네이버).
BYLINE_LINE_PATTERNS = [
    r"^\s*프로필\s*$",
    r"^\s*프로파일\s*$",
    r"^\s*URL\s*복사",
    r"이웃추가",
    r"^\s*본문\s*기타\s*기능\s*$",
    r"・\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.",   # "워킹초이 ・ 2026. 8. 7. 10:41"
    r"^\s*(공감|댓글|조회)\s*\d",
    r"^\s*\[출처\]",                          # "[출처] ... |작성자 ..."
]


def strip_byline(text: str) -> str:
    keep = [
        ln for ln in text.splitlines()
        if not any(re.search(p, ln) for p in BYLINE_LINE_PATTERNS)
    ]
    return "\n".join(keep)


def mask_disclosure(text: str, context: int = 1) -> str:
    """
    표기 문장 + 앞뒤 context개 문장을 삭제한 본문을 반환. 표기가 없으면 byline만 정리해 반환.

    context: 표기 문장 앞뒤로 함께 지울 문장 수(기본 1, 근거는 모듈 docstring).
    """
    text = strip_byline(text)
    matches = find_disclosure_matches(text)
    if not matches:
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    sents = split_sentences(text)
    kill = set()
    for m in matches:
        pos = m["span"][0]
        idx = next(
            (i for i, (s, off) in enumerate(sents) if off <= pos < off + len(s)),
            None,
        )
        if idx is None:
            continue
        for j in range(max(0, idx - context), min(len(sents), idx + context + 1)):
            kill.add(j)

    kept = "".join(s for i, (s, _) in enumerate(sents) if i not in kill)
    return re.sub(r"\n{3,}", "\n\n", kept).strip()
