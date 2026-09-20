# 합성 정정안 비교·동의 충돌·운영자 심의 준비도 (#6301~#6700)

이 계층은 입주사·NURION PG·본 PG 사이의 4방향 전자문서 흐름에서 정정안과 상대 제안을 합성 비교하고, 동의 범위·데이터 의미·역할 권한·부분 배치·계보 단절 충돌을 운영자 심의용 비실행 패킷으로 묶는다.

통제는 16개 작업군마다 25개 aspect를 고정해 정확히 400개다. 4개 흐름과 5개 충돌 주제의 조합 20개가 모두 있어야 패킷을 만들며 하나라도 빠지면 fail-closed 된다. 각 비교물은 원문, 발신·수신 당사자, 흐름, 주제, route, 이전 correction case set과 파생 digest로 결속된다.

모든 event와 hold는 append-only hash chain이다. 직전 packet compiler를 source anchor와 receipt lineage에 보존하며, 신규 packet compiler는 선행 reviewer들과 직전 compiler 모두로부터 분리된다. 패킷의 최대 상태는 `OPERATOR_CONFLICT_REVIEW_PACKET_READY_NOT_DECIDED_NOT_APPROVED`이며 동의·결정·승인·공개·활성화·배포를 기록하거나 수행하지 않는다.

구현은 합성 데이터와 메모리 구조만 사용한다. 실제 문서 전송, 전자서명, 외부 PG/API, 카드망, 금융 처리, 원장 쓰기, 운영 자격증명, 정책·Prompt·가중치 변경 기능은 없다.
