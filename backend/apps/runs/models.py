from django.db import models

from apps.masterdata.models import Organization, TransportRoute
from apps.optimizer.models import OptimizeMode
from apps.orders.models import OrganizationOrder


class SortedOrderResult(models.Model):
    batch_no = models.CharField('运行批次号', max_length=64, db_index=True)
    optimize_mode = models.ForeignKey(
        OptimizeMode,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='sorted_order_results',
        verbose_name='优化模式',
    )
    seq_no = models.PositiveIntegerField('排序序号')
    order = models.ForeignKey(OrganizationOrder, on_delete=models.PROTECT, related_name='sorted_results', verbose_name='订单')
    order_date = models.DateField('订单日期')
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='sorted_results', verbose_name='机构')
    route = models.ForeignKey(TransportRoute, on_delete=models.PROTECT, related_name='sorted_results', verbose_name='线路')
    final_position = models.PositiveIntegerField('最终排序位置')
    est_start_time = models.DateTimeField('预计开始时间')
    est_finish_time = models.DateTimeField('预计完成时间')
    est_total_seconds = models.DecimalField('预计累计完成时长(秒)', max_digits=12, decimal_places=2)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'sorted_order_result'
        verbose_name = '排序结果'
        verbose_name_plural = verbose_name
        unique_together = ('batch_no', 'seq_no')
        indexes = [models.Index(fields=['order_date', 'route'], name='sorted_orde_order_d_ed21c7_idx')]
