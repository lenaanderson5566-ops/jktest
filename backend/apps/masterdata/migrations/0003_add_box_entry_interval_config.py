from django.db import migrations


def seed_box_entry_interval(apps, schema_editor):
    GlobalConfig = apps.get_model('masterdata', 'GlobalConfig')
    GlobalConfig.objects.update_or_create(
        config_key='BOX_ENTRY_INTERVAL_SECONDS',
        defaults={
            'config_value': '5',
            'enabled': True,
            'remark': '流水线上箱时间间隔(秒)',
        },
    )


def unseed_box_entry_interval(apps, schema_editor):
    GlobalConfig = apps.get_model('masterdata', 'GlobalConfig')
    GlobalConfig.objects.filter(config_key='BOX_ENTRY_INTERVAL_SECONDS').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('masterdata', '0002_global_config_and_cleanup'),
    ]

    operations = [
        migrations.RunPython(seed_box_entry_interval, unseed_box_entry_interval),
    ]
