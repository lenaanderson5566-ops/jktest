from __future__ import annotations

from datetime import datetime
from threading import Thread
from uuid import uuid4

from django.db import close_old_connections
from django.utils import timezone

from apps.jobcenter.models import SortingJob, SortingJobStatus
from apps.optimizer.models import OptimizeMode
from apps.optimizer.services.sorter import run_sorting_for_date


def enqueue_sorting_job(order_date: str, mode_no: str | None = None) -> SortingJob:
    if isinstance(order_date, str):
        order_date = datetime.strptime(order_date, '%Y-%m-%d').date()

    job = SortingJob.objects.create(
        job_no=f'JOB-{timezone.now().strftime("%Y%m%d%H%M%S")}-{str(uuid4())[:8]}',
        order_date=order_date,
        status=SortingJobStatus.PENDING,
    )

    if mode_no:
        mode = OptimizeMode.objects.filter(mode_no=mode_no, enabled=True).first()
        if mode:
            job.mode = mode
            job.save(update_fields=['mode', 'updated_at'])
    return job


def _run_job(job_id: int):
    close_old_connections()
    job = SortingJob.objects.get(id=job_id)
    job.status = SortingJobStatus.RUNNING
    job.started_at = timezone.now()
    job.message = ''
    job.save(update_fields=['status', 'started_at', 'message', 'updated_at'])

    try:
        summary = run_sorting_for_date(job.order_date, job.mode.mode_no if job.mode else None)
        job.status = SortingJobStatus.SUCCESS
        job.result_batch_no = summary.batch_no
        job.message = f'排序完成: score={summary.score}'
    except Exception as exc:  # noqa: BLE001
        job.status = SortingJobStatus.FAILED
        job.message = str(exc)[:255]
    finally:
        job.finished_at = timezone.now()
        job.save(update_fields=['status', 'result_batch_no', 'message', 'finished_at', 'updated_at'])
        close_old_connections()


def start_sorting_job_in_background(job_id: int):
    t = Thread(target=_run_job, args=(job_id,), daemon=True)
    t.start()
