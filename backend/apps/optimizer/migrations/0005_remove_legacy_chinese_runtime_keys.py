from django.db import migrations


LEGACY_KEYS = [
    '默认优化模式编号',
    '线路切换惩罚系数',
    '最大重启次数',
    '最大迭代次数',
    '固定上箱间隔',
]


def delete_legacy_keys(apps, schema_editor):
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')
    GlobalConfig.objects.filter(config_key__in=LEGACY_KEYS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('optimizer', '0004_normalize_runtime_config_keys'),
    ]

    operations = [
        migrations.RunPython(delete_legacy_keys, migrations.RunPython.noop),
    ]
