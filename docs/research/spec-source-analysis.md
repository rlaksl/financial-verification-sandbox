# 명세·소스 분석 기록

기준일: 2026-11-26

## 0. 문서 기준

### 0.1 역할

명세와 프레임워크 소스에서 확인한 사실을 재현 가능한 형태로 기록한다. 판단과 해석은 따로 표시한다. 결정은 [결정·상태 대장](../decision-register.md), 해결할 문제는 [기술 쟁점 대장](technical-issues.md)이 담당한다.

### 0.2 표기

| 표기 | 의미 |
| --- | --- |
| 확인 | 원문·소스를 열어 확인함 (확인 일자 2026-11-25) |
| 확인(이전) | 이전 조사에서 확인했으나 문서 작성 시 다시 열지 않음. 절 번호 미기록. **재확인 대상** |
| 판단 | 확인한 사실에 대한 해석 |
| 미확인 | 확인하지 못함 |

**이 문서의 모든 항목은 실행 검증 전이다.** 명세나 소스를 확인한 것은 실제 동작의 검증이 아니다.

### 0.3 소스 버전

| 저장소 | 태그 | 커밋 | 확인 범위 |
| --- | --- | --- | --- |
| spring-projects/spring-security | 7.2.0 | 00d500621a9561f353e63b596f4128230a70862c | 이 문서의 Spring Security 소스 사실 전부 |
| spring-projects/spring-security | 7.1.1 | a825937b8175ee85872c49d9c7fc25eea8cff991 | 일부 파일만 개별 비교 (SRC-19) |
| spring-projects/spring-data-redis | 4.2.0 | 5c390dbd32aa1fce6a064f87b8cc554b3beff83f | 캐시 writer, RedisCache |

고정 링크 형식: `https://github.com/spring-projects/spring-security/blob/<커밋>/<경로>#L<줄>`. 줄 번호는 위 태그 기준이다.

| 약어 | 경로 |
| --- | --- |
| [AS] | oauth2/oauth2-authorization-server/src/main/java/org/springframework/security/oauth2/server/authorization/ |
| [RS] | oauth2/oauth2-resource-server/src/main/java/org/springframework/security/oauth2/server/resource/ |
| [JOSE] | oauth2/oauth2-jose/src/main/java/org/springframework/security/oauth2/jwt/ |
| [CORE] | oauth2/oauth2-core/src/main/java/org/springframework/security/oauth2/core/ |
| [CFG] | config/src/main/java/org/springframework/security/config/annotation/web/ |

### 0.4 근거 자료 관리

| 대상 | 관리 방식 |
| --- | --- |
| RFC | rfc-editor.org 원문과 RFC 번호. 정오표는 별도 확인 |
| FAPI 2.0 | 최종본 원문 링크와 발행일. 현재 최종본 원문 링크 미확보 (재확인 대상) |
| OWASP ASVS | OWASP/ASVS 저장소 v5.0.0_release 태그의 영문 장별 파일 |
| OWASP SAMM | owaspsamm/core 저장소 v2.2.0 태그 |
| PostgreSQL | 공식 문서의 버전별 페이지. SPEC-50 ~ 52는 PostgreSQL 18.4 문서를 옮긴 매뉴얼 페이지에서 확인했으므로 공식 사이트 원문으로 재확인 필요 |
| Redis | redis.io 공식 문서와 확인 일자 |

---

## 1. 명세

### 1.1 RFC 10070

| 항목 | 내용 |
| --- | --- |
| 제목 | Updates to OAuth 2.0 JSON Web Token (JWT) Client Authentication and Assertion-Based Authorization Grants |
| 상태 | Standards Track, 2026년 11월. RFC 7521, 7522, 7523, 9126을 갱신 |
| 원문 | https://www.rfc-editor.org/rfc/rfc10070.txt |
| 확인 | 확인 |

| ID | 절 | 규범 수준 | 내용 | 관련 |
| --- | --- | --- | --- | --- |
| SPEC-01 | §4 (RFC 7523 §3 항목 3의 대체) | MUST / MUST NOT | 클라이언트 인증 JWT의 aud는 인가 서버의 issuer 식별자를 유일한 값으로 사용해야 한다. 토큰 엔드포인트 URL을 aud 값으로 사용하면 안 된다 | T-20, D-X11 |
| SPEC-02 | §4 (같은 항목) | MUST | 인가 서버는 issuer 식별자를 유일한 aud 값으로 포함하지 않은 JWT를 거부해야 한다 | T-20 |
| SPEC-03 | §4 (같은 항목) | MUST | 별도 프로필이 없으면 aud 값은 RFC 3986 §6.2.1의 단순 문자열 비교로 비교한다 | T-20 |
| SPEC-04 | §4 (RFC 7523 §3.2에 추가) | SHOULD (클라이언트) | 클라이언트 인증 JWT는 typ 헤더 값 `client-authentication+jwt` 또는 더 구체적인 명시적 타입으로 표시한다 | D-X11 |
| SPEC-05 | §4 (같은 위치) | NOT RECOMMENDED (서버) | 서버가 명시적 타입이 없는 JWT를 거부하는 것은 권장되지 않는다. 강화된 aud 요구를 이미 따르지만 명시적 타입을 아직 도입하지 않은 클라이언트와의 상호운용 문제가 생기기 때문이다 | D-X11 |
| SPEC-06 | §6 | 설명 | 이전 요구를 구현한 일부 클라이언트는 갱신된 요구를 엄격히 적용하는 인가 서버와 상호운용되지 않을 수 있다 | 연동 가이드 |

#### aud의 JSON 표현 (판단)

RFC 10070 원문에는 aud가 JSON 문자열이어야 하는지 배열이어도 되는지를 직접 규정한 문장이 없다. 확인된 요구는 "issuer가 유일한 값"이다. RFC 7519 §4.1.3의 aud 기본 정의(SPEC-60, 미확인)가 "일반적으로 문자열 배열이며 대상이 하나면 단일 문자열로 표현할 수 있다"는 내용으로 확인되면, 단일 원소 배열을 허용하는 해석에 근거가 생긴다.

| 형태 | 명세 판단 | 근거 |
| --- | --- | --- |
| `"aud": "<issuer>"` | 적합 | SPEC-01 |
| `"aud": ["<issuer>", "<다른 값>"]` | 부적합. 서버 거부 MUST | SPEC-01, SPEC-02 |
| `"aud": ["<토큰 엔드포인트 URL>"]` | 부적합. 서버 거부 MUST | SPEC-01, SPEC-02 |
| `"aud": ["<issuer>"]` | 명세 문언상 명시 없음. 유일한 값 요건을 충족한다는 해석이 가능 (판단) | SPEC-60 확인 대기 |

#### 명세 요구, 자체 강화, PoC 필수 기준

| 항목 | 명세 요구 수준 | 프로젝트 정책 | PoC 필수 통과 기준 |
| --- | --- | --- | --- |
| issuer 외 값을 포함한 aud 거부 | MUST | 따름 (확정) | 필수 |
| 토큰 엔드포인트 등 URL 거부 | MUST | 따름 (확정) | 필수 |
| 단일 원소 배열 거부 | 명시 없음 | 자체 강화 (우선 후보) | 정책 의존 시나리오. 채택한 경우에만 필수 |
| typ 없는 Assertion 거부 | 서버 거부 NOT RECOMMENDED | 거부하지 않음 | 필수 아님. typ 없는 정상 Assertion의 수락을 상호운용 시나리오로 둔다 |
| typ 값이 다른 JWT 타입인 경우 | 명시 없음 | 미결정 | 상세 설계 |

### 1.2 RFC 9449 (DPoP)

| 항목 | 내용 |
| --- | --- |
| 제목 | OAuth 2.0 Demonstrating Proof of Possession (DPoP) |
| 상태 | Standards Track, 2023년 9월 |
| 원문 | https://www.rfc-editor.org/rfc/rfc9449.html |
| 확인 | 확인 |

| ID | 절 | 규범 수준 | 내용 | 관련 |
| --- | --- | --- | --- | --- |
| SPEC-10 | §4.2 | MUST | Proof 헤더에 typ(dpop+jwt), alg(비대칭, none과 대칭 알고리즘 금지), jwk(개인키 포함 금지). 페이로드에 jti, htm, htu, iat. htu는 요청 대상 URI에서 쿼리와 프래그먼트를 뺀 값이다 | T-07 |
| SPEC-11 | §4.2 | MUST | jti는 같은 맥락에서 유효 기간 동안 다른 Proof와 같은 값이 될 확률이 무시할 수 있을 만큼 작아야 한다 (예: 96비트 이상 난수, UUID v4) | T-11 |
| SPEC-12 | §4.2 | 설명 | 요청 중 메서드와 URI만 Proof에 포함되며, 추가 정보를 포함하도록 확장할 수 있다 | T-08, D-X40 |
| SPEC-13 | §4.3 | MUST | 수신 서버의 검증 항목. 무조건 검증: DPoP 헤더 1개, JWT 형식, 필수 Claim, typ, alg, 서명, 개인키 미포함, htm, htu, 생성 시각. 조건부 검증: 서버가 nonce를 제공한 경우의 nonce, Access Token과 함께 보호 자원에 제시된 경우의 ath와 키 일치. 검사는 어떤 순서로 수행해도 된다 | T-12 |
| SPEC-14 | §4.3 | SHOULD | 서버는 htu 비교 전에 구문 기반·스킴 기반 정규화를 적용한다 | T-07 |
| SPEC-15 | §5.2 | MUST | 클라이언트 메타데이터 dpop_bound_access_tokens가 true이면 인가 서버는 DPoP 헤더가 없는 해당 클라이언트의 토큰 요청을 거부한다 | T-21 |
| SPEC-16 | §7.2 | MUST | DPoP와 Bearer를 함께 지원하는 보호 자원은 Bearer로 받은 DPoP 바인딩 Access Token을 거부한다 | T-22 |
| SPEC-17 | §7.3 | RECOMMENDED | 클라이언트는 일시적 오류에 대한 멱등 요청 재시도에서도 새 DPoP Proof를 생성한다 | D-X55 |
| SPEC-18 | §11.1 | MUST | 서버는 생성 후 제한된 시간 동안만 Proof를 받는다 | T-04, T-40 |
| SPEC-19 | §11.1 | 가능 | 대상 URI 맥락에서 서버는 수락 기간 동안 jti를 저장해 중복 사용을 막을 수 있다. 공유 상태가 없는 여러 서버 환경에서는 실무적으로 어려울 수 있다 | T-02, T-04, T-11 |
| SPEC-20 | §11.1 | 권고 | jti를 추적하는 서버는 불필요하게 큰 jti를 거부하거나 해시만 저장한다 | T-03 |
| SPEC-21 | §11.5 | MUST | 서버는 Proof 헤더의 typ이 dpop+jwt인지 확인한다 | T-10 |
| SPEC-22 | §11.7 | 설명 | DPoP는 요청 본문이나 헤더의 무결성을 보장하지 않는다 | T-08, T-12, D-T10 |
| SPEC-23 | §11.11 | 설명 | 클라이언트 인증과 함께 쓸 때 DPoP는 같은 TLS 터널에 있다는 사실로만 인증에 묶이며, 인증과 DPoP의 암호학적 바인딩은 이 명세의 범위 밖이다 | T-25 |

### 1.3 RFC 9421·RFC 9530 (재확인 대상)

| 항목 | 내용 |
| --- | --- |
| 원문 | https://www.rfc-editor.org/rfc/rfc9421.html , https://www.rfc-editor.org/rfc/rfc9530.html |
| 확인 | 확인(이전). 절 번호 미기록 |

| ID | 이전 조사 내용 | 관련 |
| --- | --- | --- |
| SPEC-30 | RFC 9421은 애플리케이션이 필수 구성 요소, 키 조회, 알고리즘, 오류 처리를 정하도록 한다 | T-08 |
| SPEC-31 | 리버스 프록시·TLS 종료 게이트웨이는 서버가 보는 파생 구성 요소를 바꾼다 | T-07, T-08 |
| SPEC-32 | 응답 서명에 요청 구성 요소를 포함하는 방법과 상태 코드를 서명 대상으로 삼는 방법이 있다 | T-17 |
| SPEC-33 | RFC 9530: Digest는 경로 공격자가 교체할 수 있어 TLS나 서명과 결합해야 하며, 수신자가 무시할 수 있으므로 애플리케이션이 검증을 요구해야 한다 | T-09 |

### 1.4 FAPI 2.0 (대부분 재확인 대상)

| ID | 내용 | 상태 |
| --- | --- | --- |
| SPEC-40 | OpenID Foundation의 구현자 가이드 기준, 최종본은 클라이언트 인증 JWT의 aud에 issuer 식별자만 허용하며 인가 서버가 이를 강제해야 한다 | 확인 (가이드 기준). 최종본 원문 절 번호 미확인 |
| SPEC-41 | 인가 서버가 aud를 문자열로만 받도록 요구한다는 내용 | 확인(이전), 재확인 실패. D-X11의 자체 강화 근거로 쓰려면 원문 재확인 필요 |
| SPEC-42 | 발신자 제한 Access Token만 발급(MTLS 또는 DPoP), 고객사 인증은 MTLS 또는 private_key_jwt | 확인(이전) |
| SPEC-43 | 사용자가 다루지 않는 자격 증명의 최소 엔트로피 요구 | 확인(이전). 절 번호 미확인 |
| SPEC-44 | Client Credentials 흐름은 형식 보안 분석 대상이 아니다 | 확인(이전) |
| SPEC-45 | Message Signing 최종본은 업무 API 요청·응답 서명을 다루지 않는다 | 확인(이전) |

구현자 가이드: https://openid.net/implementers-guide-fapi-2-final-vs-implementers-draft-2/

### 1.5 OWASP ASVS 5.0.0

요구사항 ID·수준·문구는 로컬 사본에서 확인했다. 태그와 파일 경로의 대응은 확인(이전)이다.

| ID | 수준 | 요지 | 관련 |
| --- | --- | --- | --- |
| 8.2.2 | L1 | 데이터 항목 단위 접근 제한 | FR-AUTH-11 |
| 9.1.1 | L1 | 자체 포함 토큰은 서명·MAC 검증 후 내용을 수락 | T-10 |
| 9.1.2 | L1 | 맥락별 알고리즘 허용 목록 | T-35-a, T-35-b |
| 9.1.3 | L1 | 검증 키는 신뢰된 사전 설정 출처에서 와야 하며 jku·x5u·jwk 헤더는 허용 목록으로 검증 | T-24, T-25 |
| 9.2.1 | L1 | 유효 기간 검증 | T-40 |
| 9.2.2 | L2 | 토큰 유형·목적 검증 | SPEC-21 |
| 9.2.3 | L2 | 대상(aud) 검증 | T-22 |
| 10.3.1 | L2 | 리소스 서버는 자신을 위한 토큰만 수락 | FR-AUTH-20, T-22 |
| 10.3.2 | L2 | 위임 권한 Claim 기반 인가 | — |
| 10.3.5 | L3 | 발신자 제한으로 탈취·재전송 토큰 사용 방지 | FR-AUTH-14 |
| 10.4.10 | L2 | 기밀 클라이언트의 백채널 요청 인증 | — |
| 10.4.11 | L2 | 필요한 Scope만 할당 | T-10 |
| 10.4.14 | L3 | 발신자 제한 토큰만 발급 | FR-AUTH-14, T-21 |
| 10.4.16 | L3 | 공개키 기반·재전송 내성의 강한 클라이언트 인증 | T-01, T-36 |

판단: DPoP Proof 검증은 Proof 안의 키로 키 보유를 확인하는 것이고, 그 키가 고객사가 승인한 키인지에 대한 신뢰 판단은 별개다. 9.1.3과 T-25의 관련은 해석으로만 유지하며, ASVS가 이를 명시적으로 요구한 것으로 기록하지 않는다.

### 1.6 저장소 공식 문서

| ID | 출처 | 내용 | 상태 |
| --- | --- | --- | --- |
| SPEC-50 | PostgreSQL INSERT 문서 | ON CONFLICT DO UPDATE는 독립적인 오류가 없으면 높은 동시성에서도 INSERT 또는 UPDATE 중 하나의 원자적 결과를 보장한다 | 확인 (미러). 재전송 방지에 필요한 "최초 삽입 성공 여부"와는 다른 보장이다 |
| SPEC-51 | 같은 문서 | RETURNING은 실제로 삽입되거나 갱신된 행만 반환한다 | 확인 (미러). DO NOTHING RETURNING 후보의 근거 |
| SPEC-52 | 같은 문서 | 유일 색인이 있는 테이블은 같은 색인 값을 다루는 동시 세션이 있으면 대기할 수 있다 | 확인 (미러). 커밋 전 대기의 세부는 미확인 |
| SPEC-53 | Redis 복제 문서 | 기본 비동기 복제이며, WAIT를 써도 강한 일관성을 갖는 시스템이 되지 않아 확인된 쓰기가 장애 전환 중 유실될 수 있다 | 확인 |
| SPEC-54 | Redis 트랜잭션 문서 | 트랜잭션의 명령은 직렬화되어 순차 실행되고 다른 클라이언트의 요청이 중간에 끼어들지 않는다. 롤백은 지원하지 않는다 | 확인 |
| SPEC-55 | Redis 스크립트 오류 시 부분 쓰기의 유지 여부 | — | 미확인 |
| SPEC-56 | Redis AOF·RDB·WAITAOF·noeviction, PostgreSQL WAL·커밋 동기화·복제·장애 전환·Fencing | — | 미확인 |

### 1.7 추적 중인 명세 (미확인)

| ID | 명세 | 확인할 내용 | 관련 |
| --- | --- | --- | --- |
| SPEC-60 | RFC 7519 §4.1.3 | aud의 기본 정의 (배열과 단일 문자열 표현) | T-20, D-X11 |
| SPEC-61 | RFC 7523 | JWT 고객사 인증의 jti 포함 여부와 서버 측 재전송 방지의 규범 수준 | T-01 |
| SPEC-62 | OpenID Connect Core 1.0 §9 | private_key_jwt의 jti 필수 여부와 1회 사용 요구의 규범 수준·적용 범위 | T-01 |
| SPEC-63 | RFC 8705 | mTLS 고객사 인증, 인증서 바인딩 Access Token, 리소스 서버 검증 요구 | T-22, T-36, T-37, T-38 |
| SPEC-64 | RFC 8446 | TLS 1.3 0-RTT Early Data의 재전송 특성 | T-28 |
| SPEC-65 | RFC 8470 | HTTP에서의 Early Data 처리 | T-28 |

Assertion jti 단일 사용은 명세 요구 수준(SPEC-61·62 확인 후 기록), 적용 범위, 프로젝트 자체 정책을 구분해 기록한다. 확인 전까지 현재 정책은 자체 정책이다.

---

## 2. Spring Security 소스 (7.2.0)

### 2.1 Client Assertion (private_key_jwt)

| ID | 위치 | 확인된 동작 | 공개 확장 지점 | 교체 시 유지할 검증 | 관련 |
| --- | --- | --- | --- | --- | --- |
| SRC-01 | [AS]authentication/JwtClientAssertionDecoderFactory.java `buildDecoder` (134 ~ 168행) | 서명 알고리즘이면 JWK Set URL이 없을 때 invalid_client로 실패한다. 대칭 알고리즘이면 Client Secret으로 검증한다 | `JwtClientAssertionAuthenticationProvider.setJwtDecoderFactory` (159행). 키 공급까지 교체 | SRC-02 전부, 고객사별 서명 알고리즘 고정 | T-24 |
| SRC-02 | 같은 파일 `defaultJwtValidatorFactory` (171 ~ 178행) | iss = client_id, sub = client_id, aud 검사, exp 존재, 시간 검증 | `setJwtValidatorFactory` (129행). Claim 검증만 교체 | iss·sub = client_id, exp 필수, 시간 검증 | T-10, T-20 |
| SRC-03 | 같은 파일 `containsAudience`, `getAudience` (181 ~ 214행) | 허용 목록은 issuer와 토큰·Introspection·폐기·PAR 엔드포인트 URL이다. aud 목록의 원소 중 하나라도 허용 목록에 있으면 통과한다 | SRC-02와 같음 | — | SPEC-01·02와 불일치: 엔드포인트 URL 수락, issuer 외 값을 포함한 배열 수락. 명세 갱신과 기본 구현의 차이이며 취약점으로 표현하지 않는다 (T-20) |
| SRC-04 | [JOSE]JwtTimestampValidator.java (54행) | 기본 허용 시계 오차 60초 | 생성자 인자 | — | T-40 |
| SRC-05 | JwtClientAssertionDecoderFactory.java (107 ~ 114행) | 고객사별 검증기를 등록 식별자 기준으로 프로세스 수명 동안 캐시한다 | 팩토리 교체 (SRC-01) | — | T-24 |
| SRC-06 | 같은 파일 (102 ~ 103행) | JWK Set 조회의 연결·읽기 타임아웃 각 15초 | 팩토리 교체 | — | T-24 |
| SRC-07 | 위 파일과 Provider | jti 단일 사용 검증이 없다 | SRC-02로 검증기 추가 가능 (판단). 다만 기록 시점이 고객사 인증 단계가 된다 | — | T-01, T-23 |
| SRC-42 | [JOSE]MappedJwtClaimSetConverter.java (108행), oauth2-core의 converter/ObjectToListStringConverter.java | aud에 컬렉션 문자열 변환기가 적용되고, 컬렉션이 아닌 값은 단일 원소 리스트로 변환된다. Spring Claim 단계에서는 문자열과 단일 원소 배열이 같은 리스트가 되어 구분할 수 없다 | `NimbusJwtDecoder.setClaimSetConverter` (127행), 토큰 원문의 페이로드 재해석 (판단) | — | T-20 |

미확인: Assertion용 검증기의 JWK Set 내부 캐시·갱신 주기, JWT 라이브러리 단계에서 aud 원래 표현의 보존 여부.

### 2.2 mTLS 고객사 인증

| ID | 위치 | 확인된 동작 | 공개 확장 지점 | 관련 |
| --- | --- | --- | --- | --- |
| SRC-08 | [AS]web/authentication/X509ClientCertificateAuthenticationConverter.java (54행 부근) | 서블릿 요청 속성 `jakarta.servlet.request.X509Certificate`에서 인증서를 취득한다 | — | T-36 |
| SRC-09 | [AS]authentication/X509ClientCertificateAuthenticationProvider.java (170 ~ 178행) | tls_client_auth는 등록된 주체 DN과 인증서 주체 이름의 문자열 완전 일치로 판단한다 | `setCertificateVerifier` (154행) | T-36 |
| SRC-10 | [AS]authentication/X509SelfSignedCertificateVerifier.java (65 ~ 225행) | 발급자와 주체가 같은지 확인하고(82 ~ 83행), JWK Set에서 인증서가 있는 키의 공개키와 바이트 비교한다(94행). JWK Set은 URL이 필수이고 고객사별로 보관하며(133행), 마지막 갱신 후 5분이 지나면 갱신하는 조건이 있다(221 ~ 224행). 타임아웃 15초(126 ~ 127행) | `setCertificateVerifier`로 교체 | T-24, T-36 |

5분 갱신 조건이 있다는 사실과 폐기 반영 지연의 상한이 5분이라는 보장은 구분한다. 조회 실패·타임아웃 시 동작, 이전 캐시의 유지 여부, 등록 URL 변경의 반영, 다중 인스턴스 간 반영 차이를 확인하기 전에는 상한을 확정하지 않는다. 긴급 폐기는 이 갱신만으로 충족한다고 가정하지 않는다 (D-B04, FR-AUTH-07).

미확인: 서블릿 컨테이너에서 CA 검증 없이 클라이언트 인증서를 요청하는 설정의 명칭과 동작.

### 2.3 client_credentials 처리

| ID | 위치 | 확인된 동작 | 공개 확장 지점 | 교체 시 유지할 검증 | 관련 |
| --- | --- | --- | --- | --- | --- |
| SRC-11 | [AS]authentication/OAuth2ClientCredentialsAuthenticationProvider.java | 검증기 호출(117행) 다음에 DPoP Proof가 있으면 검증(122행)한다. 토큰 형식과 무관하게 발급 정보를 저장한다(166행) | `setAuthenticationValidator` (196행) | `OAuth2ClientCredentialsAuthenticationValidator.DEFAULT_SCOPE_VALIDATOR` (공개 상수, 58행): 요청 Scope가 비어 있지 않으면 허용 Scope에 모두 포함돼야 한다(74행) | T-10, T-21, T-23, T-34 |

판단: Proof 원문은 인증 토큰의 추가 파라미터로 전달된다(SRC-13). 검증기 교체로 DPoP 필수화와 기본 Scope 검증 결합이 가능해 보이나, 검증기 문맥에서 해당 값에 접근하는 정확한 방법은 미확인이다.

### 2.4 DPoP Proof 검증

| ID | 위치 | 확인된 동작 | 공개 확장 지점 | 관련 |
| --- | --- | --- | --- | --- |
| SRC-12 | [JOSE]DPoPProofReplayValidator.java (공개 클래스) | iat가 현재 ± 허용 오차(기본 30초, 73행) 안이어야 한다. 기록 키는 jti의 SHA-256 해시만 사용한다. 만료 시각은 iat + 허용 오차다. 캐시의 putIfAbsent가 null이 아니면 실패한다(136행). 기본 메모리 캐시는 전체 10만 건, 키 지문당 1,000건, 10초 주기 정리(196 ~ 200행). Spring Cache 인터페이스를 받는다 | 생성자에 Cache 주입 | T-02 ~ T-04, T-11, T-40 |
| SRC-13 | [AS]authentication/DPoPProofVerifier.java | 패키지 전용 final 클래스이며 정적 팩토리(43행)로 기본 검증기를 만든다. Proof·메서드·대상 URI를 추가 파라미터 `dpop_proof`, `dpop_method`, `dpop_target_uri`에서 읽는다 | 없음 | T-05 |
| SRC-14 | [AS]web/authentication/OAuth2EndpointUtils.java (121행) | `dpop_target_uri`는 서블릿 요청 URL이다 | — | T-07 |
| SRC-15 | [JOSE]DPoPProofJwtDecoderFactory.java | typ 검증기가 있다. 알고리즘은 RSA·EC 계열만 허용한다(182행). 검증 순서는 사용자 검증기 → htm(대소문자 무시 비교) → htu(문자열 완전 일치) → iat(필수, 30초) → jkt·ath(Access Token이 있을 때) → 재전송이다. 첫 실패에서 중단하도록 설정된다 | `setJwtValidatorFactory` (96행), `createDefaultJwtValidatorFactory` (112행)에 재전송 검증기를 전달하면 기본 재전송 검증기를 대체 | T-07, T-10, T-12, T-35-b |
| SRC-16 | [CORE]DelegatingOAuth2TokenValidator.java (58 ~ 66행) | 실패 시 중단 옵션이 켜져 있으면 첫 실패에서 즉시 반환한다 | — | T-12 |

판단:
- SRC-15·16에 따라 리소스 서버에서 앞선 검증에 실패한 Proof는 재전송 검증기에 도달하지 않는다. 본문 무결성은 이 검증기 체인에 없으므로(SPEC-22) 별도 구조가 필요하다.
- SPEC-14의 정규화 권고와 달리 Spring은 htu를 문자열 완전 일치로 비교한다. 같은 URI의 다른 표기가 거부될 수 있는 상호운용 차이이며 보안 약화로 보지는 않는다.
- HTTP 메서드를 대소문자 무시로 비교하는 동작의 명세 적합성 판단은 미확정이다.
- 기록 키가 jti 해시뿐이라는 점이 보안상 문제가 없다고 단정하지 않는다. T-11에서 검증한다.

### 2.5 리소스 서버

| ID | 위치 | 확인된 동작 | 공개 확장 지점 | 관련 |
| --- | --- | --- | --- | --- |
| SRC-17 | [RS]introspection/OpaqueTokenIntrospector.java (46행) | `introspect(String token)`. 요청 객체를 받지 않는다 | 구현 교체 | T-38, D-X36 |
| SRC-18 | [RS]authentication/DPoPAuthenticationProvider.java | 토큰 인증 결과의 속성에서 cnf.jkt를 읽어 Proof를 검증한다 | `setDPoPProofVerifierFactory` (120행) | T-05 |
| SRC-19 | [CFG]configurers/oauth2/server/resource/OAuth2ResourceServerConfigurer.java (713행) | DSL `dPoPProofVerifierFactory(...)`가 있다. 7.1.1의 같은 파일에는 해당 문자열이 없다 | E1 | T-05 |
| SRC-20 | [RS]web/authentication/DPoPAuthenticationConverter.java (84행) | htu 비교 대상은 서블릿 요청 URL이다 | — | T-07 |
| SRC-21 | [RS]web/authentication/BearerTokenAuthenticationFilter.java (314 ~ 325행) | 토큰 속성의 cnf에 jkt가 있으면 DPoP 바인딩 토큰으로 판단한다 | — | SPEC-16, T-22 |
| SRC-22 | [RS] 모듈 검색 | 인증서 지문(x5t) 관련 코드를 찾지 못했다. 검색 범위는 리소스 서버 모듈이며, 지문 검증기는 JOSE 모듈에 있고 JWT 경로에서 쓰인다(SRC-24). 확인된 것은 "Opaque 경로에서 쓰이지 않음"까지다 | — | T-38 |

### 2.6 인증서 바인딩 토큰

| ID | 위치 | 확인된 동작 | 관련 |
| --- | --- | --- | --- |
| SRC-23 | [AS]settings/TokenSettings.java (122 ~ 130행), [CFG]configurers/oauth2/server/authorization/DefaultOAuth2TokenCustomizers.java (74 ~ 90행) | 인증서 바인딩 옵션은 tls_client_auth 또는 self_signed_tls_client_auth로 인증한 경우에만 cnf.x5t#S256을 넣는다. 커스터마이저는 JWT용과 Claim(Opaque)용이 모두 있다 | T-37 |
| SRC-24 | [JOSE]X509CertificateThumbprintValidator.java | 패키지 전용 클래스다. 요청 컨텍스트에서 인증서를 가져와 cnf.x5t#S256과 비교한다. **cnf가 없으면 통과한다** | T-22, T-38 |
| SRC-25 | [JOSE]JwtValidators.java (68 ~ 100행) | 기본 검증기 묶음이 SRC-24를 자동 포함한다 | T-10 |

발신자 제한 없는 토큰을 허용하지 않으므로(FR-AUTH-14) 지문 대조뿐 아니라 바인딩 정보가 없는 토큰의 거부를 별도로 보장해야 한다.

미확인: 사용자 정의 토큰 커스터마이저와 기본 커스터마이저의 결합 방식.

### 2.7 토큰 저장과 서명

| ID | 위치 | 확인된 동작 | 관련 |
| --- | --- | --- | --- |
| SRC-26 | oauth2-authorization-server의 리소스 `oauth2-authorization-schema.sql`, [AS]JdbcOAuth2AuthorizationService.java (874행) | Access Token 값 컬럼에 토큰 값을 저장하며 해시 처리 코드를 찾지 못했다 | T-34 |
| SRC-27 | [JOSE]NimbusJwtEncoder.java | 기본 헤더 RS256(104행). 같은 알고리즘의 키가 여럿이면 기본 선택기가 예외를 던진다(114 ~ 120행). `setJwkSelector`(166행) | T-35-a |
| SRC-28 | [CFG]configuration/OAuth2AuthorizationServerConfiguration.java `jwtDecoder` (65 ~ 71행) | RSA·EC·HMAC 계열을 모두 허용한다. 인가 서버 설정의 정적 도우미 메서드이며 실제 채택 구성에서 쓰이는지는 미확인 | T-35-a |

### 2.8 검색 결과가 없는 기능 (7.2.0, 테스트 제외)

검색 결과가 없다는 사실과 기능이 완전히 존재하지 않는다는 결론은 구분한다. 아래는 "기능 부재로 추정"이다.

| ID | 검색어 | 결과 | 관련 |
| --- | --- | --- | --- |
| SRC-30 | Signature-Input, Content-Digest | 0건 | T-08, T-09 |
| SRC-31 | DPoP-Nonce, use_dpop_nonce | 0건 | T-06 |
| SRC-32 | dpop_bound_access_tokens | 0건 | T-21 |

---

## 3. Spring Data Redis 소스 (4.2.0)

| ID | 위치 | 확인된 동작 | 관련 |
| --- | --- | --- | --- |
| SRC-40 | src/main/java/org/springframework/data/redis/cache/DefaultRedisCacheWriter.java `putIfAbsent` (382 ~ 418행) | TTL이 양수면 값과 만료를 한 번의 SET(NX + 만료)으로 기록한다. TTL이 양수가 아니면 만료 없는 SETNX를 쓴다. 삽입에 실패하면 GET으로 기존 값을 반환한다 | T-02, T-40 |
| SRC-41 | 같은 패키지 RedisCache.java (191 ~ 227행) | TTL은 키와 값을 받는 함수로 계산한다 | T-40 |

미검증 항목 (결함으로 단정하지 않는다):
- 일반 Cache의 putIfAbsent 의미가 "최초 삽입 성공 시에만 수락" 요구와 정확히 일치하는지
- SET NX 실패 후 GET 전에 키가 만료돼 GET이 null을 반환하는 경우, 삽입에 성공하지 않았는데 성공으로 해석될 가능성
- TTL 함수에 전달되는 키와 값만으로 증명의 마지막 수락 시점을 정확히 계산할 수 있는지
- 실제 사용할 spring-data-redis 버전과 위 동작의 동일성

---

## 4. 재확인·미확인 목록

관련 관문이나 기술 선택 전에 확인해야 하는 선행 조건으로 관리한다.

| 항목 | 상태 | 필요 시점 |
| --- | --- | --- |
| SPEC-30 ~ 33 (RFC 9421·9530 절 번호) | 재확인 | G6 착수 전 |
| SPEC-41 (FAPI의 문자열 aud) | 재확인 | D-X11 자체 강화 확정 전 |
| SPEC-42 ~ 45 (FAPI 최종본 원문·절 번호) | 재확인 | ADR 작성 전 |
| SPEC-50 ~ 52 (PostgreSQL 공식 사이트 원문) | 재확인 | G7 착수 전 |
| SPEC-55, SPEC-56 (Redis·PostgreSQL 지속성) | 미확인 | U-29 확정 전 |
| SPEC-60 (RFC 7519 aud 정의) | 미확인 | D-X11 자체 강화 확정 전 |
| SPEC-61, SPEC-62 (jti 요구 수준) | 미확인 | G4·G5 착수 전 |
| SPEC-63 (RFC 8705) | 미확인 | G3-a·G3-b 착수 전 |
| SPEC-64, SPEC-65 (0-RTT) | 미확인 | G1-a 착수 전 |
| Assertion 검증기의 JWK Set 캐시 | 미확인 | U-30 결정 전 |
| 자체 서명 검증기의 조회 실패·URL 변경 동작 | 미확인 | G2 |
| 서블릿 컨테이너의 클라이언트 인증서 설정 | 미확인 | G1-a, G2 착수 전 |
| 토큰 커스터마이저 결합 방식 | 미확인 | G4 |
| 검증기 문맥의 DPoP Proof 접근 | 미확인 | G5 |
| aud 원래 표현의 보존 | 미확인 | D-X11 자체 강화 채택 시 |
| 재전송 검증기 값 객체의 TTL 계산 접근 | 미확인 | G7 |
| 7.1.1 전체 비교 | 일부 파일만 비교 | U-07a 결정 시 |
