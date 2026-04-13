from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='OrganizationOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_no', models.CharField(max_length=64, unique=True, verbose_name='订单编号')),
                ('order_date', models.DateField(verbose_name='订单日期')),
                ('qty_100', models.PositiveIntegerField(default=0, verbose_name='100元捆数')),
                ('qty_50', models.PositiveIntegerField(default=0, verbose_name='50元捆数')),
                ('qty_20', models.PositiveIntegerField(default=0, verbose_name='20元捆数')),
                ('qty_10', models.PositiveIntegerField(default=0, verbose_name='10元捆数')),
                ('qty_5', models.PositiveIntegerField(default=0, verbose_name='5元捆数')),
                ('qty_coin_1', models.PositiveIntegerField(default=0, verbose_name='1元包数')),
                ('qty_coin_05', models.PositiveIntegerField(default=0, verbose_name='0.5元包数')),
                ('qty_coin_01', models.PositiveIntegerField(default=0, verbose_name='0.1元包数')),
                ('status', models.CharField(choices=[('NEW', '新建'), ('LOCKED', '锁定'), ('RUNNING', '运行中'), ('FINISHED', '已完成'), ('CANCELED', '已取消')], default='NEW', max_length=16, verbose_name='订单状态')),
                ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='orders', to='masterdata.organization', verbose_name='机构')),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='orders', to='masterdata.transportroute', verbose_name='线路')),
            ],
            options={
                'verbose_name': '机构订单',
                'verbose_name_plural': '机构订单',
                'db_table': 'organization_order',
                'indexes': [models.Index(fields=['order_date', 'route'], name='organizatio_order_d_f8e7bc_idx'), models.Index(fields=['status'], name='organizatio_status_803f99_idx')],
            },
        ),
    ]
