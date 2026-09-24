"""历史记录测试。

历史文件是用户可触碰的外部状态，必须：原子写入、损坏不崩、可查可清。
"""

import json
from datetime import datetime

import pytest

from app import history as history_module


@pytest.fixture
def hist(tmp_path, monkeypatch):
    """把历史文件重定向到临时目录，避免污染真实 %APPDATA%。"""
    path = tmp_path / "history.json"
    monkeypatch.setenv("EXAM_HISTORY_PATH", str(path))
    return path


def test_record_and_used_qids_round_trip(hist):
    assert not hist.exists()

    history_module.record("期末试卷", 3, 12345, ["q1", "q2", "q3"])
    assert history_module.used_qids() == {"q1", "q2", "q3"}

    history_module.record("补考试卷", 1, 999, ["q3", "q4"])
    assert history_module.used_qids() == {"q1", "q2", "q3", "q4"}


def test_list_entries_newest_first(hist):
    base = datetime(2026, 3, 5, 10, 0, 0)
    history_module.record("第一份", 1, 1, ["a"], when=base)
    history_module.record("第二份", 2, 2, ["b"], when=base.replace(hour=11))

    listing = history_module.list_entries()
    assert listing["path"] == str(hist)
    assert [e["exam_title"] for e in listing["entries"]] == ["第二份", "第一份"]
    assert listing["entries"][0]["qid_count"] == 1


def test_clear(hist):
    history_module.record("x", 1, 1, ["a"])
    history_module.clear()
    assert history_module.used_qids() == set()
    assert history_module.load_entries() == []


def test_delete_by_id(hist):
    entry_a = history_module.record("甲", 1, 1, ["a"])
    history_module.record("乙", 1, 2, ["b"])

    assert history_module.delete([entry_a.id]) == 1
    assert [e["exam_title"] for e in history_module.load_entries()] == ["乙"]
    assert history_module.delete(["不存在"]) == 0


def test_ids_are_unique_even_with_a_coarse_clock(hist):
    """ID 不能依赖时钟精度。

    Windows 的计时器粒度可以粗到十几毫秒（CI runner、虚拟机尤甚），
    连续调用会拿到同一个微秒值。早先用时间戳做 ID，在 GitHub 的
    Windows runner 上必现重复 —— 删一条会连带删掉另一条。
    """
    entries = [
        history_module.record(f"卷{i}", 1, i, [f"q{i}"]) for i in range(50)
    ]
    ids = [entry.id for entry in entries]
    assert len(set(ids)) == len(ids), f"ID 出现重复：{len(ids) - len(set(ids))} 个"

    # 重复 ID 的后果：删一条会误删多条
    assert history_module.delete([ids[0]]) == 1
    assert len(history_module.load_entries()) == 49


def test_corrupt_file_does_not_crash(hist):
    hist.write_text("{ 这不是合法 JSON", encoding="utf-8")

    assert history_module.used_qids() == set()
    listing = history_module.list_entries()
    assert listing["entries"] == []
    assert listing["warnings"]
    assert listing["warnings"][0]["code"] == "HISTORY_CORRUPT"


def test_wrong_shape_does_not_crash(hist):
    hist.write_text(json.dumps({"unexpected": "shape"}), encoding="utf-8")
    assert history_module.used_qids() == set()


def test_missing_file_is_not_an_error(hist):
    assert not hist.exists()
    assert history_module.used_qids() == set()
    assert history_module.list_entries()["warnings"] == []


def test_write_is_atomic_no_leftover_temp_files(hist):
    history_module.record("x", 1, 1, ["a"])
    leftovers = [p.name for p in hist.parent.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_entries_are_capped(hist, monkeypatch):
    monkeypatch.setattr(history_module, "MAX_ENTRIES", 5)
    for i in range(12):
        history_module.record(f"卷{i}", 1, i, [f"q{i}"])
    assert len(history_module.load_entries()) == 5
