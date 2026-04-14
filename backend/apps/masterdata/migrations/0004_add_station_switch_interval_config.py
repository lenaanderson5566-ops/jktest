from django.db import migrations


def seed_station_switch_interval(apps, schema_editor):
    GlobalConfig = apps.get_model('masterdata', 'GlobalConfig')
    GlobalConfig.objects.update_or_create(
        config_key='STATION_SWITCH_INTERVAL_SECONDS',
        defaults={
            'config_value': '0.5',
            'enabled': True,
            'remark': '同一工位处理相邻箱子的切换间隔(秒)',
        },
    )


def unseed_station_switch_interval(apps, schema_editor):
    GlobalConfig = apps.get_model('masterdata', 'GlobalConfig')
    GlobalConfig.objects.filter(config_key='STATION_SWITCH_INTERVAL_SECONDS').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('masterdata', '0003_add_box_entry_interval_config'),
    ]

    operations = [
        migrations.RunPython(seed_station_switch_interval, unseed_station_switch_interval),
    ]
