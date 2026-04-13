from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [('optimizer', '0001_initial')]

    operations = [
        migrations.CreateModel(
            name='SortingJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_no', models.CharField(blank=True, max_length=64, unique=True, verbose_name='任务编号')),
                ('order_date', models.DateField(verbose_name='订单日期')),
                ('status', models.CharField(choices=[('PENDING', '待执行'), ('RUNNING', '运行中'), ('SUCCESS', '成功'), ('FAILED', '失败')], default='PENDING', max_length=16, verbose_name='状态')),
                ('result_batch_no', models.CharField(blank=True, max_length=64, verbose_name='结果批次号')),
                ('message', models.CharField(blank=True, max_length=255, verbose_name='结果信息')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='开始时间')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='完成时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('mode', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sorting_jobs', to='optimizer.optimizemode', verbose_name='优化模式')),
            ],
            options={'db_table': 'sorting_job', 'verbose_name': '排序计算任务', 'verbose_name_plural': '排序计算任务', 'indexes': [models.Index(fields=['order_date', 'status'], name='sorting_job_order_d_01f655_idx')]},
        ),
    ]
