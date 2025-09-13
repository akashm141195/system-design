import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .settings import settings


@dataclass
class Job:
    id: str
    payload: Dict[str, Any]
    status: str = "queued"  # queued -> processing -> done / failed
    result: Optional[Any] = None
    error: Optional[str] = None


class InMemoryJobQueue:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[Job] = asyncio.Queue()
        self.jobs: Dict[str, Job] = {}
        self._workers: list[asyncio.Task] = []
        self._shutdown = asyncio.Event()

    async def start(self) -> None:
        for _ in range(max(1, settings.queue_worker_concurrency)):
            self._workers.append(asyncio.create_task(self._worker()))

    async def stop(self) -> None:
        self._shutdown.set()
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)

    async def _worker(self) -> None:
        while not self._shutdown.is_set():
            try:
                job = await self.queue.get()
            except asyncio.CancelledError:
                break
            try:
                job.status = "processing"
                await asyncio.sleep(0.5)  # simulate work
                # demo "processing": return the sum of numeric fields
                result_sum = sum(v for v in job.payload.values() if isinstance(v, (int, float)))
                job.result = {"sum": result_sum}
                job.status = "done"
            except Exception as exc:  # pragma: no cover - demo error path
                job.status = "failed"
                job.error = str(exc)
            finally:
                self.queue.task_done()

    async def enqueue(self, payload: Dict[str, Any]) -> Job:
        job = Job(id=str(uuid.uuid4()), payload=payload)
        self.jobs[job.id] = job
        await self.queue.put(job)
        return job

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        return {
            job_id: {
                "status": job.status,
                "result": job.result,
                "error": job.error,
            }
            for job_id, job in self.jobs.items()
        }


job_queue = InMemoryJobQueue()
