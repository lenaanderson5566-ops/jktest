from django.db import migrations


DEFAULT_MODES = [
    {
        'mode_no': 'MODE_GLOBAL_TIME',
        'mode_name': '全局时长优化',
        'mode_type': 'GLOBAL',
        'enabled': True,
        'remark': '默认以总时长最小化为目标',
        'params': [
            {'category': 'TOTAL_TIME_WEIGHT', 'station': None, 'value': '1.0000', 'enabled': True, 'remark': '总时长主目标'},
            {'category': 'STATION_CONCENTRATION_WEIGHT', 'station': None, 'value': '0.2000', 'enabled': True, 'remark': '工位集中度辅助目标'},
            {'category': 'ROUTE_CONTINUITY_WEIGHT', 'station': None, 'value': '0.2000', 'enabled': True, 'remark': '线路连续性辅助目标'},
        ],
    },
    {
        'mode_no': 'MODE_STATION_1',
        'mode_name': '1号位集中优化',
        'mode_type': 'GLOBAL',
        'enabled': True,
        'remark': '强调1号工位集中度的优化模式',
        'params': [
            {'category': 'TOTAL_TIME_WEIGHT', 'station': None, 'value': '0.7000', 'enabled': True, 'remark': '总时长权重'},
            {'category': 'ROUTE_CONTINUITY_WEIGHT', 'station': None, 'value': '0.1500', 'enabled': True, 'remark': '线路连续性权重'},
            {'category': 'STATION_CONCENTRATION_WEIGHT', 'station': 'ST01', 'value': '1.2000', 'enabled': True, 'remark': '1号位集中权重'},
        ],
    },
]


def _resolve_station(PackingStation, station_no):
    if not station_no:
        return None
    station = PackingStation.objects.filter(station_no=station_no).first()
    if station:
        return station
    return PackingStation.objects.order_by('station_order').first()


def seed_default_modes(apps, schema_editor):
    OptimizeMode = apps.get_model('optimizer', 'OptimizeMode')
    OptimizeModeParameter = apps.get_model('optimizer', 'OptimizeModeParameter')
    PackingStation = apps.get_model('masterdata', 'PackingStation')
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')

    for item in DEFAULT_MODES:
        mode, _ = OptimizeMode.objects.update_or_create(
            mode_no=item['mode_no'],
            defaults={
                'mode_name': item['mode_name'],
                'mode_type': item['mode_type'],
                'enabled': item['enabled'],
                'remark': item['remark'],
            },
        )
        for p in item['params']:
            station = _resolve_station(PackingStation, p['station'])
            OptimizeModeParameter.objects.update_or_create(
                mode=mode,
                category=p['category'],
                station=station,
                defaults={
                    'value': p['value'],
                    'enabled': p['enabled'],
                    'remark': p['remark'],
                },
            )

    GlobalConfig.objects.update_or_create(
        config_key='DEFAULT_OPTIMIZE_MODE_NO',
        defaults={
            'config_value': 'MODE_GLOBAL_TIME',
            'enabled': True,
            'remark': '默认优化模式',
        },
    )


def unseed_default_modes(apps, schema_editor):
    OptimizeMode = apps.get_model('optimizer', 'OptimizeMode')
    OptimizeMode.objects.filter(mode_no__in=[x['mode_no'] for x in DEFAULT_MODES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('masterdata', '0001_initial'),
        ('optimizer', '0006_seed_missing_runtime_configs'),
    ]

    operations = [
        migrations.RunPython(seed_default_modes, unseed_default_modes),
    ]
