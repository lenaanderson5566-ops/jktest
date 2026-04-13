from django.db import migrations, models


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
    ]
