"""
FR-04 프롬프트 v1 파일럿 실행기

- ./blog_samples 폴더 안의 .txt 파일들(블로그 본문)을 읽어서
- Signal 청사진 FR-04 프롬프트로 Gemini에 질의하고
- JSON 파싱 성공 여부 + evidence의 quote가 원문에 실제로 존재하는지를 검사해 리포트로 출력한다.

8/24 회의 브리핑용 "실제 테스트 결과"를 만들기 위한 스크립트.

사용법:
  1) pip install google-genai python-dotenv --break-system-packages
  2) 이 파일과 같은 폴더에 .env 파일을 만들고 안에 GEMINI_API_KEY=본인키 한 줄 작성
     (.gitignore에 .env가 이미 등록돼 있어서 git에는 안 올라감)
  3) ./blog_samples/ 폴더를 만들고 블로그 본문 .txt 파일들을 넣기 (골든셋 10건 정도, 파일명 자유)
  4) python fr04_pilot_runner.py
  5) 실행 후 ./fr04_pilot_results/ 안에 파일별 JSON 결과 + _report.json(요약)이 저장됨
"""

import os
import re
import sys
import json
import glob
from dotenv import load_dotenv
from google import genai

# Windows 콘솔(cp949)에서 한글/특수문자 출력 시 깨지거나 죽는 것 방지
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

load_dotenv()  # 같은 폴더의 .env 파일을 읽어서 os.environ에 채워줌

# 콘솔(Google AI Studio)에서 실제로 쓸 수 있는 모델명으로 바꿔도 됨. 필요하면 환경변수로 덮어쓰기 가능.
MODEL_NAME = os.environ.get("SIGNAL_MODEL", "gemini-flash-lite-latest")
# temperature=0만으로는 Gemini가 결정적으로 동작하지 않는다(재현성 테스트로 확인됨).
# seed를 같이 고정해야 동일 입력 -> 동일 출력이 보장된다.
SEED = int(os.environ.get("SIGNAL_SEED", "42"))
SAMPLE_DIR = "./blog_samples"
OUTPUT_DIR = "./fr04_pilot_results"

SYSTEM_PROMPT = """당신은 블로그 글에서 정해진 4가지 사실 여부만 추출하는 추출기입니다.
이 글이 광고인지 아닌지, 좋은 글인지 나쁜 글인지 판단하지 마세요.
아래 4개 질문에 대해서만 답하고, 근거가 되는 문장은 본문에서 "그대로" 인용하세요(요약·의역 금지 — 원문과 한 글자도 다르면 안 됨).
반드시 JSON만 출력하세요. 설명, 마크다운 코드블록, 여는 말 없이 JSON 객체 하나만 출력합니다."""

USER_PROMPT_TEMPLATE = """다음은 네이버 블로그 글 본문입니다. 문단은 빈 줄로 구분되어 있고, 각 문단에는 번호가 붙어 있습니다.

---
{body}
---

아래 4개 항목을 순서대로 판단하세요.

1. has_drawback — 이 제품·서비스의 단점이나 한계를 언급한 문장이 있습니까?
2. has_not_for — "~한 분에게는 비추천" 류의 제약·비추천 대상을 언급한 문장이 있습니까?
3. measured_facts — 본문 내용 중 제품·서비스에 대한 가격·기간·수치·모델명이 몇 개 등장합니까?
   - 작성자명, 작성일시(예: "2026.8.12.12:30"), 조회수, 공감수 등 게시글 메타데이터(byline)는 절대 포함하지 마세요. 이건 제품에 대한 사실이 아닙니다.
   - 같은 사실이 본문에서 여러 번 반복 언급되어도 서로 다른 사실 단위로 1회씩만 세세요 (예: "3만원"이 3번 나와도 1개로 카운트, "3만원"과 "2주"는 서로 다른 사실이므로 각각 세어 총 2개). 같은 스펙이 본문·스펙표·비교표 등 여러 위치에 반복 등장해도 동일한 사실이면 1개로만 세세요.
   - 표(스펙표·비교표) 형식이나 FAQ처럼 목록으로 정리된 부분에 있는 수치도 빠뜨리지 말고 포함하세요.
   - 리스트 항목이나 소제목 앞에 붙는 순번(예: "1.", "2.", "Q1.", "Q2.")은 수치가 아니므로 절대 포함하지 마세요. 그 항목의 실제 "내용"에 가격·기간·수치·모델명이 있을 때만 세세요.
   - 본문 안에 링크로 삽입된 다른 게시물의 제목이나 설명(예: "[다른 글 제목] 관련 글 보기" 같은 삽입 링크)은 지금 리뷰 중인 제품에 대한 내용이 아니므로 제외하세요. 지금 다루는 제품·서비스에 대한 사실만 세세요.
   - 제품의 작동 방식·카테고리·종류를 설명하는 단어(예: "초음파식", "무선형", "유선", "터치식")는 가격·기간·수치·모델명이 아니므로 절대 포함하지 마세요. "50mL", "3만원대", "1000ml", "SPF50+" 처럼 실제 숫자·단위가 들어간 값만 세세요.
   (정수로 개수만 세기, 예: "3만원", "2주", "128GB", "A100 모델" → 각각 1개씩. 단, 위 규칙에 따라 메타데이터·순번·다른 게시물 링크·방식/카테고리 설명은 제외하고, 반복 언급은 중복 카운트하지 않음)
4. has_comparison — 타사 제품이나 이전 제품과 직접 비교한 서술이 있습니까?

각 항목마다:
- value: true/false (measured_facts는 count: 정수)
- evidence: 근거가 된 문장을 원문 그대로 인용 (quote), 그 문장이 속한 문단 번호 (para_hint). 근거가 없으면 빈 배열 []

다음 JSON 형식으로만 출력하세요:

{{
  "has_drawback": {{ "value": bool, "evidence": [ {{ "quote": "원문 문장", "para_hint": N }} ] }},
  "has_not_for": {{ "value": bool, "evidence": [ {{ "quote": "원문 문장", "para_hint": N }} ] }},
  "measured_facts": {{ "count": N, "evidence": [ {{ "quote": "원문 문장", "para_hint": N }} ] }},
  "has_comparison": {{ "value": bool, "evidence": [ {{ "quote": "원문 문장", "para_hint": N }} ] }}
}}"""


def to_paragraphs(text):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    return "\n\n".join(f"[문단 {i + 1}] {p}" for i, p in enumerate(paras))


def extract_json(raw_text):
    # 코드블록으로 감싸져 오는 경우 대비
    cleaned = re.sub(r"^```json\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)


def check_quotes(result, original_text):
    """evidence의 quote가 원문에 실제로 존재하는지 검사 (R2 대응 방식과 동일한 매칭 아이디어)"""
    mismatches = []
    for key in ["has_drawback", "has_not_for", "measured_facts", "has_comparison"]:
        for ev in result.get(key, {}).get("evidence", []):
            quote = ev.get("quote", "")
            if quote and quote not in original_text:
                mismatches.append((key, quote))
    return mismatches


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY 환경변수를 먼저 설정하세요. (예: export GEMINI_API_KEY=...)")

    client = genai.Client(api_key=api_key)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    files = sorted(glob.glob(os.path.join(SAMPLE_DIR, "*.txt")))
    if not files:
        raise SystemExit(f"{SAMPLE_DIR} 폴더에 .txt 파일이 없습니다. 블로그 본문을 넣어주세요.")

    report = []
    for path in files:
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            body = f.read()

        user_prompt = USER_PROMPT_TEMPLATE.format(body=to_paragraphs(body))

        try:
            resp = client.models.generate_content(
                model=MODEL_NAME,
                contents=[SYSTEM_PROMPT + "\n\n" + user_prompt],
                config=genai.types.GenerateContentConfig(temperature=0, seed=SEED),
            )
            raw = resp.text
        except Exception as e:
            print(f"[API 에러] {name}: {e}")
            report.append({"file": name, "status": "api_error", "error": str(e)})
            continue

        try:
            result = extract_json(raw)
        except Exception as e:
            print(f"[파싱 실패] {name}: {e}")
            report.append({"file": name, "status": "parse_error", "error": str(e), "raw": raw})
            continue

        mismatches = check_quotes(result, body)
        if mismatches:
            print(f"[quote 불일치] {name}: {len(mismatches)}건")
        else:
            print(f"[정상] {name}")

        with open(os.path.join(OUTPUT_DIR, name.replace(".txt", ".json")), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        report.append({
            "file": name,
            "status": "ok" if not mismatches else "quote_mismatch",
            "quote_mismatches": mismatches,
        })

    total = len(report)
    ok = sum(1 for r in report if r["status"] == "ok")
    parse_err = sum(1 for r in report if r["status"] == "parse_error")
    api_err = sum(1 for r in report if r["status"] == "api_error")
    quote_mismatch = sum(1 for r in report if r["status"] == "quote_mismatch")

    print(f"\n===== FR-04 파일럿 결과 요약 ({total}건) =====")
    print(f"정상(quote 일치): {ok}")
    print(f"JSON 파싱 실패: {parse_err}")
    print(f"API 에러: {api_err}")
    print(f"quote 원문 불일치: {quote_mismatch}")
    if total:
        print(f"파싱 성공률: {(total - parse_err - api_err) / total * 100:.1f}%")

    with open(os.path.join(OUTPUT_DIR, "_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n상세 결과는 {OUTPUT_DIR}/ 안에 저장됨 (_report.json 포함) — 이걸 8/24 브리핑 자료로 쓰면 됨")


if __name__ == "__main__":
    main()