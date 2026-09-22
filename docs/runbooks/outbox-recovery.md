# Outbox recovery

오래된 unpublished event의 lease와 시도 횟수를 확인한다. 소유권이 만료된 항목만 재claim하고 소비자의 멱등키를 확인한다. DB 행을 직접 published 처리하지 않는다.
