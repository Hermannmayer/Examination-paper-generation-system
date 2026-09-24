"""API 信封与契约测试。

这一层是 JS 与 Python 的唯一边界，最容易出的问题是「前端读了一个后端没返回的
字段」—— 界面上表现为显示 `undefined` / `?`，而单元测试完全看不见。
所以这里除了验信封形状，还固定断言前端依赖的字段确实存在。
"""

import json
import os
import time

import pytest

from app.errors import Codes, DomainError
from conftest import make_bank

# 一份能出卷的最小配置（至少要勾选一种题型并给出数量）
VALID_CONFIG = {
    "include_judgment": True,
    "include_mcq": True,
    "judgment_count": 5,
    "mcq_count": 5,
}


@pytest.fixture
def api(api_env, bank_path):
    from ui.api import Api

    instance = Api()
    instance.load_excel(str(bank_path))
    return instance


# ── 信封形状 ─────────────────────────────────────────────────────────

def test_success_envelope_shape(api_env):
    from ui.api import Api

    reply = Api().get_app_info()
    assert set(reply) == {"ok", "data", "warnings", "error"}
    assert reply["ok"] is True
    assert reply["error"] is None
    assert isinstance(reply["warnings"], list)


def test_domain_error_becomes_structured_error(api_env):
    from ui.api import Api

    reply = Api().preview({})  # 未加载题库
    assert reply["ok"] is False
    assert reply["data"] is None
    assert reply["error"]["code"] == Codes.NOT_LOADED
    assert reply["error"]["message"]


def test_unexpected_exception_does_not_propagate(api_env, monkeypatch):
    """未预期异常必须被收敛成 INTERNAL，绝不能抛穿到 JS 层。"""
    from ui import api as api_module

    instance = api_module.Api()

    def boom(*_args, **_kwargs):
        raise RuntimeError("模拟的内部崩溃")

    monkeypatch.setattr(api_module, "load_question_bank", boom)
    reply = instance.load_excel("whatever.xlsx")

    assert reply["ok"] is False
    assert reply["error"]["code"] == Codes.INTERNAL
    assert "模拟的内部崩溃" in reply["error"]["message"]


def test_envelope_is_json_serialisable(api):
    """pywebview 用 json.dumps 序列化返回值，不能含非法类型。"""
    for reply in (api.get_app_info(), api.get_bank_info(), api.preview({})):
        assert json.dumps(reply)


# ── 前端契约：字段必须齐全 ───────────────────────────────────────────

def test_bank_summary_has_every_field_the_frontend_reads(api):
    """前端 applyBankInfo / renderAvailability 读到的键，后端都必须给。"""
    bank = api.get_bank_info()["data"]

    required = {
        "source", "filename", "total",
        "counts_by_type",
        "difficulty_values", "difficulty_counts",
        "knowledge_values", "knowledge_counts",
    }
    missing = required - set(bank)
    assert not missing, f"题库摘要缺少前端依赖的字段：{sorted(missing)}"

    assert bank["total"] == 70
    assert bank["counts_by_type"]["判断题"] == 30
    # 用同一个题库生成的题目带难度/知识点时，计数必须与之对应
    for value in bank["difficulty_values"]:
        assert value in bank["difficulty_counts"]


def test_app_info_has_every_field_the_frontend_reads(api_env):
    from ui.api import Api

    info = Api().get_app_info()["data"]
    required = {
        "version", "question_types", "export_modes", "paper_sizes", "fonts",
        "history_path", "settings_path",
        "default_exam_title", "default_student_info",
    }
    assert not required - set(info)
    assert info["fonts"]["cjk_ok"] in (True, False)
    for field in ("key", "label", "score", "default"):
        assert field in info["question_types"][0]


def test_preview_has_every_field_the_frontend_reads(api):
    preview = api.preview(VALID_CONFIG)["data"]
    required = {"sections", "answer_groups", "total_count", "total_score", "stats"}
    assert not required - set(preview)

    section = preview["sections"][0]
    assert {"label", "per_score", "count", "points",
            "number_start", "number_end", "questions"} <= set(section)

    question = section["questions"][0]
    assert {"stem", "options"} <= set(question)
    assert preview["stats"]["by_type"]


def test_preview_answer_groups_only_when_requested(api):
    assert api.preview(VALID_CONFIG)["data"]["answer_groups"] == []

    config = dict(VALID_CONFIG, include_answers=True)
    with_answers = api.preview(config)["data"]
    assert with_answers["answer_groups"]
    assert with_answers["answer_groups"][0]["label"] == "全部"


# ── 取消 / 错误路径 ──────────────────────────────────────────────────

def test_cancel_save_reports_cancelled(api):
    """没有窗口时对话框返回 None —— 必须回传 cancelled，而不是假装成功。"""
    reply = api.save_template({})
    assert reply["ok"] is True
    assert reply["data"]["cancelled"] is True


def test_export_requires_output_dir(api):
    reply = api.start_export({}, {"docx": True, "output_dir": ""})
    assert reply["ok"] is False
    assert reply["error"]["code"] == Codes.FILE_NOT_FOUND


def test_export_requires_a_format(api, tmp_path):
    reply = api.start_export({}, {"output_dir": str(tmp_path)})
    assert reply["ok"] is False
    assert reply["error"]["code"] == Codes.UNSUPPORTED_FORMAT


def test_load_failure_does_not_replace_pool(api, tmp_path):
    before = api.get_bank_info()["data"]
    bad = make_bank(tmp_path / "bad.xlsx", omit_column="正确答案")

    reply = api.load_excel(str(bad))
    assert reply["ok"] is False
    assert reply["error"]["code"] == Codes.MISSING_COLUMNS

    after = api.get_bank_info()["data"]
    assert after["total"] == before["total"]
    assert after["source"] == before["source"]


# ── 长任务 ───────────────────────────────────────────────────────────

def _wait(job_id, api, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = api.get_job(job_id)["data"]
        if job["done"]:
            return job
        time.sleep(0.05)
    raise AssertionError("任务超时未结束")


def test_export_job_produces_all_formats(api, tmp_path):
    reply = api.start_export(
        {"include_judgment": True, "include_mcq": True, "judgment_count": 3,
         "mcq_count": 3, "exam_title": "契约测试"},
        {"docx": True, "pdf": True, "card": True, "card_docx": True,
         "output_dir": str(tmp_path)},
    )
    assert reply["ok"] is True
    job = _wait(reply["data"]["job_id"], api)

    assert job["state"] == "done", job.get("error")
    assert job["progress"] == 1.0

    names = sorted(os.path.basename(p) for p in job["result"]["files"])
    assert names == ["试卷-答题卡.docx", "试卷-答题卡.pdf", "试卷.docx", "试卷.pdf"]
    for path in job["result"]["files"]:
        assert os.path.getsize(path) > 0


def test_export_uses_custom_file_prefix(api, tmp_path):
    """文件名必须可由用户指定 —— 固定成「试卷」会让不同批次互相覆盖。"""
    reply = api.start_export(
        {"include_judgment": True, "judgment_count": 3, "exam_title": "命名测试"},
        {"docx": True, "card": True, "output_dir": str(tmp_path),
         "file_prefix": "三年级语文期末"},
    )
    job = _wait(reply["data"]["job_id"], api)

    names = sorted(os.path.basename(p) for p in job["result"]["files"])
    assert names == ["三年级语文期末-答题卡.pdf", "三年级语文期末.docx"]


def test_export_numbers_multiple_papers(api, tmp_path):
    reply = api.start_export(
        {"include_judgment": True, "judgment_count": 3},
        {"docx": True, "output_dir": str(tmp_path), "exam_count": 3,
         "file_prefix": "多份"},
    )
    job = _wait(reply["data"]["job_id"], api)

    names = sorted(os.path.basename(p) for p in job["result"]["files"])
    assert names == ["多份-1.docx", "多份-2.docx", "多份-3.docx"]


def test_file_prefix_strips_illegal_characters(api, tmp_path):
    """Windows 不允许 \\ / : * ? " < > |，必须清洗掉，否则写文件会失败。"""
    reply = api.start_export(
        {"include_judgment": True, "judgment_count": 3},
        {"docx": True, "output_dir": str(tmp_path),
         "file_prefix": 'a/b\\c:d*e?f"g<h>i|j'},
    )
    job = _wait(reply["data"]["job_id"], api)

    name = os.path.basename(job["result"]["files"][0])
    assert name == "abcdefghij.docx", name


def test_file_prefix_falls_back_when_blank(api, tmp_path):
    reply = api.start_export(
        {"include_judgment": True, "judgment_count": 3},
        {"docx": True, "output_dir": str(tmp_path), "file_prefix": "   "},
    )
    job = _wait(reply["data"]["job_id"], api)
    assert os.path.basename(job["result"]["files"][0]) == "试卷.docx"


def test_export_job_reports_unknown_id(api):
    reply = api.get_job("不存在的任务")
    assert reply["ok"] is False
    assert reply["error"]["code"] == Codes.NOT_LOADED


def test_cancel_unknown_job_is_false(api):
    assert api.cancel_job("nope")["data"]["cancelling"] is False


def test_export_records_history(api, tmp_path):
    from app import history as history_store

    api.start_export(
        {"include_judgment": True, "judgment_count": 3, "exam_title": "历史测试"},
        {"docx": True, "output_dir": str(tmp_path)},
    )
    deadline = time.time() + 30
    while time.time() < deadline and not history_store.load_entries():
        time.sleep(0.05)

    entries = history_store.load_entries()
    assert entries, "导出后应记录历史"
    assert entries[-1]["exam_title"] == "历史测试"
    assert history_store.used_qids(), "历史里应存下本次用过的题"


# ── 设置 ─────────────────────────────────────────────────────────────

def test_settings_round_trip(api_env):
    from ui.api import Api

    instance = Api()
    saved = instance.save_settings({"paper_size": "A3", "export_card_docx": True})
    assert saved["ok"] is True

    loaded = instance.load_settings()["data"]
    assert loaded["paper_size"] == "A3"
    assert loaded["export_card_docx"] is True
    # 未提供的键应保留默认值
    assert "export_docx" in loaded


def test_reroll_returns_different_seeds(api):
    seeds = {api.reroll()["data"]["seed"] for _ in range(20)}
    assert len(seeds) > 1, "重新抽题应给出不同的种子"


def test_open_path_rejects_missing_file(api, tmp_path):
    reply = api.open_path(str(tmp_path / "不存在.txt"))
    assert reply["ok"] is False
    assert reply["error"]["code"] == Codes.FILE_NOT_FOUND
