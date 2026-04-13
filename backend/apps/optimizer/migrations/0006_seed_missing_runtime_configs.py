from django.db import migrations


REQUIRED_RUNTIME_CONFIGS = {
    'MAX_ITERATIONS': ('100', '排序局部搜索最大迭代次数'),
    'BOX_INTERVAL_SECONDS': ('2', '固定上箱间隔(秒)'),
    'SORT_TRACE_ENABLED': ('0', '是否打印排序过程日志(0/1)'),
}


def seed_missing_runtime_configs(apps, schema_editor):
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')
    for key, (value, remark) in REQUIRED_RUNTIME_CONFIGS.items():
        row, created = GlobalConfig.objects.get_or_create(
            config_key=key,
            defaults={'config_value': value, 'enabled': True, 'remark': remark},
        )
        if (not created) and (not row.config_value):
            row.config_value = value
            if not row.remark:
                row.remark = remark
            row.save(update_fields=['config_value', 'remark'])


def unseed_missing_runtime_configs(apps, schema_editor):
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')
    GlobalConfig.objects.filter(config_key__in=REQUIRED_RUNTIME_CONFIGS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('optimizer', '0005_remove_legacy_chinese_runtime_keys'),
    ]

    operations = [
        migrations.RunPython(seed_missing_runtime_configs, unseed_missing_runtime_configs),
    ]
