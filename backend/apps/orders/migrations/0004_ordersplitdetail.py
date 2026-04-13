from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_order_import_batch_and_detail_link'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderSplitDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('split_type', models.CharField(choices=[('PIPELINE_BOX', '流水线箱'), ('MANUAL_PACK', '人工包')], max_length=16, verbose_name='拆分类型')),
                ('seq_no', models.PositiveIntegerField(default=1, verbose_name='序号')),
                ('bundle_count', models.PositiveIntegerField(default=0, verbose_name='捆数')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='split_details', to='orders.organizationorder', verbose_name='订单明细')),
            ],
            options={
                'verbose_name': '订单拆分明细',
                'verbose_name_plural': '订单拆分明细',
                'db_table': 'order_split_detail',
                'unique_together': {('order', 'split_type', 'seq_no')},
            },
        ),
    ]
