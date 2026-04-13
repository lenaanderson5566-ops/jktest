from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='TransportRoute',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('route_no', models.CharField(max_length=32, unique=True, verbose_name='线路号')),
                ('route_name', models.CharField(max_length=128, verbose_name='线路名称')),
                ('enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
            ],
            options={'db_table': 'transport_route', 'verbose_name': '押运线路', 'verbose_name_plural': '押运线路'},
        ),
        migrations.CreateModel(
            name='PackingStation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('station_no', models.CharField(max_length=32, unique=True, verbose_name='工位号')),
                ('station_name', models.CharField(max_length=128, verbose_name='工位名称')),
                ('station_order', models.PositiveIntegerField(unique=True, verbose_name='工位顺序')),
                ('station_type', models.CharField(choices=[('MANUAL', '人工'), ('ROBOT', '机械臂'), ('SUCTION', '吸盘')], max_length=16, verbose_name='工位类型')),
                ('fixed_boxing_seconds', models.DecimalField(decimal_places=2, default=0, max_digits=8, verbose_name='固定装箱时间(秒)')),
                ('max_units_per_action', models.PositiveIntegerField(default=1, verbose_name='单次装箱最大单位')),
                ('unit_boxing_seconds', models.DecimalField(decimal_places=2, default=0, max_digits=8, verbose_name='单位装箱时间(秒)')),
                ('enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
            ],
            options={'db_table': 'packing_station', 'verbose_name': '装箱工位', 'verbose_name_plural': '装箱工位'},
        ),
        migrations.CreateModel(
            name='DenominationPackagingSpec',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('currency_type', models.CharField(choices=[('BANKNOTE', '纸币'), ('COIN', '硬币')], max_length=16, verbose_name='币种类型')),
                ('denomination', models.DecimalField(decimal_places=2, max_digits=8, verbose_name='面额')),
                ('units_per_package', models.PositiveIntegerField(help_text='如100元纸币每捆1000张，1元硬币每包500枚', verbose_name='每捆/包数量')),
                ('enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
            ],
            options={'db_table': 'denomination_packaging_spec', 'verbose_name': '面额封装规格', 'verbose_name_plural': '面额封装规格', 'unique_together': {('currency_type', 'denomination')}},
        ),
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('org_no', models.CharField(max_length=32, unique=True, verbose_name='机构号')),
                ('org_name', models.CharField(max_length=128, verbose_name='机构名称')),
                ('enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='organizations', to='masterdata.transportroute', verbose_name='所属线路')),
            ],
            options={'db_table': 'organization', 'verbose_name': '机构', 'verbose_name_plural': '机构'},
        ),
        migrations.CreateModel(
            name='StationDenominationSupport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('currency_type', models.CharField(choices=[('BANKNOTE', '纸币'), ('COIN', '硬币')], max_length=16, verbose_name='币种类型')),
                ('denomination', models.DecimalField(decimal_places=2, max_digits=8, verbose_name='面额')),
                ('enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
                ('station', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='denomination_supports', to='masterdata.packingstation', verbose_name='工位')),
            ],
            options={'db_table': 'station_denomination_support', 'verbose_name': '工位支持面额', 'verbose_name_plural': '工位支持面额', 'unique_together': {('station', 'currency_type', 'denomination')}},
        ),
        migrations.CreateModel(
            name='StationDenominationEfficiency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('currency_type', models.CharField(choices=[('BANKNOTE', '纸币'), ('COIN', '硬币')], max_length=16, verbose_name='币种类型')),
                ('denomination', models.DecimalField(decimal_places=2, max_digits=8, verbose_name='面额')),
                ('max_units_per_action', models.PositiveIntegerField(default=1, verbose_name='单次装箱最大单位')),
                ('unit_boxing_seconds', models.DecimalField(decimal_places=2, max_digits=8, verbose_name='单位装箱时间(秒)')),
                ('enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
                ('station', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='denomination_efficiencies', to='masterdata.packingstation', verbose_name='工位')),
            ],
            options={'db_table': 'station_denomination_efficiency', 'verbose_name': '工位面额效率', 'verbose_name_plural': '工位面额效率', 'unique_together': {('station', 'currency_type', 'denomination')}},
        ),
        migrations.CreateModel(
            name='TransferSegment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fixed_transfer_seconds', models.DecimalField(decimal_places=2, max_digits=8, verbose_name='固定传输时间(秒)')),
                ('enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
                ('from_station', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transfer_from', to='masterdata.packingstation', verbose_name='起始工位')),
                ('to_station', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transfer_to', to='masterdata.packingstation', verbose_name='终点工位')),
            ],
            options={'db_table': 'transfer_segment', 'verbose_name': '传输段', 'verbose_name_plural': '传输段', 'unique_together': {('from_station', 'to_station')}},
        ),
    ]
