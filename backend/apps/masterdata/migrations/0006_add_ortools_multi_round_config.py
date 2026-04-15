from django.db import migrations


def seed_ortools_multi_round(apps, schema_editor):
    GlobalConfig = apps.get_model('masterdata', 'GlobalConfig')
    GlobalConfig.objects.update_or_create(
        config_key='ORTOOLS_MULTI_ROUNDS',
        defaults={
            'config_value': '3',
            'enabled': True,
            'remark': 'ORTools 多轮求解轮数(每轮使用不同随机种子)',
        },
    )


def unseed_ortools_multi_round(apps, schema_editor):
    GlobalConfig = apps.get_model('masterdata', 'GlobalConfig')
    GlobalConfig.objects.filter(config_key='ORTOOLS_MULTI_ROUNDS').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('masterdata', '0005_add_ortools_configs'),
    ]

    operations = [
        migrations.RunPython(seed_ortools_multi_round, unseed_ortools_multi_round),
    ]
