from django.db import migrations


def seed_schedule_start_time(apps, schema_editor):
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')
    GlobalConfig.objects.update_or_create(
        config_key='SCHEDULE_START_TIME',
        defaults={
            'config_value': '08:00:00',
            'enabled': True,
            'remark': '预计排程起始时间(HH:MM[:SS])',
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('optimizer', '0008_tune_default_mode_weights'),
    ]

    operations = [
        migrations.RunPython(seed_schedule_start_time, migrations.RunPython.noop),
    ]
