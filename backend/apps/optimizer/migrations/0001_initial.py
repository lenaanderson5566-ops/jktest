from django.db import migrations, models
import django.db.models.deletion
import django.db.models.functions.comparison
from django.db.models import Value


class Migration(migrations.Migration):
    initial = True
    dependencies = [('masterdata', '0001_initial')]

    operations = [
        migrations.CreateModel(
            name='GlobalConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('config_key', models.CharField(max_length=64, unique=True, verbose_name='配置项名称')),
                ('config_value', models.CharField(max_length=255, verbose_name='配置项值')),
                ('enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
            ],
            options={'db_table': 'global_config', 'verbose_name': '全局配置', 'verbose_name_plural': '全局配置'},
        ),
        migrations.CreateModel(
            name='OptimizeMode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode_no', models.CharField(max_length=32, unique=True, verbose_name='模式编号')),
                ('mode_name', models.CharField(max_length=128, verbose_name='模式名称')),
                ('mode_type', models.CharField(choices=[('GLOBAL', '全局'), ('BY_ROUTE', '分线路')], max_length=16, verbose_name='模式类型')),
                ('enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
            ],
            options={'db_table': 'optimize_mode', 'verbose_name': '优化模式配置', 'verbose_name_plural': '优化模式配置'},
        ),
        migrations.CreateModel(
            name='OptimizeModeParameter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('TOTAL_TIME_WEIGHT', '总耗时权重'), ('STATION_SPAN_WEIGHT', '工位跨度权重'), ('MANUAL_STATION_DURATION_WEIGHT', '人工工位时长权重'), ('STATION_CONCENTRATION_WEIGHT', '特定工位集中权重'), ('ROUTE_CONTINUITY_WEIGHT', '线路连续性权重')], max_length=48, verbose_name='参数类别')),
                ('value', models.DecimalField(decimal_places=4, max_digits=12, verbose_name='参数值')),
                ('enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
                ('mode', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parameters', to='optimizer.optimizemode', verbose_name='模式')),
                ('station', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='mode_parameters', to='masterdata.packingstation', verbose_name='工位')),
            ],
            options={'db_table': 'optimize_mode_parameter', 'verbose_name': '优化模式参数明细', 'verbose_name_plural': '优化模式参数明细'},
        ),
        migrations.AddConstraint(
            model_name='optimizemodeparameter',
            constraint=models.UniqueConstraint(fields=('mode', 'category', 'station'), name='uq_mode_category_station'),
        ),
        migrations.AddConstraint(
            model_name='optimizemodeparameter',
            constraint=models.UniqueConstraint(django.db.models.functions.comparison.Coalesce('station', Value(0)), 'mode', 'category', name='uq_mode_category_station_coalesced'),
        ),
    ]
