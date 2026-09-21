# #6701~#7100 합성 비구속적 조정 대안 시뮬레이션

## 목적

직전 정정안 비교·동의 충돌 검토 패킷을 입력으로 삼아 입주사, NURION PG, 본 PG 사이의 조정 대안을 조건·영향·잔여위험 관점에서 비교한다. 결과는 사람이 검토할 합성 자료일 뿐 권고, 동의, 결정 또는 승인이 아니다.

## 통제 구조

- 범위: #6701~#7100, 정확히 400개
- 구성: 16개 workstream × 25개 공통 통제 aspect
- 전자문서 흐름: 입주사→NURION, NURION→본 PG, 본 PG→NURION, NURION→입주사
- 비교 차원: 범위, 시점, 데이터 의미, 책임, 잔여위험
- 결과: 20개 합성 case와 20개 append-only hold

각 case는 발신 당사자의 문서, 흐름 route, 직전 case-set과 결속된 조건에서 영향과 잔여위험을 순차 파생한다. 외곽 digest만 다시 계산한 문서·역할·의미 치환은 전체 재계산 검증에서 거부한다.

## 계보와 역할분리

직전 패킷 digest, 세 source reviewer, 선행 compiler와 직전 compiler를 단일 source lineage digest로 결속한다. 최종 simulation packet에도 세 reviewer·두 compiler·source lineage digest를 직접 투영해 단독 이관 시 부분 계보가 되지 않게 한다. 새 simulation compiler는 이 다섯 주체와 모두 달라야 한다. 통제 registry key와 객체 control ID도 일치해야 한다.

## 상태 및 안전경계

최대 상태는 `NONBINDING_ALTERNATIVE_PACKET_READY_NOT_RECOMMENDED_NOT_DECIDED`이다. 시스템은 다음 능력을 제공하지 않는다.

- 실제 권고·동의·결정·승인·활성화
- 문서 전송·전자서명·외부 PG/API·카드망 호출
- 결제·취소·환불·정산·송금·원장 기록
- 운영 자격증명 접근·배포·운영 Prompt/정책/가중치 변경

모든 자료는 합성 데이터와 프로세스 메모리에만 존재한다. case 또는 hold가 하나라도 누락되거나 계보가 변조되면 완료 evidence는 fail-closed 된다.

## 아르카온 자가진단

초기 설계에서 신규 compiler를 source reviewer와만 분리하면 이전 두 compiler 중 하나가 다시 신규 역할로 등장할 수 있음을 확인했다. `source_compilers` 전체를 계보에 포함하고 다섯 source 주체 전체와 신규 compiler의 identity를 비교하도록 보완했으며, compiler 재사용·계보 치환 부정 테스트를 포함했다.
