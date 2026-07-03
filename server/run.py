"""remote_agent_server 启动脚本。

在 server 根目录下运行：

    python run.py

等价于 `python -m src`，但无需进入 src 目录或使用模块语法，便于在 IDE 或
部署环境直接启动。

支持的环境变量（RAS_ 前缀，双下划线分隔层级）会覆盖 config.toml 中的同名字段，
例如：

    RAS_AUTH__token=my-token
    RAS_SERVER__port=9000

详见 `config.toml.example` 与 `src/utils/config.py`。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 将 src 目录加入搜索路径，使 `import src` 在脚本直接运行时也能生效。
_PROJECT_ROOT = Path(__file__).resolve().parent
_SRC_DIR = _PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from src.__main__ import main  # noqa: E402  位置必须在 sys.path 调整之后


if __name__ == "__main__":
    main()
