# 작업 절차와 검증

기준일: 2026-11-26

규칙 자체는 [AGENTS.md](../../AGENTS.md)와 각 프로세스 문서에 있다. 이 문서는 그 규칙을 작업 순서와 검사 명령으로 연결한다. 특정 개발 도구의 설정은 두지 않는다 (D-O15, D-O23).

## 1. 작업 유형별 최소 문서

항상 [status.md](../status.md)를 먼저 읽는다. 그다음 작업 유형에 해당하는 문서의 **관련 절만** 읽고, 필요한 항목은 식별자로 찾는다 (예: `grep -n "D-O25" docs/decision-register.md`).

| 작업 유형 | 읽을 문서 (관련 절) |
| --- | --- |
| 설계 문서 수정, 결정 변경 | 결정 대장 해당 절과 10·11절, [documentation.md](documentation.md) |
| PoC 관문 | [PoC 계획](../poc/plan.md)의 해당 관문, 1절, 7절, 관련 T·SPEC·SRC |
| 정식 기능 (Feature) | 요구사항 해당 FR·NFR과 9절, 관련 업무 정책, 위협 모델의 관련 공격자 |
| CI, Hook, 비밀값 검사 | [ci-cd.md](ci-cd.md), [ADR-0001](../adr/0001-secret-scanning-betterleaks.md), 결정 대장 D-O24 ~ D-O28 |
| Issue·PR·브랜치·태그 | [git-workflow.md](git-workflow.md), [project-management.md](project-management.md), [release.md](release.md) |
| AI 리뷰 | [ai-review.md](ai-review.md), 결정 대장 D-O12·D-O13 |

## 2. 착수 전 확인

1. Issue의 목적, 완료 기준, 관련 식별자를 확인한다.
2. 관련 식별자의 현재 상태를 결정 대장에서 확인한다. 대체된 항목은 후속 식별자를 따라간다.
3. 필요한 정책·기술이 미결정인지 결정 대장 10절과 요구사항 9절에서 확인한다. 미결정이면 착수하지 않고 결정을 요청한다 (AGENTS.md 3·4절).
4. 브랜치, 작업 트리, 기준 커밋을 확인한다 (`git status`, `git log -1`).

## 3. 작업 전후 검사

| 시점 | 검사 | 명령 | 통과 조건 |
| --- | --- | --- | --- |
| 문서 변경 후 | 필수 파일, 식별자 중복 정의, 상대 링크, 공개 금지 정보 | `python3 -I scripts/check-docs.py` | 종료 코드 0 |
| 검사 스크립트 변경 후 | 검사 스크립트 테스트 | `python3 -I scripts/tests/test_check_docs.py` | 종료 코드 0 |
| 커밋 전·Push 전 | 비밀값 검사 | D-O25의 검사 절차 (Hook 구성 전에는 D-O28의 수동 절차) | 종료 코드 0 |
| 커밋 후 | 작성자 정보와 메시지 | `git log -1 --format='%an %cn%n%B%n%(trailers)'` | 기존 작성자 정보, D-O31 위반 표시 없음 |

- 0이 아닌 종료 코드는 모두 실패다. 실패를 우회하지 않는다.
- 검사 결과는 파이프라인 끝의 명령이 아니라 검사 명령 자체의 종료 코드로 판단한다.

`check-docs.py`가 식별자 **정의**로 보는 것은 첫 헤더 칸이 `ID` 또는 `SC`인 표의 첫 칸이다. 다른 표나 본문에서 식별자를 참조하는 것은 중복이 아니다.

## 4. 실행 증거와 미검증 기록

PR의 검증 절과 PoC 결과에는 다음을 남긴다.

| 항목 | 기록 |
| --- | --- |
| 실행한 검사 | 명령, 실행 환경, 종료 코드, 결과 요약 |
| 실행하지 않은 검사 | "미실행"과 사유. 통과로 세지 않는다 |
| 판정 | PoC는 [plan.md](../poc/plan.md) 7절, 그 외는 [documentation.md](documentation.md) 2절의 검증 상태 값 |
| 근거 유형 | 판단, 명세 확인, 소스 확인, 실행 검증을 구분한다 |

## 5. 작업 종료와 인수인계

- 공개 상태는 PR과 [status.md](../status.md)에 남긴다. status.md 갱신 시점은 [documentation.md](documentation.md) 4절을 따른다.
- 다음 작업자에게 넘길 내용(진행 중 브랜치와 상위 브랜치, 커밋 범위, 승인 대기 항목, 미검증 항목, 다음 단계)은 로컬 전용 인수인계 파일에 남기고 커밋하지 않는다 (D-O23).
- 새 도구, 검사, 문서는 필요성이 확인된 경우에만 추가한다 (NFR-ARCH-04). 하나의 Issue 범위 밖은 수정하지 않는다.
