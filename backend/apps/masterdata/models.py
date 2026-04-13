from django.db import models


class TransportRoute(models.Model):
    route_no = models.CharField('线路号', max_length=32, unique=True)
    route_name = models.CharField('线路名称', max_length=128)
    enabled = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'transport_route'
        verbose_name = '押运线路'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.route_no}-{self.route_name}'


class Organization(models.Model):
    org_no = models.CharField('机构号', max_length=32, unique=True)
    org_name = models.CharField('机构名称', max_length=128)
    route = models.ForeignKey(TransportRoute, on_delete=models.PROTECT, related_name='organizations', verbose_name='所属线路')
    enabled = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'organization'
        verbose_name = '机构'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.org_no}-{self.org_name}'


class StationType(models.TextChoices):
    MANUAL = 'MANUAL', '人工'
    ROBOT = 'ROBOT', '机械臂'
    SUCTION = 'SUCTION', '吸盘'


class PackingStation(models.Model):
    station_no = models.CharField('工位号', max_length=32, unique=True)
    station_name = models.CharField('工位名称', max_length=128)
    station_order = models.PositiveIntegerField('工位顺序', unique=True)
    station_type = models.CharField('工位类型', max_length=16, choices=StationType.choices)
    fixed_boxing_seconds = models.DecimalField('固定装箱时间(秒)', max_digits=8, decimal_places=2, default=0)
    max_units_per_action = models.PositiveIntegerField('单次装箱最大单位', default=1)
    unit_boxing_seconds = models.DecimalField('单位装箱时间(秒)', max_digits=8, decimal_places=2, default=0)
    enabled = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'packing_station'
        verbose_name = '装箱工位'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.station_name}({self.station_no})'


class CurrencyType(models.TextChoices):
    BANKNOTE = 'BANKNOTE', '纸币'
    COIN = 'COIN', '硬币'


class StationDenominationSupport(models.Model):
    station = models.ForeignKey(PackingStation, on_delete=models.CASCADE, related_name='denomination_supports', verbose_name='工位')
    currency_type = models.CharField('币种类型', max_length=16, choices=CurrencyType.choices)
    denomination = models.DecimalField('面额', max_digits=8, decimal_places=2)
    enabled = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'station_denomination_support'
        verbose_name = '工位支持面额'
        verbose_name_plural = verbose_name
        unique_together = ('station', 'currency_type', 'denomination')


class StationDenominationEfficiency(models.Model):
    station = models.ForeignKey(PackingStation, on_delete=models.CASCADE, related_name='denomination_efficiencies', verbose_name='工位')
    currency_type = models.CharField('币种类型', max_length=16, choices=CurrencyType.choices)
    denomination = models.DecimalField('面额', max_digits=8, decimal_places=2)
    max_units_per_action = models.PositiveIntegerField('单次装箱最大单位', default=1)
    unit_boxing_seconds = models.DecimalField('单位装箱时间(秒)', max_digits=8, decimal_places=2)
    enabled = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'station_denomination_efficiency'
        verbose_name = '工位面额效率'
        verbose_name_plural = verbose_name
        unique_together = ('station', 'currency_type', 'denomination')


class DenominationPackagingSpec(models.Model):
    currency_type = models.CharField('币种类型', max_length=16, choices=CurrencyType.choices)
    denomination = models.DecimalField('面额', max_digits=8, decimal_places=2)
    units_per_package = models.PositiveIntegerField('每捆/包数量', help_text='如100元纸币每捆1000张，1元硬币每包500枚')
    enabled = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'denomination_packaging_spec'
        verbose_name = '面额封装规格'
        verbose_name_plural = verbose_name
        unique_together = ('currency_type', 'denomination')


class GlobalConfig(models.Model):
    config_key = models.CharField('配置项名称', max_length=64, unique=True)
    config_value = models.CharField('配置项值', max_length=255)
    enabled = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'global_config'
        verbose_name = '全局配置'
        verbose_name_plural = verbose_name


class TransferSegment(models.Model):
    from_station = models.ForeignKey(PackingStation, on_delete=models.PROTECT, related_name='transfer_from', verbose_name='起始工位')
    to_station = models.ForeignKey(PackingStation, on_delete=models.PROTECT, related_name='transfer_to', verbose_name='终点工位')
    fixed_transfer_seconds = models.DecimalField('固定传输时间(秒)', max_digits=8, decimal_places=2)
    enabled = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'transfer_segment'
        verbose_name = '传输段'
        verbose_name_plural = verbose_name
        unique_together = ('from_station', 'to_station')

    def __str__(self):
        return f'{self.from_station} -> {self.to_station}'
