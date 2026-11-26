# ADR-0001 비밀값 검사 도구: Betterleaks v1.10.1

| 항목 | 내용 |
| --- | --- |
| 상태 | 채택 |
| 기록 기준일 | 2026-11-26 |
| 관련 결정 | D-O24, D-O25, D-O26, D-O27 (D-O16 대체), U-34 (비밀값 검사 도구만 해소) |
| 관련 요구사항 | NFR-SEC-01, NFR-ARCH-04, NFR-OPS-04, D-O17 |
| 관련 문서 | [결정·상태 대장](../decision-register.md) 9절, [CI/CD](../process/ci-cd.md) |

## Context

- 공개 저장소에서는 비밀값이 한 번 Push되면 CI 실패로 공개를 되돌릴 수 없다. 기존 결정 D-O16은 커밋 전 로컬 검사를 "고려"하고 CI 검사를 함께 두는 수준이었다.
- NFR-SEC-01과 D-O17은 비밀값·실제 키를 소스코드와 Git에 노출하지 않도록 요구한다.
- CI 1단계(ci-cd.md 1절)에 비밀값 검사가 포함돼 있어 도구 선택이 필요했다 (U-34).
- 선택 조건(판단): CLI 직접 실행, Git Hook 직접 구성(pre-commit 프레임워크 미사용), staged 변경분과 Git 이력 검사, 외부 통신 없이 동작, 결과 마스킹, 배포 파일 무결성 검증 가능.

## Alternatives

근거 유형은 명세 확인(공식 저장소 문서·릴리스 정보)이다. 표의 내용은 기록 기준일 기준이다.

| 항목 | Gitleaks | Betterleaks | TruffleHog | detect-secrets |
| --- | --- | --- | --- | --- |
| 유지보수 | 보안 패치 중심 단계로 전환 | 활발. Gitleaks 원저자 참여. 2.0.0은 정식판 이전 | 활발 | 최종 릴리스 2024-05 |
| 검토 버전 | v8.30.1 | v1.10.1 (2026-11-12) | v3.100.1 | v1.5.0 |
| 라이선스 | MIT | MIT | AGPL-3.0 | Apache-2.0 |
| staged 변경분 검사 | `git --pre-commit --staged` | `git --pre-commit --staged` | staged 한정 여부 미확인 | 파일 단위 |
| Git 이력 검사 | 지원 | 지원 | 지원 | 설계상 미지원 (baseline 방식) |
| 외부 자격 증명 검증 | 없음 | 기본 비활성 (`--validation`으로 활성) | 기본 활성 (`--no-verification`으로 비활성) | 일부 플러그인 활성 (`--no-verify`) |
| 결과 마스킹 | `--redact` | `--redact` | 옵션 미확인 | baseline에 해시만 저장 |
| 배포 파일 무결성 | 체크섬 | 체크섬 + Sigstore 서명 번들 + GitHub 릴리스 증명 | 체크섬 + cosign 서명 | PyPI 해시 |

제외 근거 (판단):

- Gitleaks: 기능은 충족하지만 보안 패치 중심 유지보수 단계라 장기 사용 근거가 약하다. 설정 형식은 Betterleaks가 호환한다.
- TruffleHog: 발견한 자격 증명을 기본으로 외부 서비스에 보내 검증한다. 오프라인 기본 원칙과 맞지 않고, 공식 Hook 예시는 검증된 결과만 실패로 처리해 가상 데이터를 쓰는 이 프로젝트에서 미검증 비밀값을 놓칠 수 있다. 라이선스가 AGPL-3.0이다.
- detect-secrets: Git 이력 검사를 지원하지 않고 2024-05 이후 릴리스가 없다.

## Decision

| 결정 | 내용 | 결정 대장 |
| --- | --- | --- |
| 도구 | Betterleaks v1.10.1 CLI | D-O24 |
| 외부 자격 증명 검증 | 비활성 (`--validation`을 쓰지 않는다) | D-O24 |
| 결과 마스킹 | 필수 (`--redact`) | D-O24 |
| 종료 코드 | 정상 0, 탐지 3 (`--exit-code 3`). 0 이외의 모든 종료 코드는 실패로 처리한다 (Fail-closed) | D-O24 |
| 공통 검사 설정 | 저장소에서 버전 관리한다. v1은 저장소 설정을 자동으로 읽지 않으므로 명시적으로 지정한다 | D-O24 |
| 배포 파일 검증 | GitHub 릴리스 증명, Sigstore 서명, SHA-256 대조를 모두 통과한 배포 파일만 실행한다 | D-O24 |
| 로컬 검사 | Git pre-commit Hook을 직접 구성하고 필수 작업 규칙으로 적용한다. Hook은 우회할 수 있다 | D-O25 |
| CI 검사 | 별도 Action 없이 CLI를 직접 실행한다. Linux 배포 파일에도 같은 검증 관문을 적용한다 | D-O26 |
| GitHub 보조 방어 | Secret Scanning과 Push Protection을 보조 방어 수단으로 도입한다. 주 검사 수단을 대체하지 않는다 | D-O27 |

## Rationale

- MIT 라이선스이고 staged 변경분·Git 이력 검사, 마스킹, 종료 코드 지정을 지원한다 (명세 확인, 실행 검증).
- 외부 자격 증명 검증이 기본 비활성이고 네트워크 차단 환경에서 같은 결과를 냈다 (실행 검증, macOS arm64).
- 체크섬 파일에 Sigstore 서명이 있어 체크섬만 제공하는 도구보다 배포 파일 검증 근거가 강하다 (명세 확인, 실행 검증).
- Gitleaks 설정 형식(`.gitleaks.toml` 등)과 호환된다 (명세 확인).
- 로컬 Hook과 CI를 함께 두는 이유: Hook은 Push 전에 막을 수 있지만 우회할 수 있다. CI는 Hook 실행을 강제하지 않지만, Hook을 거치지 않은 변경도 병합 전에 다시 검사하며 Push된 뒤에 실행된다.

## Consequences

- **Hook 우회:** 로컬 Hook은 `--no-verify`, Hook 미설치 등으로 우회할 수 있다. CI 필수 검사는 Hook 실행 자체를 강제하지 않으며, Hook을 거치지 않은 변경도 병합 전에 다시 검사한다 (D-O26, D-O08).
- **CI의 한계:** CI 검사는 이미 Push된(공개된) 비밀값을 보호하지 못한다. 노출이 확인되면 Git 이력 정리만으로는 부족하며 해당 비밀값을 폐기·교체해야 한다.
- **종료 코드:** 실행 오류는 `--exit-code 3`을 지정해도 1을 반환한다. 탐지(3)와 오류(1)를 구분할 수 있지만, 둘 다 실패로 처리한다.
- **v2 전환:** v2에서 호환되지 않는 변경(명령 체계, `.gitleaksignore` 미지원 등)이 예정돼 있다. 버전 변경은 새 결정과 재검증 대상이다.
- **검증 도구 의존:** Sigstore 서명 검증에 cosign이 필요하다. cosign 자체도 검증해야 하므로 신뢰 사슬이 한 단계 늘어난다.
- **Hook·CI 구성 전:** #9 완료 전까지는 수동 검사 절차로 대신한다.

## Verification

근거 유형은 실행 검증이며, 검증 상태는 **검증 불충분**(macOS arm64 단독 실행 범위)이다. 검증 스크립트는 임시 디렉터리에서 실행하고 삭제했다. 재현 가능한 스크립트는 Hook·CI 연동 단계(#9)에서 저장소에 둔다.

### 배포 파일 검증 (macOS arm64)

| 관문 | 검증 종류 | 결과 |
| --- | --- | --- |
| G0 | cosign v3.1.6 `darwin-arm64`의 **GitHub 릴리스 증명** (`gh release verify-asset`, predicate `https://in-toto.io/attestation/release/v0.2`) | 통과 |
| G1 | Betterleaks `checksums.txt`의 **Sigstore 서명 검증** (`cosign verify-blob --bundle`) | 통과. identity `https://github.com/betterleaks/betterleaks/.github/workflows/release.yml@refs/tags/v1.10.1`, issuer `https://token.actions.githubusercontent.com` |
| G1-neg | 틀린 identity(`v1.10.0`)로 검증 | 거부됨 (정상) |
| G2 | 서명 검증된 체크섬과 `betterleaks_1.10.1_darwin_arm64.tar.gz`의 SHA-256 대조 | 일치 |
| G3 | Betterleaks tar.gz의 **GitHub 릴리스 증명** | 통과 |

- 신뢰 사슬의 출발점은 기존에 설치된 `gh` 2.102.0이며, `gh` 자체의 무결성은 검증하지 않았다.
- 위 관문은 GitHub 릴리스 증명과 서명된 체크섬 확인이다. **SLSA 빌드 출처 검증이 아니다.** cosign과 Betterleaks 모두 SLSA 빌드 출처 증명을 찾지 못했고(`gh attestation verify` 결과 없음), 빌드 출처는 미검증이다.
- 관문 통과 후 압축 해제한 바이너리의 SHA-256: `13ac5109fa85a590c7ba6e7f130311e0c60a2bf582c3aac073176c93b46621a8`

### 기능·보안 시나리오 (macOS arm64, 가상 비밀값)

가상 비밀값은 실행 때마다 무작위로 생성했고 실제 자격 증명은 쓰지 않았다. 네트워크 차단은 `sandbox-exec`의 네트워크 거부 정책으로 구성했고, 대조군 요청이 차단 환경에서만 실패하는 것을 확인했다.

| # | 시나리오 | 결과 | 판정 |
| --- | --- | --- | --- |
| S1 | 정상 파일 | 종료 코드 0, 탐지 없음 | 통과 |
| S2 | staged 변경분의 가상 비밀값 (사용자 정의 규칙 형식, `ghp_` 형식) | 종료 코드 1, 각 규칙 1건 | 통과 |
| S3 | unstaged·미추적 파일의 비밀값 공존 | staged 파일만 탐지 | 통과 |
| S3b | 정상 staged 파일 + 비밀값이 든 unstaged 파일 | 종료 코드 0 | 통과 |
| S2-net | 정상 네트워크 환경에서 S2 재실행 | 차단 환경과 동일 | 통과 |
| S4 | 추가 후 삭제된 비밀값 | 이력 검사에서만 탐지, 작업 트리 검사 0건 | 통과 |
| S5 | 공통 설정 미지정 | 사용자 정의 규칙 미적용 | 설정 지정 필요성 확인 |
| S6 | `--redact` | 출력·보고서에 원문 0건. 미지정 대조군은 원문 포함 | 통과 |
| S7 | 없는 설정 파일, Git 저장소가 아닌 경로 | 종료 코드 1 / 1 | 오류와 기본 탐지 코드가 같음 → 탐지 코드 3으로 결정 |
| S8 | `--exit-code 3` | 종료 코드 3 | 통과 |

#5(PR #12)의 커밋 전 수동 검사(staged 변경분, 기존 이력, Push 전 전체 이력)에서 위 바이너리를 같은 조건으로 사용했고 모두 종료 코드 0이었다.

### 미검증

| 항목 | 상태 | 검증 시점 |
| --- | --- | --- |
| Linux(CI) 배포 파일의 검증 관문 | 미검증 | #9 |
| 실제 pre-commit Hook 연동, Hook을 거치지 않은 커밋의 CI 검출 | 미검증 | #9 |
| CI 실행과 실패 시 병합 차단 | 미검증 | #9 |
| 탐지율·오탐률 | 미측정 | 별도 |
| 외부 통신 시도 여부 | 미검증. 차단 환경에서 같은 결과(통신 없이 동작)만 확인 | 별도 |
| SLSA 빌드 출처 | 미검증 (증명 없음) | 해당 증명 제공 시 |
| GitHub Secret Scanning·Push Protection | 도입 결정은 확정(D-O27). 저장소 설정 활성화는 API 조회로 확인. 실제 차단 동작은 미검증 | #9 |

이후 검증 결과는 결정 대장의 D-O24 ~ D-O27 검증 상태에 기록한다. 결정이 바뀌면 이 ADR을 수정하지 않고 후속 ADR로 대체한다.

### 출처

- Betterleaks: [저장소](https://github.com/betterleaks/betterleaks), [v1.10.1 README](https://github.com/betterleaks/betterleaks/blob/v1.10.1/README.md), [v1.10.1 scanning.md](https://github.com/betterleaks/betterleaks/blob/v1.10.1/docs/scanning.md), [v1.10.1 config.md](https://github.com/betterleaks/betterleaks/blob/v1.10.1/docs/config.md), [릴리스](https://github.com/betterleaks/betterleaks/releases/tag/v1.10.1)
- Gitleaks: [저장소](https://github.com/gitleaks/gitleaks)
- TruffleHog: [저장소](https://github.com/trufflesecurity/trufflehog), [PreCommit.md](https://github.com/trufflesecurity/trufflehog/blob/main/PreCommit.md)
- detect-secrets: [저장소](https://github.com/Yelp/detect-secrets), [PyPI](https://pypi.org/project/detect-secrets/)
- cosign: [v3.1.6 릴리스](https://github.com/sigstore/cosign/releases/tag/v3.1.6)
