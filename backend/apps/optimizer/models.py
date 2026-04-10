from django.db import models
from django.db.models import Value
from django.db.models.functions import Coalesce

from apps.masterdata.models import PackingStation


class OptimizeModeType(models.TextChoices):
    GLOBAL = 'GLOBAL', '全局'
    BY_ROUTE = 'BY_ROUTE', '分线路'


class OptimizeMode(models.Model):
    mode_no = models.CharField('模式编号', max_length=32, unique=True)
    mode_name = models.CharField('模式名称', max_length=128)
    mode_type = models.CharField('模式类型', max_length=16, choices=OptimizeModeType.choices)
    enabled = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'optimize_mode'
        verbose_name = '优化模式配置'
        verbose_name_plural = verbose_name


class ParameterCategory(models.TextChoices):
    TOTAL_TIME_WEIGHT = 'TOTAL_TIME_WEIGHT', '总耗时权重'
    STATION_SPAN_WEIGHT = 'STATION_SPAN_WEIGHT', '工位跨度权重'
    MANUAL_STATION_DURATION_WEIGHT = 'MANUAL_STATION_DURATION_WEIGHT', '人工工位时长权重'
    STATION_CONCENTRATION_WEIGHT = 'STATION_CONCENTRATION_WEIGHT', '特定工位集中权重'
    ROUTE_CONTINUITY_WEIGHT = 'ROUTE_CONTINUITY_WEIGHT', '线路连续性权重'


class OptimizeModeParameter(models.Model):
    mode = models.ForeignKey(OptimizeMode, on_delete=models.CASCADE, related_name='parameters', verbose_name='模式')
    category = models.CharField('参数类别', max_length=48, choices=ParameterCategory.choices)
    station = models.ForeignKey(PackingStation, null=True, blank=True, on_delete=models.CASCADE, related_name='mode_parameters', verbose_name='工位')
    value = models.DecimalField('参数值', max_digits=12, decimal_places=4)
    enabled = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'optimize_mode_parameter'
        verbose_name = '优化模式参数明细'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(fields=['mode', 'category', 'station'], name='uq_mode_category_station'),
            models.UniqueConstraint(
                Coalesce('station', Value(0)),
                'mode',
                'category',
                name='uq_mode_category_station_coalesced',
            ),
        ]


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


class GlobalConfig(models.Model):
    config_key = models.CharField('配置项名称', max_length=64, unique=True)
    config_value = models.CharField('配置项值', max_length=255)
    enabled = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'global_config'
        verbose_name = '全局配置'
        verbose_name_plural = verbose_name
