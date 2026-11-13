# 데이터 출처와 이용 조건

모든 데이터는 **한국에서 외국으로 발송**하는 국제우편 기준이다. 수집일은 각 md 파일 front matter의 `collected_at`에 기록한다.

## 1. 우체국 국제우편 국가별 발송조건 (항목 메타데이터 + 국가별 문서)

| 서비스 | 수집 경로 (ems.epost.go.kr) | 산출물 |
|---|---|---|
| 국제특급(EMS) | `/front.EmsApplyGoCondition.postal` | `countries.json`, `docs/epost/countries/<코드>.md` |
| EMS프리미엄 | `/front.EmsApplyGoConditionPremium.postal` | 〃 |
| 국제소포(항공/선편) | `/front.EmsParcelAirShipSendCondition.postal` (`frnMailDivcdTab=2`) | 〃 |
| 국제통상(서신·인쇄물·소형포장물 등) | `/front.EmsParcelAirShipSendCondition.postal` (`frnMailDivcdTab=1`) | 〃 |
| K-Packet | `/front.EmsKPacketSendCondition.postal` (`frnMailDivcdTab=14`) | 〃 |

- 국가별로 기본 조건 표(요금적용지역, 최대규격, 제한중량 등), 긴급공지, 접수 시 주의사항, 금지·제한품목, 배달특이사항, 세관·통관사항을 수집한다.
- 스크립트: `scripts/collect_epost_conditions.py` → `scripts/build_country_data.py`

## 2. 우체국 국제우편 공통 안내 (`docs/epost/common/`)

EMS 국가별 공통사항, 보낼 수 있는/없는 물품(항공탑재금지물품), 서비스 안내(EMS, 국제소포, EMS프리미엄, 소형포장물, K-Packet), 손해배상 규정, 부가취급 수수료, 상업송장 쓰는 법, 수출우편물 발송확인, 미국행 식품 사전신고, 동·식물 검역 안내, 국가별 요금적용 지역.

- 스크립트: `scripts/collect_epost_common.py`

**이용 조건(1·2 공통)**: 과학기술정보통신부 우정사업본부가 업무상 작성해 공개한 공공저작물(저작권법 제24조의2)로 보고, 출처를 표시해 비상업적 교육 목적으로 이용한다. 사이트의 `robots.txt`는 자동 수집을 허용하지 않으므로 요청 간격(2.5초)을 두고 국가·페이지당 1회만 수집하며, 원본 HTML을 캐시해 재요청하지 않는다. 원본 HTML(`data/raw/`)은 저장소에 올리지 않는다.

## 3. 법령·고시 (`docs/law/`, 국가법령정보센터 www.law.go.kr)

| 구분 | 이름 |
|---|---|
| 법률 | 우편법 |
| 대통령령 | 우편법 시행령, 국제우편규정 |
| 부령 | 우편법 시행규칙 |
| 고시 | 국제우편물의 종류별 이용조건 및 취급절차 / 외국으로 발송하는 우편물의 규격·포장 및 외부기재사항 / 국제우편금지물품 / 우편금지물품의 내용에 관한 고시 / 국제우편물 손해배상액과 국제특급우편 이용자에 대한 실비 지급기준 / 국제우편에 관한 요금 / 국제우편 연계서비스 요금 / 국제우편요금등을 감액할 수 있는 우편물의 종류·취급요건·감액범위 / 국제우편요금의 별납 및 후납의 표시와 취급우체국 / 국제우편 이용에 관한 수수료 |

- 현행본만 수집한다. 고시의 별표(HWP/HWPX/PDF)는 텍스트로 추출해 같은 문서 뒤에 붙이고, 원문 링크를 함께 남긴다. 본문 속 표·그림 이미지는 원문 이미지 링크로 대체한다.
- 스크립트: `scripts/collect_laws.py` (별표 추출: `scripts/hwp_text.py`)

**이용 조건**: 법령·고시는 저작권법 제7조에 따라 저작권 보호 대상이 아니다. law.go.kr `robots.txt`는 수집을 허용한다.

## 주의

국제우편 조건은 수시로 바뀐다. 답변에는 기준일을 함께 표시하고, 최종 확인은 우체국 고객센터(1588-1300)나 인터넷우체국에서 하도록 안내한다.
