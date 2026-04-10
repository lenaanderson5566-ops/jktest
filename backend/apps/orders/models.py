from django.db import models

from apps.masterdata.models import Organization, TransportRoute


class OrderStatus(models.TextChoices):
    NEW = 'NEW', '新建'
    LOCKED = 'LOCKED', '锁定'
    RUNNING = 'RUNNING', '运行中'
    FINISHED = 'FINISHED', '已完成'
    CANCELED = 'CANCELED', '已取消'


class OrganizationOrder(models.Model):
    order_no = models.CharField('订单编号', max_length=64, unique=True)
    order_date = models.DateField('订单日期')
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='orders', verbose_name='机构')
    route = models.ForeignKey(TransportRoute, on_delete=models.PROTECT, related_name='orders', verbose_name='线路')

    qty_100 = models.PositiveIntegerField('100元捆数', default=0)
    qty_50 = models.PositiveIntegerField('50元捆数', default=0)
    qty_20 = models.PositiveIntegerField('20元捆数', default=0)
    qty_10 = models.PositiveIntegerField('10元捆数', default=0)
    qty_5 = models.PositiveIntegerField('5元捆数', default=0)
    qty_coin_1 = models.PositiveIntegerField('1元包数', default=0)
    qty_coin_05 = models.PositiveIntegerField('0.5元包数', default=0)
    qty_coin_01 = models.PositiveIntegerField('0.1元包数', default=0)

    status = models.CharField('订单状态', max_length=16, choices=OrderStatus.choices, default=OrderStatus.NEW)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'organization_order'
        verbose_name = '机构订单'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['order_date', 'route']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.order_no
