from django.db import migrations


def seed_ortools_configs(apps, schema_editor):
    GlobalConfig = apps.get_model('masterdata', 'GlobalConfig')
    configs = [
        ('ORTOOLS_MAX_BLOCKS', '40', 'ORTools 求解最大机构块数量，超过后回退启发式'),
        ('ORTOOLS_MAX_TIME_SECONDS', '1.2', 'ORTools 单次求解最大时长(秒)'),
        ('ORTOOLS_NUM_WORKERS', '2', 'ORTools 并行求解线程数'),
        ('ORTOOLS_RANDOM_SEED', '42', 'ORTools 随机种子'),
    ]
    for key, value, remark in configs:
        GlobalConfig.objects.update_or_create(
            config_key=key,
            defaults={
                'config_value': value,
                'enabled': True,
                'remark': remark,
            },
        )


def unseed_ortools_configs(apps, schema_editor):
    GlobalConfig = apps.get_model('masterdata', 'GlobalConfig')
    GlobalConfig.objects.filter(config_key__in=[
        'ORTOOLS_MAX_BLOCKS',
        'ORTOOLS_MAX_TIME_SECONDS',
        'ORTOOLS_NUM_WORKERS',
        'ORTOOLS_RANDOM_SEED',
    ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('masterdata', '0004_add_station_switch_interval_config'),
    ]

    operations = [
        migrations.RunPython(seed_ortools_configs, unseed_ortools_configs),
    ]
