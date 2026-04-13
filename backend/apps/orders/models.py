from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from apps.masterdata.models import (
    CurrencyType,
    DenominationPackagingSpec,
    Organization,
    StationDenominationSupport,
    TransportRoute,
)


class OrderStatus(models.TextChoices):
    NEW = 'NEW', '新建'
    LOCKED = 'LOCKED', '锁定'
    RUNNING = 'RUNNING', '运行中'
    FINISHED = 'FINISHED', '已完成'
    CANCELED = 'CANCELED', '已取消'


class OrganizationOrder(models.Model):
    order_no = models.CharField('订单编号', max_length=64)
    order_date = models.DateField('订单日期')
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='orders', verbose_name='机构')
    route = models.ForeignKey(TransportRoute, on_delete=models.PROTECT, related_name='orders', verbose_name='线路')
    currency_type = models.CharField('币种类型', max_length=16, choices=CurrencyType.choices)
    denomination = models.DecimalField('面额', max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField('数量', default=0)
    status = models.CharField('订单状态', max_length=16, choices=OrderStatus.choices, default=OrderStatus.NEW)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'organization_order'
        verbose_name = '机构订单'
        verbose_name_plural = verbose_name
        unique_together = ('order_no', 'currency_type', 'denomination')
        indexes = [
            models.Index(fields=['order_date', 'route']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.order_no}-{self.denomination}'

    def clean(self):
        super().clean()
        if self.quantity and self.quantity > 0:
            _validate_denomination_binding(str(self.denomination), self.currency_type)


def _validate_denomination_binding(denom_text: str, currency_type: str):
    denomination = Decimal(denom_text)

    spec_exists = DenominationPackagingSpec.objects.filter(
        currency_type=currency_type,
        denomination=denomination,
        enabled=True,
    ).exists()
    support_exists = StationDenominationSupport.objects.filter(
        currency_type=currency_type,
        denomination=denomination,
        enabled=True,
    ).exists()

    if not spec_exists or not support_exists:
        raise ValidationError(
            f'面额 {denom_text} 缺少绑定配置：'
            f"{'封装规格' if not spec_exists else ''}"
            f"{'、' if (not spec_exists and not support_exists) else ''}"
            f"{'工位支持面额' if not support_exists else ''}。"
        )
