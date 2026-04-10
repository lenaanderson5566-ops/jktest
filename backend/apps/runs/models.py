from django.db import models

from apps.masterdata.models import Organization, PackingStation, TransportRoute
from apps.optimizer.models import OptimizeMode
from apps.orders.models import OrganizationOrder


class RunResultSummary(models.Model):
    batch_no = models.CharField('运行批次号', max_length=64, unique=True)
    run_at = models.DateTimeField('运行日期时间', auto_now_add=True)
    optimize_mode = models.ForeignKey(OptimizeMode, on_delete=models.PROTECT, related_name='run_summaries', verbose_name='优化模式')
    total_seconds = models.DecimalField('运行总耗时(秒)', max_digits=12, decimal_places=2)
    score = models.DecimalField('综合评分', max_digits=12, decimal_places=4)
    is_best = models.BooleanField('是否最优方案', default=False)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'run_result_summary'
        verbose_name = '排序运行结果主评估'
        verbose_name_plural = verbose_name


class RunResultStationDetail(models.Model):
    batch = models.ForeignKey(RunResultSummary, on_delete=models.CASCADE, related_name='station_details', verbose_name='运行批次')
    station = models.ForeignKey(PackingStation, on_delete=models.PROTECT, related_name='run_details', verbose_name='工位')
    station_span = models.DecimalField('工位跨度', max_digits=12, decimal_places=2)
    busy_seconds = models.DecimalField('工位忙碌时长(秒)', max_digits=12, decimal_places=2)
    idle_seconds = models.DecimalField('工位空闲时长(秒)', max_digits=12, decimal_places=2)
    wait_seconds = models.DecimalField('工位等待时长(秒)', max_digits=12, decimal_places=2)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'run_result_station_detail'
        verbose_name = '排序运行结果工位评估明细'
        verbose_name_plural = verbose_name
        unique_together = ('batch', 'station')


class SortedOrderResult(models.Model):
    batch = models.ForeignKey(RunResultSummary, on_delete=models.CASCADE, related_name='sorted_orders', verbose_name='运行批次')
    seq_no = models.PositiveIntegerField('排序序号')
    order = models.ForeignKey(OrganizationOrder, on_delete=models.PROTECT, related_name='sorted_results', verbose_name='订单')
    order_date = models.DateField('订单日期')
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='sorted_results', verbose_name='机构')
    route = models.ForeignKey(TransportRoute, on_delete=models.PROTECT, related_name='sorted_results', verbose_name='线路')
    final_position = models.PositiveIntegerField('最终排序位置')
    est_start_time = models.DateTimeField('预计开始时间')
    est_finish_time = models.DateTimeField('预计完成时间')
    est_total_seconds = models.DecimalField('预计总处理时长(秒)', max_digits=12, decimal_places=2)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'sorted_order_result'
        verbose_name = '排序结果'
        verbose_name_plural = verbose_name
        unique_together = ('batch', 'seq_no')
        indexes = [models.Index(fields=['order_date', 'route'])]
