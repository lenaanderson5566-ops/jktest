from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [('masterdata', '0001_initial'), ('optimizer', '0001_initial'), ('orders', '0001_initial')]

    operations = [
        migrations.CreateModel(
            name='RunResultSummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('batch_no', models.CharField(max_length=64, unique=True, verbose_name='运行批次号')),
                ('run_at', models.DateTimeField(auto_now_add=True, verbose_name='运行日期时间')),
                ('total_seconds', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='运行总耗时(秒)')),
                ('score', models.DecimalField(decimal_places=4, max_digits=12, verbose_name='综合评分')),
                ('is_best', models.BooleanField(default=False, verbose_name='是否最优方案')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
                ('optimize_mode', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='run_summaries', to='optimizer.optimizemode', verbose_name='优化模式')),
            ],
            options={'db_table': 'run_result_summary', 'verbose_name': '排序运行结果主评估', 'verbose_name_plural': '排序运行结果主评估'},
        ),
        migrations.CreateModel(
            name='RunResultStationDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('station_span', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='工位跨度')),
                ('busy_seconds', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='工位忙碌时长(秒)')),
                ('idle_seconds', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='工位空闲时长(秒)')),
                ('wait_seconds', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='工位等待时长(秒)')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='station_details', to='runs.runresultsummary', verbose_name='运行批次')),
                ('station', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='run_details', to='masterdata.packingstation', verbose_name='工位')),
            ],
            options={'db_table': 'run_result_station_detail', 'verbose_name': '排序运行结果工位评估明细', 'verbose_name_plural': '排序运行结果工位评估明细', 'unique_together': {('batch', 'station')}},
        ),
        migrations.CreateModel(
            name='SortedOrderResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('seq_no', models.PositiveIntegerField(verbose_name='排序序号')),
                ('order_date', models.DateField(verbose_name='订单日期')),
                ('final_position', models.PositiveIntegerField(verbose_name='最终排序位置')),
                ('est_start_time', models.DateTimeField(verbose_name='预计开始时间')),
                ('est_finish_time', models.DateTimeField(verbose_name='预计完成时间')),
                ('est_total_seconds', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='预计总处理时长(秒)')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sorted_orders', to='runs.runresultsummary', verbose_name='运行批次')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sorted_results', to='orders.organizationorder', verbose_name='订单')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sorted_results', to='masterdata.organization', verbose_name='机构')),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sorted_results', to='masterdata.transportroute', verbose_name='线路')),
            ],
            options={'db_table': 'sorted_order_result', 'verbose_name': '排序结果', 'verbose_name_plural': '排序结果', 'unique_together': {('batch', 'seq_no')}, 'indexes': [models.Index(fields=['order_date', 'route'], name='sorted_orde_order_d_ed21c7_idx')]},
        ),
    ]
