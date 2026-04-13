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
    import_batch = models.ForeignKey('OrderImportBatch', on_delete=models.CASCADE, related_name='details', verbose_name='导入批次', null=True, blank=True)
    line_no = models.PositiveIntegerField('行号', default=0)
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
        verbose_name = '订单导入'
        verbose_name_plural = verbose_name
        unique_together = ('import_batch', 'line_no')
        indexes = [
            models.Index(fields=['order_date', 'route'], name='organizatio_order_d_f8e7bc_idx'),
            models.Index(fields=['status'], name='organizatio_status_803f99_idx'),
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


class SplitType(models.TextChoices):
    PIPELINE_BOX = 'PIPELINE_BOX', '流水线箱'
    MANUAL_PACK = 'MANUAL_PACK', '人工包'


class OrderSplitDetail(models.Model):
    order = models.ForeignKey(OrganizationOrder, on_delete=models.CASCADE, related_name='split_details', verbose_name='订单明细')
    split_type = models.CharField('拆分类型', max_length=16, choices=SplitType.choices)
    seq_no = models.PositiveIntegerField('序号', default=1)
    bundle_count = models.PositiveIntegerField('捆数', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'order_split_detail'
        verbose_name = '订单拆分明细'
        verbose_name_plural = verbose_name
        unique_together = ('order', 'split_type', 'seq_no')

    def __str__(self):
        return f'{self.order_id}-{self.split_type}-{self.seq_no}'


class ManualPackManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(split_type=SplitType.MANUAL_PACK)


class PipelineBoxManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(split_type=SplitType.PIPELINE_BOX)


class ManualPackTask(OrderSplitDetail):
    objects = ManualPackManager()

    class Meta:
        proxy = True
        verbose_name = '人工清单'
        verbose_name_plural = verbose_name


class PipelineBoxTask(OrderSplitDetail):
    objects = PipelineBoxManager()

    class Meta:
        proxy = True
        verbose_name = '流水线箱清单'
        verbose_name_plural = verbose_name


class OrderImportBatch(models.Model):
    order_no = models.CharField('订单编号', max_length=64, unique=True)
    order_date = models.DateField('订单日期')
    source_filename = models.CharField('来源文件名', max_length=255, blank=True)
    total_rows = models.PositiveIntegerField('导入行数', default=0)
    created_at = models.DateTimeField('导入时间', auto_now_add=True)

    class Meta:
        db_table = 'order_import_batch'
        verbose_name = '订单管理'
        verbose_name_plural = verbose_name
        ordering = ('-created_at',)

    def __str__(self):
        return self.order_no
