"""架构约束：业务层必须零界面依赖。

用**子进程**跑，避免其他测试已经 import 过 tkinter 污染 ``sys.modules`` 而给出假绿。
这条约束靠测试强制，不靠人工 review。
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHECK_SCRIPT = r"""
import sys

# 业务层全部模块
import app.constants
import app.errors
import app.models
import app.loader
import app.pool
import app.allocation
import app.selection
import app.numbering
import app.generator
import app.docmodel
import app.history
import app.settings
import app.cli

# 输出层全部模块
import renderers.fonts
import renderers.pdf_renderer
import renderers.docx_renderer
import renderers.answer_card

banned = [m for m in ("tkinter", "webview") if m in sys.modules]
if banned:
    sys.stderr.write("业务层/输出层不应 import: %s\n" % ", ".join(banned))
    sys.exit(1)

# 界面层已彻底摆脱 tkinter（改用 pywebview）
import ui.api
import ui.jobs
import ui.dialogs
if "tkinter" in sys.modules:
    sys.stderr.write("界面层仍残留 tkinter 依赖\n")
    sys.exit(1)

print("CLEAN")
"""


def _run(script):
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_business_layer_imports_no_ui():
    proc = _run(CHECK_SCRIPT)
    assert proc.returncode == 0, (
        f"业务层引入了界面依赖：\n{proc.stdout}\n{proc.stderr}"
    )
    assert "CLEAN" in proc.stdout

