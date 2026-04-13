from decimal import Decimal

from django.db import migrations


DEFAULT_MODES = [
    {
        'mode_no': 'MODE_GLOBAL_TIME',
        'mode_name': '全局时长优化',
        'mode_type': 'GLOBAL',
        'remark': '默认模式：优先压缩全局总耗时。',
        'params': [
            {'category': 'TOTAL_TIME_WEIGHT', 'value': Decimal('1.0000')},
            {'category': 'STATION_CONCENTRATION_WEIGHT', 'value': Decimal('0.1500')},
            {'category': 'ROUTE_CONTINUITY_WEIGHT', 'value': Decimal('0.1000')},
        ],
    },
    {
        'mode_no': 'MODE_STATION_1',
        'mode_name': '1号位集中优化',
        'mode_type': 'GLOBAL',
        'remark': '在保障总时长的同时尽量降低1号位跨度。',
        'params': [
            {'category': 'TOTAL_TIME_WEIGHT', 'value': Decimal('0.9000')},
            {'category': 'STATION_CONCENTRATION_WEIGHT', 'value': Decimal('0.6000')},
            {'category': 'ROUTE_CONTINUITY_WEIGHT', 'value': Decimal('0.1000')},
            {'category': 'STATION_CONCENTRATION_WEIGHT', 'value': Decimal('1.0000'), 'station_order': 1},
        ],
    },
    {
        'mode_no': 'MODE_STATION_3',
        'mode_name': '3号位集中优化',
        'mode_type': 'GLOBAL',
        'remark': '在保障总时长的同时尽量降低3号位跨度。',
        'params': [
            {'category': 'TOTAL_TIME_WEIGHT', 'value': Decimal('0.9000')},
            {'category': 'STATION_CONCENTRATION_WEIGHT', 'value': Decimal('0.6000')},
            {'category': 'ROUTE_CONTINUITY_WEIGHT', 'value': Decimal('0.1000')},
            {'category': 'STATION_CONCENTRATION_WEIGHT', 'value': Decimal('1.0000'), 'station_order': 3},
        ],
    },
    {
        'mode_no': 'MODE_BY_ROUTE',
        'mode_name': '分线路优化',
        'mode_type': 'BY_ROUTE',
        'remark': '优先同线路连续处理，降低线路切换。',
        'params': [
            {'category': 'TOTAL_TIME_WEIGHT', 'value': Decimal('0.8500')},
            {'category': 'STATION_CONCENTRATION_WEIGHT', 'value': Decimal('0.1500')},
            {'category': 'ROUTE_CONTINUITY_WEIGHT', 'value': Decimal('0.9000')},
        ],
    },
]


def seed_default_modes(apps, schema_editor):
    OptimizeMode = apps.get_model('optimizer', 'OptimizeMode')
    OptimizeModeParameter = apps.get_model('optimizer', 'OptimizeModeParameter')
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')
    PackingStation = apps.get_model('masterdata', 'PackingStation')

    station_map = {
        station.station_order: station.id
        for station in PackingStation.objects.filter(enabled=True, station_order__in=[1, 3]).only('id', 'station_order')
    }

    for mode_data in DEFAULT_MODES:
        mode, _ = OptimizeMode.objects.update_or_create(
            mode_no=mode_data['mode_no'],
            defaults={
                'mode_name': mode_data['mode_name'],
                'mode_type': mode_data['mode_type'],
                'enabled': True,
                'remark': mode_data['remark'],
            },
        )

        for param in mode_data['params']:
            station_id = None
            station_order = param.get('station_order')
            if station_order:
                station_id = station_map.get(station_order)
                if not station_id:
                    continue

            OptimizeModeParameter.objects.update_or_create(
                mode_id=mode.id,
                category=param['category'],
                station_id=station_id,
                defaults={
                    'value': param['value'],
                    'enabled': True,
                    'remark': f"默认参数({mode_data['mode_no']})",
                },
            )

    config_defaults = [
        ('默认优化模式编号', 'MODE_GLOBAL_TIME', '默认优化模式'),
        ('线路切换惩罚系数', '1', '线路切换连续性惩罚因子'),
        ('最大重启次数', '5', '排序局部搜索随机重启次数'),
    ]
    for key, value, remark in config_defaults:
        GlobalConfig.objects.update_or_create(
            config_key=key,
            defaults={
                'config_value': value,
                'enabled': True,
                'remark': remark,
            },
        )


def unseed_default_modes(apps, schema_editor):
    OptimizeMode = apps.get_model('optimizer', 'OptimizeMode')
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')

    mode_nos = [item['mode_no'] for item in DEFAULT_MODES]
    OptimizeMode.objects.filter(mode_no__in=mode_nos).delete()
    GlobalConfig.objects.filter(config_key__in=['默认优化模式编号', '线路切换惩罚系数', '最大重启次数']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('masterdata', '0001_initial'),
        ('optimizer', '0002_seed_split_configs'),
    ]

    operations = [
        migrations.RunPython(seed_default_modes, unseed_default_modes),
    ]
