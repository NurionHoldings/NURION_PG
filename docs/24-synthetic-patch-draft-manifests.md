# 합성 패치 초안 Manifest

## 목적

`AUTHORIZE_SYNTHETIC_PATCH_DRAFT`로 검증·수신된 합성 결정 의사에서 ARKAON이
사람 검토용 패치 초안 Manifest를 만든다. Manifest에는 허용된 초안 범위와
불투명한 대상 경로 SHA-256만 있으며 파일 경로 원문·코드·diff·실행 명령은 없다.

## 허용 범위

- `SYNTHETIC_FIXTURE_PATCH_DRAFT_ONLY`
- `TEST_HARDENING_PATCH_DRAFT_ONLY`
- `POLICY_CLARIFICATION_PATCH_DRAFT_ONLY`
- `DOCUMENTATION_PATCH_DRAFT_ONLY`

범위는 비어 있을 수 없고 허용목록 순서를 따라야 한다. 각 범위에는 중복되지
않는 64자리 소문자 SHA-256 대상 다이제스트 하나가 필요하다. 이 다이제스트는
대상을 결합하는 메타데이터일 뿐 패치 내용이나 파일 쓰기 지시가 아니다.

## 실패 폐쇄

- `HOLD`와 `REJECT` 수신증은 Manifest를 만들 수 없다.
- 원천 수신대장의 메타데이터·감사 사슬·레코드 결합을 모두 검증한다.
- 초안 시각은 수신증보다 빠를 수 없고 timezone을 포함해야 한다.
- 같은 수신증의 정확한 재전송만 멱등 처리한다.
- 범위·대상 다이제스트·원천 결합 변경은 충돌로 차단한다.
- Manifest ID와 append-only SHA-256 사슬을 매번 재계산한다.
- 원천 수신대장의 전후 증거 다이제스트가 달라지면 초안을 취소한다.

## 권한 경계

최대 상태는 `SYNTHETIC_PATCH_DRAFT_MANIFESTED`다. 에테르니언 재심사와 별도
합성 Patch Shadow 없이는 다음 단계로 갈 수 없다. 실제 패치 내용·diff 생성,
소스 또는 파일시스템 변경, 명령 실행, 네트워크·자격증명·개인정보 사용, 결제,
자금이동, 병합·배포·운영승격 기능은 없다.

## 검증

```bash
PYTHONPATH=src python -m unittest tests.test_synthetic_patch_draft_manifests -v
PYTHONPATH=src python scripts/run_synthetic_patch_draft_manifest_evidence.py
```

CI 통과는 실제 패치 작성·적용 또는 운영승격을 허가하지 않는다.
