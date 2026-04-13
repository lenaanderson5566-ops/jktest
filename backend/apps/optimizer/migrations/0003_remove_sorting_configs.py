from django.db import migrations


OBSOLETE_SORTING_CONFIGS = ['默认优化模式编号', '线路切换惩罚系数', '最大重启次数']


def remove_sorting_configs(apps, schema_editor):
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')
    GlobalConfig.objects.filter(config_key__in=OBSOLETE_SORTING_CONFIGS).delete()


def restore_sorting_configs(apps, schema_editor):
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')
    defaults = {
        '默认优化模式编号': ('', '默认优化模式编号'),
        '线路切换惩罚系数': ('0.2', '线路切换惩罚系数'),
        '最大重启次数': ('5', '最大重启次数的设置项'),
    }
    for key, (value, remark) in defaults.items():
        GlobalConfig.objects.update_or_create(
            config_key=key,
            defaults={
                'config_value': value,
                'enabled': True,
                'remark': remark,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('optimizer', '0002_seed_split_configs'),
    ]

    operations = [
        migrations.RunPython(remove_sorting_configs, restore_sorting_configs),
    ]
