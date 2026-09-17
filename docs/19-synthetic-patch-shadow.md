# 합성 패치 Shadow 평가

## 목적

`READY_FOR_SYNTHETIC_PATCH_SHADOW` 구현제안을 실제 코드나 파일로 생성하지 않고
합성 패치 메타데이터와 시험결과로만 평가한다. ARKAON은 범위별 fixture의
다이제스트와 통제 결과를 비교해 에테르니언 재심사 후보를 만들 수 있지만,
패치 내용 작성·적용 권한은 갖지 않는다.

## 범위별 fixture

각 구현제안 `draft_scope`마다 정확히 하나의 fixture가 필요하다. fixture는 다음을
SHA-256으로 고정한다.

- 제안 ID·제안 다이제스트·초안 범위
- 기준 스냅숏과 후보 패치 메타데이터 다이제스트
- 합성 입력 사용 및 예상 변화 관찰 여부
- 실패 폐쇄 기준·회귀시험·동시성/장애시험 통과 여부
- 증거 재현 및 에테르니언 심사 유지 여부
- 코드·파일·네트워크·운영환경·자격증명·개인정보·자금 사용 여부

기준과 후보 다이제스트가 같거나 필수 통제가 부족하면 `HUMAN_REVIEW`다. 금지된
부작용이 하나라도 관찰되면 `BLOCKED`다. 전부 통과한 경우에만
`PROPOSED_FOR_ETERNIAN_REVIEW`가 된다.

## 권한 경계

평가물에는 패치 내용이 없다. 파일 쓰기, 코드 변경, 네트워크 접근, 운영 접근,
자동 적용, 기준 완화, 실제 데이터·자격증명 사용, 결제·자금이동, 병합·배포,
운영승격 메서드를 제공하지 않는다. 통과 결과도 재심사 후보일 뿐 승인이나
변경 허가가 아니다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_patch_shadow -v
PYTHONPATH=src python scripts/run_synthetic_patch_shadow_evidence.py
```
