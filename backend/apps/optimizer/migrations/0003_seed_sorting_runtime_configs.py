from django.db import migrations


def seed_runtime_configs(apps, schema_editor):
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')
    GlobalConfig.objects.get_or_create(
        config_key='默认优化模式编号',
        defaults={
            'config_value': '',
            'enabled': True,
            'remark': '默认优化模式编号',
        },
    )
    GlobalConfig.objects.get_or_create(
        config_key='线路切换惩罚系数',
        defaults={
            'config_value': '0.2',
            'enabled': True,
            'remark': '线路切换惩罚系数',
        },
    )
    GlobalConfig.objects.get_or_create(
        config_key='最大重启次数',
        defaults={
            'config_value': '5',
            'enabled': True,
            'remark': '最大重启次数',
        },
    )


def unseed_runtime_configs(apps, schema_editor):
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')
    GlobalConfig.objects.filter(config_key__in=['默认优化模式编号', '线路切换惩罚系数', '最大重启次数']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('optimizer', '0002_seed_split_configs'),
    ]

    operations = [
        migrations.RunPython(seed_runtime_configs, unseed_runtime_configs),
    ]
