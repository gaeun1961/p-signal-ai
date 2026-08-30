"""
FR-02 표기 판별 회귀 테스트.

  python test_fr02_disclosure.py

- TEST_CASES: 프로토타입에서 옮겨온 합성 케이스 6개 (assert)
- blog_samples/: 실제 네이버 블로그 10건 회귀 (라벨은 육안 확인해 아래에 고정)
    1.txt  -> False  "쿠팡 파트너스 활동이 아닌" 부정문 (오탐 방지 핵심 케이스)
    3.txt  -> True   "쇼핑 커넥트 상품이 포함 ... 수수료를 받습니다"
    9.txt  -> True   "네이버 쇼핑파트너스 활동의 일환 ... 수수료가 발생"
    나머지 -> False  표기 문구 없음
"""

import glob
import os
import sys

from fr02_disclosure import classify_disclosure, find_disclosure_matches

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TEST_CASES = [
    {
        "name": "부정문 → 표기 아님으로 판정돼야 함 (오탐 방지 핵심)",
        "text": "(쿠팡 파트너스 활동이 아닌, 순수 제 돈으로 직접 구매한 100% 내돈내산 추천 리뷰입니다!)",
        "expect": False,
    },
    {
        "name": "제휴 마케팅 사전 표기 → 쿠팡 파트너스",
        "text": "이 포스팅은 쿠팡파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.",
        "expect": True,
    },
    {
        "name": "제휴 마케팅 사전 표기 → 네이버 쇼핑 커넥트",
        "text": "이 글의 상품 링크는 네이버 쇼핑 커넥트를 통해 연결되며, 구매 시 수수료를 받을 수 있습니다.",
        "expect": True,
    },
    {
        "name": "협찬형 표기 (기존 FR-02 케이스, 회귀 확인용)",
        "text": "이 글은 업체로부터 제품을 제공받아 작성되었습니다.",
        "expect": True,
    },
    {
        "name": "표기 없음 → 무관한 글",
        "text": "오늘은 날씨가 좋아서 산책을 다녀왔다. 카페에서 커피도 한 잔 마셨다.",
        "expect": False,
    },
    {
        "name": "부정어가 다른 문장에 있는 경우 → 오탐(negated) 안 되는지",
        "text": "어제는 비가 오지 않았다. 오늘 쓴 이 글은 쿠팡파트너스 활동의 일환으로 수수료를 제공받고 작성한 글입니다.",
        "expect": True,
    },
]


def run_synthetic():
    fails = 0
    for c in TEST_CASES:
        r = classify_disclosure(c["text"])
        ok = r["disclosed"] == c["expect"]
        fails += not ok
        print(f"[{'PASS' if ok else 'FAIL'}] {c['name']}  (disclosed={r['disclosed']}, 기대={c['expect']})")
        for m in r["valid_matches"]:
            print(f"        매칭 \"{m['matched_text']}\" [{m['category']}]  ...{m['context']}...")
        for m in r["negated_matches"]:
            print(f"        (부정문 제외) \"{m['matched_text']}\"  문장: {m['sentence']}")
    assert fails == 0, f"{fails}건 실패"


SAMPLE_EXPECT = {"1.txt": False, "3.txt": True, "9.txt": True}


def run_samples():
    fails = 0
    for path in sorted(glob.glob("blog_samples/*.txt")):
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        r = classify_disclosure(text)
        expect = SAMPLE_EXPECT.get(name, False)
        ok = r["disclosed"] == expect
        fails += not ok
        cats = ",".join(r.get("categories", [])) or r.get("reason", "")
        print(f"[{'PASS' if ok else 'FAIL'}] {name}  disclosed={r['disclosed']} ({cats})  기대={expect}")
        for m in r["valid_matches"]:
            print(f"        + \"{m['matched_text']}\" [{m['category']}]  문장: {m['sentence'][:80]}")
        for m in r["negated_matches"]:
            print(f"        - (부정문) \"{m['matched_text']}\"  문장: {m['sentence'][:80]}")
    assert fails == 0, f"{fails}건 실패"


if __name__ == "__main__":
    print("=== 합성 케이스 ===")
    run_synthetic()
    print("\n=== blog_samples 회귀 ===")
    run_samples()
    print("\n모두 통과")
