# Alembic 마이그레이션

이 프로젝트는 지금까지 `app/db/init_db.py`의 `Base.metadata.create_all()`로만 개발 DB
스키마를 관리해왔다. `create_all()`은 "테이블이 없으면 만든다"만 할 뿐, 이미 있는
테이블에 컬럼을 추가/변경/삭제하는 것은 추적하지 못한다. 그래서 로컬 SQLite를 지우고
새로 만드는 동안에는 문제가 없었지만, 실제 운영 DB(Render의 Postgres 등)로 넘어가면
스키마를 안전하게 바꿀 방법이 없었다.

## 최초 1회 필요한 작업 (사람이 직접 실행해야 함)

이 세션(Claude)은 사용자 PC에서 셸 명령을 실행할 수 없어서, `alembic.ini`/`alembic/env.py`
배선까지만 만들어두고 실제 "현재 모델 상태를 담은 첫 마이그레이션 파일"은 만들지
못했다. 아래를 backend/ 디렉터리에서 **직접** 실행해야 한다.

```bash
cd backend
pip install -r requirements.txt   # alembic이 새로 추가됐으므로 재설치 필요
alembic revision --autogenerate -m "initial schema"
```

이렇게 생성된 `alembic/versions/xxxx_initial_schema.py` 파일을 열어 실제로 지금 모델
구조와 일치하는 내용인지 한 번 확인해보는 것을 권장한다 (autogenerate가 인덱스/기본값
등 일부는 놓칠 수 있음 - Alembic 공식 문서에서도 항상 안내하는 주의사항).

이미 stock_platform.db가 만들어져 있는 개발 환경(지금 상태)에서는, 방금 만든 마이그레이션을
"이미 적용된 것"으로 표시만 하면 된다(실제로 다시 실행해 테이블을 또 만들 필요 없음):

```bash
alembic stamp head
```

## 이후 스키마를 바꿀 때

1. `app/models/*.py`에서 모델을 수정한다.
2. `alembic revision --autogenerate -m "설명"`으로 마이그레이션 파일을 생성한다.
3. 생성된 파일 내용을 검토한다.
4. `alembic upgrade head`로 적용한다.

`app/db/init_db.py`의 `create_all()`은 당분간 테스트/최초 세팅 편의용으로 남겨두지만,
스키마를 "바꾸는" 작업은 이제부터 Alembic 마이그레이션으로 해야 한다(그래야 운영 DB에도
같은 변경을 안전하게 반영할 수 있다).
