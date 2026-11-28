# CI/CD와 DevSecOps

기준일: 2026-11-26

도구 선택은 각 단계 도입 시 결정한다 (U-34). 비밀값 검사 도구는 Betterleaks로 결정했다 (D-O24, [ADR-0001](../adr/0001-secret-scanning-betterleaks.md)). CD는 기술 선택과 배포 구조가 확정된 이후에 설계한다.

## 1. 단계별 CI

| 단계 | 추가 검사 | 시점 |
| --- | --- | --- |
| 1 | PR 제목 형식, 비밀값 검사 (D-O26) | Phase 0 |
| 2 | 빌드, 단위 테스트, 의존성 취약점 검사 | 첫 코드 |
| 3 | Testcontainers 통합 테스트, PoC 시나리오 테스트, 확장 회귀 테스트 | Phase 1 (해당 기능을 처음 구현할 때) |
| 4 | 아키텍처 검증 | 정식 모듈 생성 시 |
| 5 | 정적 분석, 코드 스타일 검사 | v0.1 착수 |
| 6 | 버전별 보안 테스트 | v0.1부터 |
| 별도 | 성능 측정, 장시간 장애 실험, 다중 인스턴스 재현, AI 리뷰 비교 실험 | 수동 실행 또는 예약 |

| 구분 | 원칙 |
| --- | --- |
| 필수 상태 검사 | 단계가 추가되면 Rulesets의 필수 검사 목록에 반영한다. CI가 실패하면 병합할 수 없다 |
| PR CI에 포함하는 장애 테스트 | 재시작, 연결 차단처럼 결정적으로 재현되는 핵심 장애 대응 테스트 |
| 별도 워크플로 | 공유 러너에서 측정값이 흔들리거나 오래 걸리는 실험. 결과는 실행 환경 정보와 함께 산출물로 남긴다 |
| 커밋 전 로컬 검사 | 공개 저장소에서는 CI 실패만으로 비밀값 공개를 막을 수 없으므로 커밋 전 비밀값 검사를 필수 작업 규칙으로 한다 (D-O25). 로컬 Hook은 우회할 수 있으므로 CI 비밀값 검사를 필수 상태 검사로 함께 둔다 (D-O26). CI는 Hook 실행 자체를 강제하지 않으며, Hook을 거치지 않은 변경도 병합 전에 다시 검사한다. CI는 이미 Push된 비밀값을 보호하지 못하며, 노출된 비밀값은 폐기·교체한다 |

## 2. GitHub Actions 보안

| 항목 | 규칙 |
| --- | --- |
| 워크플로 토큰 권한 | 기본은 읽기 전용. 필요한 Job에만 필요한 권한을 명시한다 |
| 외부 Actions | 커밋 SHA 고정을 기본으로 검토한다. 버전 갱신은 별도 PR |
| Secrets | 필요한 Job에서만 참조하고 로그에 출력하지 않는다. PR CI는 가능한 한 Secret 없이 동작하게 설계한다 |
| 외부 PR·Fork | Secret 없이 실행되는 방식으로 처리한다 |
| pull_request_target | 사용하지 않는 것을 기본으로 한다. 사용할 경우 신뢰하지 않는 PR 코드를 Secret이 있는 맥락에서 실행하지 않는다 |
| AI 리뷰 프롬프트 주입 | PR 내용(코드, 주석, 설명)은 신뢰하지 않는 입력으로 취급한다. 리뷰 도구에는 댓글 작성 외의 쓰기 권한을 주지 않는다 |
| Workflow 변경 | 단독 PR로 하고, 권한·Secret·트리거 변경 내역을 PR의 보안 영향에 적는다 |
| Timeout | 모든 Job에 실행 시간 상한을 둔다 |
| 필수 검사 우회 방지 | Rulesets 우회 목록을 비운다. 필수 검사 이름을 바꿀 때는 git-workflow.md의 전환 순서를 따른다 |
| 의존성 갱신 | 자동 갱신 PR도 같은 CI와 리뷰 절차를 거친다 |

이 규칙은 NFR-SEC-16(인증 경계별 최소 권한)의 CI/CD 경계 적용이다.

## 3. 비밀값 검사 실행 (D-O24 ~ D-O26)

| 항목 | 방법 |
| --- | --- |
| 설치 (macOS arm64, Linux x86_64) | `scripts/install-betterleaks.sh`. gh 2.93.0 이상을 확인하고(이전 버전은 증명 조회 요청에 Authorization 헤더를 TUF 미러로 보낸다, GHSA-8xvp-7hj6-mcj9), ADR-0001의 G0 ~ G3를 모두 통과해야 저장소 밖(`~/.cache/fvs-tools/betterleaks-1.10.1/`)에 설치한다. 설치한 실행 파일의 SHA-256을 출력한다. 다른 위치는 `--dest`와 `BETTERLEAKS_BIN`으로 지정 |
| 설치 (Windows x64) | 설치 스크립트는 지원하지 않는다. `betterleaks_1.10.1_windows_x64.zip`을 G0 ~ G3와 같은 관문(cosign 릴리스 증명, `checksums.txt` Sigstore 서명, ZIP SHA-256 대조, ZIP 릴리스 증명)으로 수동 검증한 뒤 `betterleaks.exe`를 저장소 밖에 둔다. 기본 위치는 `~/.cache/fvs-tools/betterleaks-1.10.1/betterleaks.exe`이고, 다른 위치는 `BETTERLEAKS_BIN`으로 지정한다. Hook과 검사 스크립트는 Git Bash에서 실행한다 |
| 실행 파일 무결성 | `scripts/secret-scan.sh`에 플랫폼별 기대 SHA-256을 고정하고 사용 전마다 대조한다. 고정값은 배포 파일(압축 파일)이 아니라 압축을 푼 실행 파일의 해시다. darwin_arm64는 ADR-0001 실행 기록의 값이다. windows_x64는 관문을 통과한 공식 배포 ZIP에서 꺼낸 `betterleaks.exe`의 해시다. 그 ZIP의 해시(`53d4b37635a999992fb8e1d79f8215279315cbb3b4139314289b69407e79143d`)는 서명된 `checksums.txt`와 대조할 수 있으며 고정값과는 다른 값이다. linux_x64는 관문을 통과한 공식 배포 tar.gz(해시 `c174b42d7aa60caf58c0c3e555c0e4bed01fe6b0d99a412bce777b5af4ce913e`)에서 Windows로 꺼낸 `betterleaks`의 해시이며, Windows에서는 실행하지 않았다. Linux에서의 실제 실행은 CI 첫 실행에서 확인한다. 그 밖의 플랫폼은 검사를 거부한다. 실행 파일 옆의 해시 파일은 신뢰하지 않는다. 고정값 변경은 보안 영향 있음으로 PR에 적는다 |
| 검사 | `scripts/secret-scan.sh staged` (staged 변경분), `scripts/secret-scan.sh history` (모든 ref의 전체 이력), `scripts/secret-scan.sh history --rev <SHA>` (ref에 연결되지 않은 커밋 추가). 공통 설정 `.betterleaks.toml`을 명시적으로 지정하고, 사용 전마다 버전과 SHA-256을 대조한다 |
| 종료 코드 | 0 통과, 3 탐지, 2 검사·설정 오류. 0 이외는 모두 실패다. 종료 코드는 파이프라인이 아니라 검사 프로세스에서 직접 받는다 |
| Hook 설치 | 클론마다 한 번 `git config --local core.hooksPath scripts/hooks`. 전역 설정은 쓰지 않으며 별도 설치 스크립트는 두지 않는다. pre-commit은 staged 변경분과 기존 전체 이력을, pre-push는 전체 이력과 실제 전송 대상 커밋(표준 입력의 로컬 SHA, 삭제 제외)을 검사한다. 입력 형식 오류나 검사 실패는 Push를 차단한다 |
| Hook 해제 | `git config --local --unset core.hooksPath` |
| Hook 확인·복구 | `git config --show-origin --get core.hooksPath`로 값과 위치를 확인한다. 값이 다르거나 전역 설정에서 온 경우 로컬 값을 다시 지정한다 |
| Hook 미설치·미적용 | `core.hooksPath` 미설정, Hook 파일이 없는 브랜치, `--no-verify` 사용 등으로 Hook이 실행되지 않으면 같은 검사를 수동으로 실행해야 한다. 커밋 전 `staged`와 `history`, Push 전 `history`와 전송할 커밋의 `--rev`. 검사 스크립트가 없는 브랜치에서는 D-O28의 수동 절차를 따른다 |
| D-O28 예외 | Hook 설치만으로 D-O28 예외를 종료하지 않는다. Rulesets와 병합 차단 검증이 끝나 예외가 종료될 때까지 필수 수동 검사와 PR 검증란의 결과 기록을 유지한다 |
| Hook의 한계 | `--no-verify`, 설정 해제로 우회할 수 있다. Hook 스크립트는 저장소 파일이므로 브랜치를 바꾸면 그 브랜치의 Hook이 실행된다. Hook·검사 스크립트 변경은 보안 영향 있음으로 PR에 적는다. CI는 Hook 실행을 강제하지 않고, Push된 변경을 병합 전에 다시 검사한다. 이미 Push된 비밀값은 보호하지 못한다 (1절) |
| 검사 설정 신뢰 | PR이 `.betterleaks.toml`이나 검사 스크립트를 바꿔 검사를 약화할 수 있다. PR 이벤트에서 CI는 base 커밋의 검사·설치 스크립트, `.betterleaks.toml`, `check-docs.py`와 테스트 코드를 쓰고, 검사 대상은 PR 체크아웃과 전체 Git 이력이다. `secret-scan.sh`에는 신뢰된 `--config`를, `check-docs.py`에는 검사 대상 `--root`를 지정한다. main Push에서는 해당 Push 커밋을 기준으로 한다. 검사 스크립트·설정을 바꾸는 PR은 병합 전 CI에서 새 버전으로 검증되지 않으므로 로컬 테스트 증거로 확인한다. Workflow 파일 자체의 변경은 이 방식으로 막지 못하며, Workflow 단독 PR 규칙과 저장소 소유자 검토에 의존한다 (D-O33) |
