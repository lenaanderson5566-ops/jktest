from django.db import migrations


CONFIGS = {
    'ADJ_COMPLEMENT_WEIGHT': {
        'config_value': '0.15',
        'remark': '相邻箱T1/T2互补惩罚权重',
    },
    'T12_SMOOTH_WEIGHT': {
        'config_value': '0.05',
        'remark': '相邻箱T1+T2平滑惩罚权重',
    },
}


def seed_adjacent_weights(apps, schema_editor):
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')
    for config_key, defaults in CONFIGS.items():
        GlobalConfig.objects.update_or_create(
            config_key=config_key,
            defaults={**defaults, 'enabled': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('optimizer', '0009_seed_schedule_start_time'),
    ]

    operations = [
        migrations.RunPython(seed_adjacent_weights, migrations.RunPython.noop),
    ]
