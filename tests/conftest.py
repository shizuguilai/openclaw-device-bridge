import sys
from pathlib import Path

# 保证 `client.*`、`relay.*`、`shared.*` 可从仓库根导入
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
