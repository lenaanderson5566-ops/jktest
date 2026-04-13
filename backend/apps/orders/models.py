from django.db import models

from decimal import Decimal

from django.core.exceptions import ValidationError

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
    order_no = models.CharField('订单编号', max_length=64, unique=True)
    order_date = models.DateField('订单日期')
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name='orders', verbose_name='机构')
    route = models.ForeignKey(TransportRoute, on_delete=models.PROTECT, related_name='orders', verbose_name='线路')

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

    def denomination_quantity_map(self) -> dict[Decimal, int]:
        result: dict[Decimal, int] = {}
        for line in self.lines.all():
            result[Decimal(str(line.denomination))] = int(line.quantity)
        return result


class OrganizationOrderLine(models.Model):
    order = models.ForeignKey(OrganizationOrder, on_delete=models.CASCADE, related_name='lines', verbose_name='订单')
    currency_type = models.CharField('币种类型', max_length=16, choices=CurrencyType.choices)
    denomination = models.DecimalField('面额', max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField('数量', default=0)

    class Meta:
        db_table = 'organization_order_line'
        verbose_name = '机构订单明细'
        verbose_name_plural = verbose_name
        unique_together = ('order', 'currency_type', 'denomination')

    def __str__(self):
        return f'{self.order.order_no}-{self.denomination}'

    def clean(self):
        super().clean()
        if self.quantity and self.quantity > 0:
            _validate_denomination_binding(str(self.denomination))


def _validate_denomination_binding(denom_text: str):
    denomination = Decimal(denom_text)
    currency_type = CurrencyType.COIN if denomination < Decimal('5') else CurrencyType.BANKNOTE

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
