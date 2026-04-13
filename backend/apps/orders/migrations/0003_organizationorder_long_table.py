from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_organizationorder_qty_coin_001'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organizationorder',
            name='order_no',
            field=models.CharField(max_length=64, verbose_name='订单编号'),
        ),
        migrations.AddField(
            model_name='organizationorder',
            name='currency_type',
            field=models.CharField(choices=[('BANKNOTE', '纸币'), ('COIN', '硬币')], default='BANKNOTE', max_length=16, verbose_name='币种类型'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='organizationorder',
            name='denomination',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8, verbose_name='面额'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='organizationorder',
            name='quantity',
            field=models.PositiveIntegerField(default=0, verbose_name='数量'),
        ),
        migrations.RemoveField(model_name='organizationorder', name='qty_100'),
        migrations.RemoveField(model_name='organizationorder', name='qty_50'),
        migrations.RemoveField(model_name='organizationorder', name='qty_20'),
        migrations.RemoveField(model_name='organizationorder', name='qty_10'),
        migrations.RemoveField(model_name='organizationorder', name='qty_5'),
        migrations.RemoveField(model_name='organizationorder', name='qty_coin_1'),
        migrations.RemoveField(model_name='organizationorder', name='qty_coin_05'),
        migrations.RemoveField(model_name='organizationorder', name='qty_coin_01'),
        migrations.RemoveField(model_name='organizationorder', name='qty_coin_001'),
        migrations.AlterUniqueTogether(
            name='organizationorder',
            unique_together={('order_no', 'currency_type', 'denomination')},
        ),
    ]
