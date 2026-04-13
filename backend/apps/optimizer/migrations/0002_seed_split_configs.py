from django.db import migrations


def seed_split_configs(apps, schema_editor):
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')
    GlobalConfig.objects.get_or_create(
        config_key='MANUAL_PACK_THRESHOLD',
        defaults={
            'config_value': '20',
            'enabled': True,
            'remark': '走人工捆数阈值(捆)',
        },
    )
    GlobalConfig.objects.get_or_create(
        config_key='PIPELINE_BOX_CAPACITY',
        defaults={
            'config_value': '16',
            'enabled': True,
            'remark': '流水线单箱捆数上限(捆)',
        },
    )


def unseed_split_configs(apps, schema_editor):
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')
    GlobalConfig.objects.filter(config_key__in=['MANUAL_PACK_THRESHOLD', 'PIPELINE_BOX_CAPACITY']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('optimizer', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_split_configs, unseed_split_configs),
    ]
