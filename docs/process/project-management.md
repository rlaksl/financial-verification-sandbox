# 프로젝트 관리

기준일: 2026-11-26

각 절차는 실제로 무엇을 막거나 도와주는지가 분명할 때만 둔다. 이 문서는 운영 규칙이며, 각 GitHub 기능의 실제 제공 범위는 설정 시점에 확인한다 (D-O04).

## 1. GitHub Projects

### 1.1 필드

| 필드 | 형식 | 값 | 쓰임 |
| --- | --- | --- | --- |
| Status | 단일 선택 | Backlog / Ready / In Progress / In Review / Blocked / Done | 흐름 관리 |
| Iteration | 반복 | 1주 | Sprint |
| Priority | 단일 선택 | P0 / P1 / P2 | P0은 필수 보안 요구사항 또는 관문을 막는 작업 |
| Estimate | 숫자 | 1, 2, 3, 5, 8 | Story Point (XS 1, S 2, M 3, L 5, XL 8) |
| Area | 단일 선택 | 인증, 토큰, 무결성, 재전송, 키 관리, 배포, 업무, 문서, DevSecOps | 영역별 진척 |
| Verification | 단일 선택 | 미검증 / 검증 예정 / 검증 통과 / 검증 실패 / 검증 불충분 / 해당 없음 | 실행 검증 상태 |
| Ref | 텍스트 | D-, U-, T-, G-, SC-, FR-, NFR- 식별자 | 문서 연결 |

- Size와 Story Point를 따로 두지 않고 Estimate 하나로 관리한다.
- Issue Field로 같은 정보를 관리할 수 있다면 어느 한쪽에만 둔다.
- Status의 Done과 Verification의 검증 통과는 별개다. PoC가 실패했더라도 실험과 실패 원인 기록이 끝났으면 이슈는 Done이 될 수 있다. 필수 보안 검증에 실패한 후보는 채택하지 않는다.

### 1.2 View

| View | 형태 | 필터·그룹 | 쓰임 |
| --- | --- | --- | --- |
| 현재 Sprint | Board | 현재 Iteration, Status별 | 작업 시작 시 확인 |
| Sprint 계획 | Table | Iteration별, Estimate 합계 | Planning |
| Backlog | Table | Backlog·Ready, Priority 순 | 다음 작업 선택 |
| 로드맵 | Roadmap | Milestone별 | 전체 진척 |
| PoC 관문 | Table | Type = PoC Gate, Verification별 | Phase 1 판단 |
| 결정 대기 | Table | Type = Decision 또는 라벨 blocked-by-decision | 기능 착수 전 결정 확인 |
| 보안 영향 | Table | 라벨 security-impact | 보안 변경 추적 |

## 2. Milestone, Sprint, Issue

### 2.1 Milestone

결과 단위다. 기간이 아니라 종료 조건([release.md](release.md))으로 닫는다.

| Milestone | 목표 |
| --- | --- |
| Phase 0 | 초기 설정과 설계 문서 정리 |
| Phase 1 | PoC 관문 검증 |
| Phase 2 | 보안·성능·장애 비교 실험 |
| Phase 3 | 기술 선택과 ADR 확정 |
| v0.1 ~ v0.4, v1.0, v1.1, v1.2 | 정식 서비스 |

### 2.2 Sprint

| 항목 | 규칙 |
| --- | --- |
| 기간 | 1주 |
| 용량 | 초기에는 정하지 않는다. 실제 완료한 Estimate 합계(Velocity)를 기록하고 이후 계획에 반영한다 |
| 집계 단위 | 실제 작업 단위만 집계한다. Sub-issue가 있으면 Sub-issue, 없으면 그 이슈. Epic과 Sub-issue를 가진 상위 이슈에는 Estimate를 넣지 않는다 |
| 집계 제외 | Sprint 운영 기록용 Chore 이슈 |
| 이월 | 기존 Estimate를 유지한다. 작업 범위가 바뀐 경우에만 재산정 사유를 기록하고 변경한다 |
| Story Point | 시간이 아니라 작업량·복잡도·불확실성의 상대 크기. 8을 넘으면 분해한다 |

### 2.3 Issue Type

| Type | 용도 |
| --- | --- |
| Epic | Milestone 안의 큰 목표. Sub-issue로 분해 |
| Research | 명세·소스 조사 |
| PoC Gate | 관문 (G1-a ~ G7). 구현, 시나리오 테스트, 결과 기록을 Sub-issue로 |
| Experiment | 비교 실험 |
| Decision | 결정과 ADR 작성 |
| Feature | 정식 기능 |
| Bug | 결함 |
| Docs | 문서 작업 |
| Chore | 설정, 도구, Sprint 운영 |

### 2.4 Ready와 Done

공통 Ready 조건: 완료 기준과 Ref가 있다.

| Type | Ready 추가 조건 | Done 조건 |
| --- | --- | --- |
| Feature | Estimate, 구현에 필요한 업무 정책이 확정됨 | PR 병합, 테스트, 문서 반영 |
| PoC Gate | Estimate, 실험 조건이 확정됨 (관문별 선행 조건) | 시나리오별 판정 상태와 실패 원인 기록 |
| Experiment | Estimate, 측정 조건이 확정됨 | 측정 결과와 환경 기록 |
| Research | 조사 질문이 명시됨 | 근거 유형과 출처 기록 |
| Decision | 결정할 질문과 후보가 명시됨 | 결정 대장 갱신 (필요 시 ADR) |
| Bug, Docs | 재현 조건 또는 변경 범위 | PR 병합 |
| Chore | — | 코드 변경이 있으면 PR 병합, 없으면 실제 동작과 완료 기준 확인 |

- Research와 Decision은 미결정 문제를 해결하기 위한 작업이므로 결정 완료를 착수 조건으로 두지 않는다.
- 코드 변경이 없는 작업(GitHub 설정, Sprint 운영 등)에는 main 병합을 요구하지 않는다.

### 2.5 기능 착수 전 결정 확인

Feature 이슈를 Ready로 옮기기 전에 [요구사항 문서](../requirements/requirements.md) 9절에서 해당 버전의 미결정 정책을 확인한다. 결정되지 않았으면 Decision 이슈를 만들고 기능 이슈에 `blocked-by-decision` 라벨을 붙인다. 정책값을 구현 중에 임의로 정하지 않기 위한 장치다.

### 2.6 라벨

Issue Type이 종류를 맡으므로 라벨은 여러 종류에 걸치는 속성에만 쓴다: `security-impact`, `extension-e3`, `extension-e4`, `needs-adr`, `blocked-by-decision`.

## 3. Sprint 운영

| 활동 | 시점 | 입력 | 출력 |
| --- | --- | --- | --- |
| Planning | Sprint 시작 | Ready 이슈, 이전 Velocity, 결정 대기 View | Sprint 목표 한 문장, Iteration 배정, 이번 Sprint에 필요한 결정 목록 |
| Review | Sprint 종료 | Done 이슈, 테스트·관문 결과 | 증거 기준의 완료 확인, status.md 갱신, Milestone 진척 |
| Retrospective | Review 직후 | 이번 Sprint 경험 | 잘된 것, 막힌 것, 바꿀 것. 바꿀 것 1 ~ 2개만 다음 Sprint 이슈로 |

- Sprint마다 Chore 이슈 하나에 목표, 완료 Estimate, 회고 요약을 남긴다. 별도 회의록 문서는 만들지 않는다.
- Daily Scrum은 두지 않고, 작업 시작 시 Blocked 상태를 확인한다.
