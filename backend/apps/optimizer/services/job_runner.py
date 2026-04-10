"""兼容层：任务执行逻辑已迁移到 apps.jobcenter.services.job_runner。"""

from apps.jobcenter.services.job_runner import (  # noqa: F401
    enqueue_sorting_job,
    start_sorting_job_in_background,
)
