from django.db import models

from apps.optimizer.models import OptimizeMode


class SortingJobStatus(models.TextChoices):
    PENDING = 'PENDING', '待执行'
    RUNNING = 'RUNNING', '运行中'
    SUCCESS = 'SUCCESS', '成功'
    FAILED = 'FAILED', '失败'


class SortingJob(models.Model):
    job_no = models.CharField('任务编号', max_length=64, unique=True, blank=True)
    order_date = models.DateField('订单日期')
    mode = models.ForeignKey(OptimizeMode, null=True, blank=True, on_delete=models.SET_NULL, related_name='sorting_jobs', verbose_name='优化模式')
    status = models.CharField('状态', max_length=16, choices=SortingJobStatus.choices, default=SortingJobStatus.PENDING)
    result_batch_no = models.CharField('结果批次号', max_length=64, blank=True)
    message = models.CharField('结果信息', max_length=255, blank=True)
    started_at = models.DateTimeField('开始时间', null=True, blank=True)
    finished_at = models.DateTimeField('完成时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'sorting_job'
        verbose_name = '排序计算任务'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['order_date', 'status']),
        ]
