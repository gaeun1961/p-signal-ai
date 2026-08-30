"""
R1 마스킹 육안 검증 + 회귀.

  python test_r1_masking.py

- strip_byline 이 byline의 날짜 오염을 실제로 없애는지 (assert)
- 마스킹 후 표기 문구가 남아있지 않은지 (assert, context=1/2 모두)
- 표기 문장 주변이 과/소하게 잘리지 않는지 (before/after 육안 출력)
"""

import sys

from fr02_disclosure import find_disclosure_matches, split_sentences
from r1_masking import mask_disclosure, strip_byline

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SAMPLES = ["1.txt", "3.txt", "9.txt"]
LEAK_TOKENS = ["쿠팡 파트너스", "쿠팡파트너스", "쇼핑 커넥트", "쇼핑파트너스",
               "제휴 마케팅", "수수료를 제공받", "수수료를 받", "수수료가 발생"]


def test_byline_removes_date_pollution():
    raw = open("blog_samples/9.txt", encoding="utf-8").read()
    # raw 에서는 byline 날짜가 문장 조각을 만든다
    raw_sents = split_sentences(raw)
    assert any(s.strip() in {"2026.", "8.", "12."} for s, _ in raw_sents), \
        "전제 확인용: raw 에는 날짜 조각 문장이 있어야 함"
    # strip_byline 후에는 사라져야 함
    clean_sents = split_sentences(strip_byline(raw))
    assert not any(s.strip() in {"2026.", "8.", "12."} for s, _ in clean_sents), \
        "strip_byline 이 byline 날짜 오염을 제거하지 못함"
    print("[PASS] strip_byline 이 byline 날짜 오염 제거")


def test_no_leak_after_masking():
    for name in SAMPLES:
        raw = open(f"blog_samples/{name}", encoding="utf-8").read()
        for ctx in (1, 2):
            masked = mask_disclosure(raw, context=ctx)
            left = [t for t in LEAK_TOKENS if t in masked]
            assert not left, f"{name} (context={ctx}) 누수 토큰 잔존: {left}"
    print("[PASS] 마스킹 후 표기 문구 잔존 없음 (context 1, 2)")


def show_before_after():
    for name in SAMPLES:
        raw = open(f"blog_samples/{name}", encoding="utf-8").read()
        clean = strip_byline(raw)
        sents = split_sentences(clean)
        hit = {
            next((i for i, (s, off) in enumerate(sents)
                  if off <= m["span"][0] < off + len(s)), -1)
            for m in find_disclosure_matches(clean)
        }
        print("\n" + "=" * 72)
        print(f"{name}  — 표기 문장 index: {sorted(hit)} / 총 {len(sents)}문장")
        for ctx in (1, 2):
            removed = mask_disclosure(raw, context=ctx)
            print(f"\n  --- context={ctx}: 삭제된 문장 ---")
            kill = set()
            for i in hit:
                kill |= set(range(max(0, i - ctx), min(len(sents), i + ctx + 1)))
            for j in sorted(kill):
                print(f"    [{j}] {sents[j][0].strip()[:90]!r}")
            print(f"  마스킹 후 길이: {len(clean)} -> {len(removed)}")


if __name__ == "__main__":
    test_byline_removes_date_pollution()
    test_no_leak_after_masking()
    show_before_after()
    print("\n육안 확인: 위 '삭제된 문장'에 표기와 무관한 요약/본문이 섞였는지 보고 context 값 확정")
