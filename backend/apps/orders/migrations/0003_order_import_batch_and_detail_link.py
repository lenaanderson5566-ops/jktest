from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_expand_order_uniqueness_scope'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderImportBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_no', models.CharField(max_length=64, unique=True, verbose_name='订单编号')),
                ('order_date', models.DateField(verbose_name='订单日期')),
                ('source_filename', models.CharField(blank=True, max_length=255, verbose_name='来源文件名')),
                ('total_rows', models.PositiveIntegerField(default=0, verbose_name='导入行数')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='导入时间')),
            ],
            options={
                'verbose_name': '订单管理',
                'verbose_name_plural': '订单管理',
                'db_table': 'order_import_batch',
                'ordering': ('-created_at',),
            },
        ),
        migrations.AddField(
            model_name='organizationorder',
            name='import_batch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='details', to='orders.orderimportbatch', verbose_name='导入批次'),
        ),
        migrations.AddField(
            model_name='organizationorder',
            name='line_no',
            field=models.PositiveIntegerField(default=0, verbose_name='行号'),
        ),
        migrations.AlterUniqueTogether(
            name='organizationorder',
            unique_together={('import_batch', 'line_no')},
        ),
    ]
