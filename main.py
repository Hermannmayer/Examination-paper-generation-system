"""考试试卷生成系统 —— 程序入口。

**这是一个本地单机小工具**：不部署、不联网、不监听任何端口。
界面用 HTML/CSS 绘制（pywebview 以 ``file://`` 从本地加载页面），
进程退出即结束。

明确传 ``http_server=False``：默认就是 False，写出来是为了把
"不监听端口"这个约束固化在代码里，避免日后被误改。
"""

from __future__ import annotations

import os
import sys

from app.constants import VERSION


def resource_path(*parts: str) -> str:
    """定位随程序分发的资源。

    打包后 ``__file__`` 指向临时解压目录，必须优先用 ``sys._MEIPASS``。
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, *parts)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)


def index_html_path() -> str:
    return resource_path("ui", "assets", "index.html")


def run_self_test(report_path: str) -> int:
    """打包环境的冒烟自检。

    存在的理由：``--exclude-module numpy`` 有可能在某条 openpyxl 冷路径上
    **运行时**才 import numpy —— 开发机上的单元测试跑不到，只有打包后才炸。
    而应用启动时并不会真的读 Excel（``import openpyxl`` 在函数内部），
    所以必须有一个真正走完「读题库 → 组卷 → 渲染三种格式」的自检，
    在**打包产物上**执行。

    用 ``EXAM_SELFTEST=<报告路径>`` 触发。
    """
    import tempfile
    import traceback

    lines = [f"考试试卷生成系统 v{VERSION} 打包自检", "=" * 46]
    status = 0

    def step(name, fn):
        nonlocal status
        try:
            detail = fn()
            lines.append(f"[通过] {name}" + (f" —— {detail}" if detail else ""))
        except BaseException as exc:  # noqa: BLE001 - 自检就是要抓全部
            status = 1
            lines.append(f"[失败] {name}: {exc.__class__.__name__}: {exc}")
            lines.append(traceback.format_exc())

    def skip(name, reason):
        """环境不具备条件时跳过 —— 不算失败。

        典型场景：CI 的 Windows Server 精简版没有中文宋体/黑体，
        此时 PDF 渲染无法验证，但那是环境属性，不是打包缺陷。
        """
        lines.append(f"[跳过] {name} —— {reason}")

    outdir = tempfile.mkdtemp(prefix="exampaper_selftest_")
    lines.append(f"输出目录: {outdir}")
    lines.append(f"资源根目录: {getattr(sys, '_MEIPASS', '(未打包)')}")
    lines.append("")

    state = {}

    def load_bank():
        from app.loader import load_question_bank
        from app.pool import QuestionPool

        path = resource_path("题库模板.xlsx")
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        state["pool"] = QuestionPool(load_question_bank(path))
        return f"{len(state['pool'])} 题 {state['pool'].count_by_type()}"

    def check_exclusions():
        """确认体积排除项真的生效。

        名单必须与 ``packaging/exam.spec`` 的 EXCLUDES 保持一致。
        注意 **不含 PIL** —— reportlab 硬依赖它，排不掉。

        开发机上这些包本来就装着，判定失败没有意义 —— 所以只在
        **打包产物**里执行这条断言。
        """
        import importlib.util

        wanted = ("numpy", "pandas", "tkinter", "matplotlib")
        found = [m for m in wanted if importlib.util.find_spec(m)]
        if not getattr(sys, "frozen", False):
            return f"（开发环境，跳过）当前存在于 venv: {found or '无'}"
        if found:
            raise AssertionError(f"这些模块本应被排除，却仍可导入: {found}")
        return "numpy / pandas / tkinter / matplotlib 均不存在"

    def generate_paper():
        from app.generator import generate
        from app.models import PaperConfig

        cfg = PaperConfig.from_legacy(
            {
                "export_mode": "随机抽取",
                "exam_title": "自检试卷",
                "include_judgment": True,
                "include_mcq": True,
                "include_mcq_multi": True,
                "include_short_answer": True,
                "judgment_count": 3,
                "mcq_count": 3,
                "mcq_multi_count": 2,
                "short_answer_count": 2,
                "judgment_score": 1,
                "mcq_score": 2,
                "mcq_multi_score": 3,
                "short_answer_score": 5,
                "include_answers": True,
            }
        )
        state["result"] = generate(cfg, state["pool"])
        state["cfg"] = cfg
        paper = state["result"].papers[0]
        return f"{paper.total_count} 题 / {paper.total_score} 分"

    def render_docx():
        from app.docmodel import build_paper_blocks
        from renderers.docx_renderer import render_docx

        path = os.path.join(outdir, "试卷.docx")
        render_docx(
            build_paper_blocks(state["result"].papers[0], state["cfg"]),
            path,
            "A4",
            "",
        )
        return f"{os.path.getsize(path)} 字节"

    def render_pdf():
        from app.docmodel import build_paper_blocks
        from renderers.pdf_renderer import render_pdf

        path = os.path.join(outdir, "试卷.pdf")
        render_pdf(
            build_paper_blocks(state["result"].papers[0], state["cfg"]),
            path,
            "A4",
            "",
        )
        return f"{os.path.getsize(path)} 字节"

    def render_pdf_a3():
        from app.docmodel import build_paper_blocks
        from renderers.pdf_renderer import render_pdf

        path = os.path.join(outdir, "试卷-A3.pdf")
        render_pdf(
            build_paper_blocks(state["result"].papers[0], state["cfg"]),
            path,
            "A3",
            "",
        )
        return f"{os.path.getsize(path)} 字节"

    def render_card():
        from renderers.answer_card import build_answer_card_document
        from renderers.pdf_renderer import render_pdf

        path = os.path.join(outdir, "答题卡.pdf")
        render_pdf(
            build_answer_card_document(state["result"].papers, state["cfg"]),
            path,
            "A4",
            "",
        )
        return f"{os.path.getsize(path)} 字节"

    def check_fonts():
        from renderers.fonts import check_fonts, register_fonts

        info = check_fonts()
        if not info["cjk_ok"]:
            raise AssertionError(f"未找到中文字体: {info}")
        fonts = register_fonts()
        return f"{fonts.body} / {fonts.title}"

    def check_frontend():
        index = index_html_path()
        if not os.path.exists(index):
            raise FileNotFoundError(index)
        missing = []
        for rel in (
            "css/app.css",
            "js/bridge.js",
            "js/dom.js",
            "js/config.js",
            "js/preview.js",
            "js/app.js",
        ):
            if not os.path.exists(os.path.join(os.path.dirname(index), rel)):
                missing.append(rel)
        if missing:
            raise FileNotFoundError(f"前端资源缺失: {missing}")
        return "index.html + 6 个静态资源齐全"

    def fonts_available() -> bool:
        """不抛异常的字体探测。"""
        from renderers.fonts import check_fonts

        return bool(check_fonts().get("cjk_ok"))

    step("排除项生效", check_exclusions)
    step("定位前端资源", check_frontend)
    step("读取题库（openpyxl）", load_bank)
    step("组卷", generate_paper)
    step("渲染 Word", render_docx)

    # PDF 依赖系统中文字体。CI 的 Windows Server 精简版常常没有宋体/黑体，
    # 那是环境属性不是打包缺陷 —— 跳过并说清楚，不判失败。
    if fonts_available():
        step("注册中文字体", check_fonts)
        step("渲染 PDF (A4)", render_pdf)
        step("渲染 PDF (A3 拼版)", render_pdf_a3)
        step("渲染答题卡", render_card)
    else:
        reason = "系统未安装中文宋体/黑体/微软雅黑（CI 的 Windows Server 常见）"
        for name in ("注册中文字体", "渲染 PDF (A4)", "渲染 PDF (A3 拼版)", "渲染答题卡"):
            skip(name, reason)

    lines.append("")
    lines.append("结论: " + ("全部通过" if status == 0 else "存在失败项"))

    report = "\n".join(lines)
    try:
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(report)
    except OSError:
        pass
    if sys.stdout is not None:
        try:
            print(report)
        except Exception:
            pass
    return status


def run_ui_self_test(window, report_path: str) -> int:
    """界面层自检：在**真实 WebView2 + file://** 里驱动一遍前端。

    为什么需要它：``run_self_test`` 只覆盖后端。而前端有一类只有真实运行
    环境才暴露的问题 —— file:// 下 Chromium 不允许 ``<script type="module">``、
    ``new Worker(file://...)`` 会被拒绝（pdf.js 必须能降级到主线程假 worker）。
    这些在 http:// 的浏览器里测不出来。

    用 ``EXAM_UI_SELFTEST=<报告路径>`` 触发，跑完自动关窗退出。
    """
    import json
    import threading
    import time

    report = []

    def js(code):
        try:
            return window.evaluate_js(code)
        except Exception as exc:  # noqa: BLE001
            return f"<JS 异常: {exc}>"

    def wait_for(expression, timeout):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if window.evaluate_js(expression):
                    return True
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.3)
        return False

    def probe():
        try:
            if not wait_for("!!(window.App && window.App.bridge)", 30):
                report.append(("页面初始化", False, "App / bridge 未就绪"))
                return

            report.append(("页面初始化", True, ""))

            pdfjs = js("typeof window.pdfjsLib")
            report.append(("pdf.js 已加载", pdfjs == "object", f"typeof = {pdfjs}"))

            # 走**真实界面路径**：点「示例」按钮。
            # 直接调 load_bundled_template 会跳过 applyBankInfo，
            # 题型数量框仍是空的，预览就会被校验拦下 —— 那是探针的错，不是应用的错。
            js("document.getElementById('btnTemplateBank').click(); true;")
            if not wait_for(
                "document.getElementById('bankInfo').textContent.indexOf('共') >= 0", 40
            ):
                report.append(
                    ("加载示例题库", False, js("document.getElementById('bankInfo').textContent"))
                )
                return
            report.append(
                ("加载示例题库", True, js("document.getElementById('bankInfo').textContent"))
            )

            js("""
                window.__probe = { state: 'running' };
                (async function () {
                  try {
                    // 先直接问一次后端，把返回结构记下来 ——
                    // 页面渲染不出来时，这样才能区分「后端没给 PDF」还是「前端没画出来」
                    var reply = await App.bridge.call('preview', App.config.read());
                    window.__probe.hasPdf = !!(reply.data && reply.data.pdf_base64);
                    window.__probe.pdfLength = reply.data && reply.data.pdf_base64
                      ? reply.data.pdf_base64.length : 0;
                    window.__probe.warnings = (reply.warnings || []).map(function (w) {
                      return w.code + ': ' + w.message;
                    });

                    await App.preview.refresh();
                    window.__probe.state = 'done';
                  } catch (e) {
                    window.__probe = { state: 'error', message: String(e),
                                       code: e && e.code ? e.code : null };
                  }
                })();
                true;
            """)

            if not wait_for("window.__probe && window.__probe.state !== 'running'", 60):
                report.append(("预览渲染", False, "超时"))
                return

            final = json.loads(js("JSON.stringify(window.__probe)"))
            if final.get("state") == "error":
                report.append(("预览渲染", False, final.get("message", "")))
                return

            report.append(
                (
                    "后端返回 PDF",
                    bool(final.get("hasPdf")),
                    f"{final.get('pdfLength', 0)} 字符"
                    + (
                        "；警告=" + "; ".join(final.get("warnings") or [])
                        if final.get("warnings")
                        else ""
                    ),
                )
            )

            pages = js("document.querySelectorAll('.page').length") or 0
            report.append(("预览渲染出页面", pages > 0, f"{pages} 页"))

            canvas = js(
                "JSON.stringify((function(){var c=document.querySelector('.page-canvas');"
                "return c ? [c.width, c.height] : null;})())"
            )
            report.append(
                ("页面画布已绘制", canvas not in (None, "null", "[]"), f"尺寸 = {canvas}")
            )

            fell_back = js("document.getElementById('previewFallback').hidden === false")
            report.append(
                (
                    "未退化到系统查看器",
                    not fell_back,
                    "已降级，说明 pdf.js 在 file:// 下不可用" if fell_back else "",
                )
            )

            stat = js("document.getElementById('statLine').textContent")
            report.append(("统计行有内容", bool(stat) and stat != "—", str(stat)))

            module_used = js(
                "Array.prototype.slice.call(document.scripts).some(function(s){"
                "return s.type === 'module';})"
            )
            report.append(("未使用 ES module", not module_used, ""))
        finally:
            # 先落盘再关窗：关窗后进程可能立刻退出，报告就写不上了
            _write_ui_report(report, report_path)
            window.destroy()

    # 探针线程跑完会调 window.destroy()，从而结束 webview 事件循环。
    # 这里不阻塞 —— 事件循环由调用方的 webview.start() 驱动。
    threading.Thread(target=probe, daemon=True).start()
    return 0


def _write_ui_report(report, report_path: str) -> None:
    lines = ["考试试卷生成系统 界面自检（真实 WebView2 + file://）", "=" * 46]
    failed = 0
    for name, passed, detail in report:
        if not passed:
            failed += 1
        mark = "通过" if passed else "失败"
        lines.append(f"[{mark}] {name}" + (f" —— {detail}" if detail else ""))
    lines.append("")
    lines.append("结论: " + ("全部通过" if failed == 0 else f"{failed} 项失败"))

    text = "\n".join(lines)
    try:
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(text)
    except OSError:
        pass
    if sys.stdout is not None:
        try:
            print(text)
        except Exception:
            pass


def main() -> int:
    self_test = os.environ.get("EXAM_SELFTEST")
    if self_test:
        return run_self_test(self_test)

    import webview

    # 延后导入：app 层不依赖 webview，这里才需要
    from app import settings as settings_store
    from ui.api import Api

    saved = settings_store.load()
    width = int(saved.get("window_width") or 1280)
    height = int(saved.get("window_height") or 860)

    api = Api()
    window = webview.create_window(
        title=f"考试试卷生成系统 v{VERSION}",
        url=index_html_path(),
        js_api=api,
        width=width,
        height=height,
        min_size=(900, 620),
        background_color="#0a0a0a",
        text_select=True,
    )
    api.attach_window(window)

    print(f"考试试卷生成系统 v{VERSION}  Copyright (C) 2026 Hermannmayer")
    print("本程序是自由软件，遵循 GNU 通用公共许可证第 3 版（或更新版本）。")
    print("你可以自由分发和/或修改它；但**衍生作品必须同样以 GPL 开源**。")
    print("本程序不提供任何担保。详见随附的 LICENSE 文件。")

    ui_self_test = os.environ.get("EXAM_UI_SELFTEST")
    if ui_self_test:
        # 界面自检：跑完会自己关窗，随后 webview.start 返回
        run_ui_self_test(window, ui_self_test)

    debug = os.environ.get("EXAM_DEBUG") == "1"
    # http_server 保持 False：页面以 file:// 加载，不开任何监听端口
    webview.start(http_server=False, debug=debug)

    try:
        settings_store.save({"window_width": width, "window_height": height})
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
