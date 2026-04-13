from django.db import migrations


KEY_MAP = {
    '默认优化模式编号': 'DEFAULT_OPTIMIZE_MODE_NO',
    '线路切换惩罚系数': 'ROUTE_SWITCH_PENALTY',
    '最大重启次数': 'MAX_RESTARTS',
    '最大迭代次数': 'MAX_ITERATIONS',
    '固定上箱间隔': 'BOX_INTERVAL_SECONDS',
}

DEFAULTS = {
    'DEFAULT_OPTIMIZE_MODE_NO': ('', '默认优化模式'),
    'ROUTE_SWITCH_PENALTY': ('0.2', '线路切换连续性惩罚因子'),
    'MAX_RESTARTS': ('5', '排序局部搜索随机重启次数'),
    'MAX_ITERATIONS': ('100', '排序局部搜索最大迭代次数'),
    'BOX_INTERVAL_SECONDS': ('2', '固定上箱间隔(秒)'),
}


def normalize_runtime_config_keys(apps, schema_editor):
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')

    for old_key, new_key in KEY_MAP.items():
        old_row = GlobalConfig.objects.filter(config_key=old_key).first()
        if old_row:
            new_row, _ = GlobalConfig.objects.get_or_create(
                config_key=new_key,
                defaults={
                    'config_value': old_row.config_value,
                    'enabled': old_row.enabled,
                    'remark': old_row.remark,
                },
            )
            if new_row.config_value != old_row.config_value:
                new_row.config_value = old_row.config_value
                new_row.enabled = old_row.enabled
                new_row.remark = old_row.remark
                new_row.save(update_fields=['config_value', 'enabled', 'remark'])

    for key, (value, remark) in DEFAULTS.items():
        GlobalConfig.objects.get_or_create(
            config_key=key,
            defaults={
                'config_value': value,
                'enabled': True,
                'remark': remark,
            },
        )


def rollback_runtime_config_keys(apps, schema_editor):
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')
    GlobalConfig.objects.filter(config_key__in=DEFAULTS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('optimizer', '0003_seed_sorting_runtime_configs'),
    ]

    operations = [
        migrations.RunPython(normalize_runtime_config_keys, rollback_runtime_config_keys),
    ]
