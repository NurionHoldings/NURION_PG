# ARKAON 감사 재발방지 지도사항

이 문서는 에테르니언 독립 감사에서 발견된 미비점을 아르카온의 반복실수 방지 지식으로 환류한다. 코드·검증기·테스트·증적 설계에만 적용하며 운영 Prompt, 가중치 또는 운영 정책을 자동 변경하지 않는다. 기계검증 원본은 [`config/arkaon-audit-recurrence-prevention.json`](../config/arkaon-audit-recurrence-prevention.json)이다.

에테르니언이 코드를 보완한 모든 경우에는 안정적인 remediation ID를 [`ethernian-remediation-manifest-v1.json`](../config/ethernian-remediation-manifest-v1.json)에 선언하고 [`arkaon-lesson-registry-v1.json`](../config/arkaon-lesson-registry-v1.json)에 대응 lesson을 추가해야 완료된다. 각 lesson은 발견 범위, 결함 분류, 근본 원인, 공격 시나리오, 강제 예방 규칙, 실제 저장소에 존재하는 필수 부정 테스트, 보완 reference, 아르카온 확인, 재검증 증적을 가진다. validator는 remediation과 lesson이 1:1로 대응하지 않거나 ack/test/evidence가 빠지면 fail-closed 한다. 커밋 SHA나 checkout 깊이에 의존하지 않으므로 로컬·GitHub CI·복제 환경에서 동일하게 작동한다. 모든 신규 단계는 구현 전에 누적 registry를 읽고 적용한 lesson ID와 registry digest를 해당 단계 evidence에 기록해야 한다.

## 구현 전 필수 절차

1. 모든 digest 필드에 의미 라벨, 권위 source type, canonical 재계산식을 정의한다.
2. 파생 산출물이 source dossier와 독립 review receipt에 직접 또는 검증 가능한 anchor로 결속되는지 확인한다.
3. case와 receipt는 최신 라운드에만 결속하고 current 판단을 호출자 값이 아닌 내부 계보에서 파생한다.
4. maker/author/assembler identity는 source artifact에서 파생하고 checker와 정규화 비교한다.
5. route·case set·artifact set 등 파생 digest는 evidence 시점에 원 입력으로 재계산한다.
6. 다자 협상은 version·operation·token class의 공통 capability 교집합만 사용한다.
7. event chain은 허용 action뿐 아니라 현재 도메인 상태에서 재구성한 실제 artifact digest와 대조한다.
8. `approval_recorded`, `release_recorded` 등 boolean과 최대 status는 생성 시와 사후 무결성에서 모두 검증한다.

## 공격 시나리오와 필수 부정 테스트

| 분류 | 공격 | 반드시 실패해야 하는 테스트 |
|---|---|---|
| 의미 결속 | 다른 의미의 유효 digest를 넣고 재해시 | 의미 라벨/source type 치환 |
| source 계보 | 동일 요청값으로 다른 dossier/receipt 재사용 | dossier·receipt 단독 치환 |
| 최신성 | stale round에 case/receipt 결속 | 이전 round ID 호출 |
| 역할분리 | 호출자가 maker identity 위조 | maker 대체·maker=checker |
| 파생값 | route 또는 derived digest 치환 | outer digest 재해시 포함 치환 |
| 공통능력 | 한 당사자 미지원 op/token 삽입 | profile 한 곳에서 capability 제거 |
| event 의미 | 허용 action에 다른 artifact 결속 | event artifact 치환 및 chain 재해시 |
| 안전상태 | 승인 boolean/status로 변경 | `true`/승인 상태 치환 및 재해시 |

## 완료 기준

- 8개 규칙 모두 코드의 생성 경로와 사후 `_integrity` 경로에서 적용된다.
- 각 규칙에 대응하는 부정 테스트가 존재하고 재해시 공격까지 포함한다.
- 부분 자료, stale 자료, 역할 충돌, 파생값 불일치는 fail-closed 한다.
- evidence는 안전 boolean/status와 외부 실행 수치 0을 최종 재확인한다.
- 정책 JSON validator, 전용 테스트, 전체 회귀, 결정론 evidence가 모두 통과해야 완료로 본다.
