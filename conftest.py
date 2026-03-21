"""Root conftest.py — ensure core/ and domains/ are on sys.path.

pytest가 테스트 모듈을 수집하기 전에 core/와 domains/를 sys.path에 추가하여
kg.* 및 maritime.* 패키지를 올바르게 해석할 수 있도록 한다.
"""
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent
for _subdir in ("core", "domains"):
    _path = str(_repo_root / _subdir)
    if _path not in sys.path:
        sys.path.insert(0, _path)
