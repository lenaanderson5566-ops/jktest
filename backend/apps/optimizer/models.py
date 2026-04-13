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


class GlobalConfig(models.Model):
    config_key = models.CharField('配置项名称', max_length=64, unique=True)
    config_value = models.CharField('配置项值', max_length=255)
    enabled = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'global_config'
        verbose_name = '全局配置'
        verbose_name_plural = verbose_name
