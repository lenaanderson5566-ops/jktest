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

    def clean(self):
        super().clean()
        checks = {
            '100': self.qty_100,
            '50': self.qty_50,
            '20': self.qty_20,
            '10': self.qty_10,
            '5': self.qty_5,
            '1': self.qty_coin_1,
            '0.5': self.qty_coin_05,
            '0.1': self.qty_coin_01,
        }
        for denom_text, qty in checks.items():
            if qty and qty > 0:
                _validate_denomination_binding(denom_text)


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
