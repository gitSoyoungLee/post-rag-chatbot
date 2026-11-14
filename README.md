# PostGuard

펜팔과 개인 국제우편 사용자를 위한 근거 기반 멀티턴 규정 어시스턴트입니다. 목적지와
물품을 대화로 입력하면 국가별 조건과 금지·제한 규정을 확인하고, 사용자가 요청한
경우에만 이용 가능한 서비스와 EMS 예상 기본요금을 조회합니다.

## 설계 원칙

- LLM은 대화 조건을 추출하고 검색된 자연어 규정을 판정합니다.
- 국가지역별 서비스·중량 조건과 EMS 요금은 구조화 데이터와 코드로 처리합니다.
- 품목별로 ChromaDB를 검색하여 서로 다른 물품의 근거가 섞이지 않게 합니다.
- 검색 결과에서 제한을 찾지 못한 상태를 발송 가능으로 단정하지 않습니다.
- 후속 질문에서는 이전 국가·품목·중량을 유지하고 변경된 조건만 갱신합니다.
- LLM 품목 판정은 `(국가, 서비스, 품목)` 키로 대화 안에서 재사용해, 같은 조건의 판정이
  턴마다 바뀌지 않게 하고 새 품목만 판정합니다.

자세한 구조와 설계 이유는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)를 참고하세요.

## MVP 범위

- 국가, 품목, 실제 중량, 희망 서비스의 멀티턴 상태 관리
- 요청 결과에 따른 실행 계획 수립
- `countries.json` 기반 서비스 조건 조회
- Markdown 조항 단위 청킹과 ChromaDB 벡터 검색
- 품목별 `금지 / 제한 / 제한 근거 없음 / 충돌 / 근거 부족` 판정
- 판정 인용문의 원문 존재 여부 검증
- 요청 시 EMS 비서류 예상 기본요금 계산
- Streamlit 채팅 UI

EMS 요금은 2026년 7월 1일 시행 고시의 비서류 기본요금 기준입니다. 부가수수료와
실제 접수 조건은 반영하지 않으므로 최종 접수 전 우체국 확인이 필요합니다.

## 설치

Python 3.12와 [uv](https://docs.astral.sh/uv/)를 사용합니다.

```bash
uv sync --group dev
```

`.env.example`을 참고해 프로젝트 루트의 `.env`에 GMS 키를 직접 입력합니다. `.env`는
Git에서 제외되므로 커밋되지 않습니다.

```bash
GMS_KEY=...
GMS_BASE_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1
GMS_CHAT_MODEL=gpt-6.1-sol
GMS_EMBEDDING_MODEL=text-embedding-3-small
```

채팅 모델은 GMS의 OpenAI Responses API 경로를 사용합니다. 문서 색인에도 같은 GMS
Base URL을 사용하며, 임베딩 모델 제공 여부는 GMS 계정의 사용 가능 모델에 따라
달라질 수 있습니다.

`gpt-6.1-sol` 요청에는 GMS 호환성을 위해 `temperature`를 전달하지 않습니다.

## 문서 색인

```bash
uv run python scripts/index_documents.py
```

색인은 `chroma_db/`에 저장되며 Git에는 포함되지 않습니다.

## 실행

```bash
uv run streamlit run app.py
```

대표 대화:

```text
미국 펜팔에게 과자와 립밤 1.5kg을 EMS로 보내도 될까?
그럼 일본은?
립밤은 빼고 스티커를 추가해줘.
EMS 예상 기본요금도 알려줘.
```

## 테스트

```bash
uv run pytest -q
```

테스트는 국가 조건 조회, 요청 기반 실행 계획, 멀티턴 상태 변경, 조항 청킹, 판정
인용 검증, EMS 요금표 파싱, 서비스 필터 검색과 멀티턴 판정 캐시(그래프 통합 테스트)를
다룹니다. LLM 호출 없이 실행됩니다.

## 평가

평가는 두 가지입니다. 결과는 `evals/results/`에 실행 조건(시각, 커밋, 모델, 커밋되지 않은
변경 여부)과 함께 저장하고 Git에 커밋합니다. 커밋되지 않은 변경이 있으면 파일명에 `-dirty`가
붙습니다.

### 품목 판정 정확도

`evals/golden_items.json`의 정답 55건으로 검색 → 판정 → 인용 검증 구간을 평가합니다. 측정 방법,
개선 과정과 정답 세트 검토표는 [docs/EVALUATION.md](docs/EVALUATION.md)에 있습니다.

```bash
uv run python scripts/evaluate_judgments.py
```

### 대화 흐름

`evals/questions.json`의 23개 시나리오(28개 질문)로 멀티턴 전체 흐름을 평가합니다. 통과 기준은
노드 실행 여부, 멀티턴 최종 상태, 내부 정보 노출 여부 같은 자동 검사이며, 답변 내용의 정확도는
품목 판정 평가에서 따로 봅니다.

```bash
uv run python scripts/run_evaluation.py
uv run python scripts/run_evaluation.py --limit 3
```

## 데이터

데이터 출처와 이용 조건은 [data/SOURCES.md](data/SOURCES.md)를 참고하세요. 각 답변은
수집된 문서의 기준일과 출처를 함께 표시하며, 실제 접수 가능 여부를 보장하지 않습니다.
