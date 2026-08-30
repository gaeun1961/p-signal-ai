"""
FR-02 테스트 결과 요약본 — 발표/캡처용. 매칭 상세 내역 없이 PASS/FAIL 한 줄씩만 출력해서
터미널 한 화면에 다 들어오게 함.

  python print_fr02_summary.py

test_fr02_disclosure.py 와 같은 폴더에 두고 실행.
"""

import glob
import os
import sys

from fr02_disclosure import classify_disclosure
from test_fr02_disclosure import TEST_CASES, SAMPLE_EXPECT

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

print("=== 합성 케이스 (6) ===")
for c in TEST_CASES:
    r = classify_disclosure(c["text"])
    ok = r["disclosed"] == c["expect"]
    print(f"[{'PASS' if ok else 'FAIL'}] {c['name']}")

print("\n=== blog_samples 실제 샘플 회귀 (10) ===")
total_ok = True
for path in sorted(glob.glob("blog_samples/*.txt")):
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    r = classify_disclosure(text)
    expect = SAMPLE_EXPECT.get(name, False)
    ok = r["disclosed"] == expect
    total_ok &= ok
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: disclosed={r['disclosed']}")

print("\n총 16/16 통과" if total_ok else "\n일부 실패 — 위 로그 확인")