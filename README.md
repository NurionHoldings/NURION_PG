# NURION PG

누리온PG의 결제·정산 기반과 ARKAON 통제형 개발 체계를 위한 저장소입니다.

현재 단계는 `UNREGISTERED_SYNTHETIC_ONLY`입니다. 실제 결제, 승인, 취소, 환불,
송금, 정산, 가맹점 승인, 계약 체결, 운영 자격증명 접근 및 배포를 수행하지 않습니다.

## 최초 기능 묶음

- ARKAON 능력 프로필과 권한 경계
- `Baseline → Proposal → Synthetic Shadow → 에테르니언 심사 → 운영자 승인 → 제한 승격 → Rollback`
- 공식 근거의 출처·조회일·유효기간·SHA-256 고정
- 인터넷 자료를 비신뢰 입력으로 취급
- append-only SHA-256 증거 사슬
- 합성 데이터 전용 벤치마크와 GitHub CI
- 규제·금융기관·보안·정산 외부 차단조건의 실패 폐쇄
- 공식 규제근거 Registry와 상충·만료·미완전 근거 차단
- 균형·멱등·불변성을 강제하는 합성 원장 및 정산 계산
- 낙관적 버전·멱등 명령·원장 연결을 갖춘 합성 결제 생명주기

자세한 내용은 [ARKAON 통제형 부트스트랩](docs/01-arkaon-governed-bootstrap.md)을 참고합니다.

## 로컬 검증

```bash
python -m unittest discover -s tests -v
PYTHONPATH=src python scripts/validate_governance.py
PYTHONPATH=src python scripts/run_bootstrap_evidence.py
```

CI 성공은 등록, 계약, 운영승인, 병합 또는 배포 승인을 의미하지 않습니다.

규제 Registry에 기록된 내용은 설계 초안의 근거일 뿐 법률자문이나 운영승인이 아닙니다.
