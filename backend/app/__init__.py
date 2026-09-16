"""ERP 백엔드 앱 패키지.

패키지가 처음 import 될 때(= FastAPI 기동 시) repo 루트의 `.env`를 읽어
`os.getenv(...)`로 어디서든 환경변수를 쓸 수 있게 한다.

- `override=False`: 이미 설정된 환경변수(예: docker-compose `env_file`, 셸 export)를
  덮어쓰지 않는다. 로컬 `.venv` 실행에서는 `.env`가 비어있던 os.environ을 채우고,
  컨테이너에서는 env_file이 주입한 값이 그대로 우선한다.
"""
from pathlib import Path

from dotenv import load_dotenv

# backend/app/__init__.py → parents[2] == repo 루트
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_ENV_PATH, override=False)
