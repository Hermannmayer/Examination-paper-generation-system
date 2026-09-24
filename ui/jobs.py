"""长任务管理：工作线程 + 进度 + 取消。

pywebview 会把 js_api 调用派发到工作线程，所以一个耗时函数**不会**卡住界面 ——
但它也不会提前返回，前端拿不到进度。因此长任务（生成 10 份卷并导出）
走"立即返回 job_id + 前端轮询"的模型。

选轮询而不是 ``evaluate_js`` 推送：推送依赖窗口就绪时机，脆弱；
轮询简单、天然线程安全、还能中途取消。
"""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from app.errors import CancelledByUser, DomainError

PENDING = "pending"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"

TERMINAL_STATES = {DONE, FAILED, CANCELLED}

# 已结束的任务保留多久（秒）后清理
RETENTION_SECONDS = 600


@dataclass
class Job:
    id: str
    kind: str
    state: str = PENDING
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: Optional[Dict] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    thread: Optional[threading.Thread] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.id,
            "kind": self.kind,
            "state": self.state,
            "progress": round(self.progress, 4),
            "message": self.message,
            "done": self.state in TERMINAL_STATES,
            "cancelled": self.state == CANCELLED,
            "result": self.result,
            "error": self.error,
            "elapsed_ms": int(
                ((self.finished_at or time.time()) - self.started_at) * 1000
            ),
        }


class JobManager:
    """线程安全的 job 表。"""

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.RLock()

    def start(self, kind: str, fn: Callable) -> str:
        """启动一个后台任务。

        ``fn(progress, cancel_event)``；``progress(fraction, message)``
        由任务主动调用以汇报进度。
        """
        job = Job(id=uuid.uuid4().hex[:12], kind=kind)
        with self._lock:
            self._jobs[job.id] = job
            self._prune_locked()

        def runner():
            with self._lock:
                job.state = RUNNING
            try:
                job.result = fn(
                    lambda fraction, message="": self._report(job, fraction, message),
                    job.cancel_event,
                )
                with self._lock:
                    job.state = CANCELLED if job.cancel_event.is_set() else DONE
                    job.progress = 1.0
            except CancelledByUser:
                with self._lock:
                    job.state = CANCELLED
                    job.message = "已取消"
            except DomainError as error:
                with self._lock:
                    job.state = FAILED
                    job.error = error.to_dict()
            except BaseException as exc:  # 未预期异常也要变成结构化结果，不能让线程静默死掉
                with self._lock:
                    job.state = FAILED
                    job.error = {
                        "code": "INTERNAL",
                        "message": str(exc),
                        "hint": "",
                        "details": {"traceback": traceback.format_exc()[-2000:]},
                    }
            finally:
                with self._lock:
                    job.finished_at = time.time()

        job.thread = threading.Thread(
            target=runner, name=f"job-{kind}-{job.id}", daemon=True
        )
        job.thread.start()
        return job.id

    def _report(self, job: Job, fraction: float, message: str) -> None:
        with self._lock:
            job.progress = max(0.0, min(1.0, float(fraction)))
            if message:
                job.message = message

    def get(self, job_id: str) -> Optional[Dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.to_dict() if job else None

    def list(self) -> List[Dict]:
        with self._lock:
            return [job.to_dict() for job in self._jobs.values()]

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state in TERMINAL_STATES:
                return False
            job.cancel_event.set()
            job.message = "正在取消…"
            return True

    def cancel_all(self) -> int:
        with self._lock:
            count = 0
            for job in self._jobs.values():
                if job.state not in TERMINAL_STATES:
                    job.cancel_event.set()
                    count += 1
            return count

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for job in self._jobs.values() if job.state not in TERMINAL_STATES)

    def _prune_locked(self) -> None:
        now = time.time()
        stale = [
            job_id
            for job_id, job in self._jobs.items()
            if job.finished_at and now - job.finished_at > RETENTION_SECONDS
        ]
        for job_id in stale:
            self._jobs.pop(job_id, None)


def check_cancelled(cancel_event: threading.Event) -> None:
    """在长循环里定期调用。"""
    if cancel_event is not None and cancel_event.is_set():
        raise CancelledByUser()
