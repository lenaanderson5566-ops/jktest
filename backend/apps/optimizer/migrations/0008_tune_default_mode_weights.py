from django.db import migrations


TUNED_PARAMS = {
    'MODE_GLOBAL_TIME': [
        {'category': 'TOTAL_TIME_WEIGHT', 'station': None, 'value': '1.0000'},
        {'category': 'STATION_CONCENTRATION_WEIGHT', 'station': None, 'value': '0.0500'},
        {'category': 'ROUTE_CONTINUITY_WEIGHT', 'station': None, 'value': '0.0500'},
    ],
    'MODE_STATION_1': [
        {'category': 'TOTAL_TIME_WEIGHT', 'station': None, 'value': '0.2500'},
        {'category': 'ROUTE_CONTINUITY_WEIGHT', 'station': None, 'value': '0.0500'},
        {'category': 'STATION_CONCENTRATION_WEIGHT', 'station': 'ST01', 'value': '2.0000'},
    ],
}


def _resolve_station(PackingStation, station_no):
    if not station_no:
        return None
    return PackingStation.objects.filter(station_no=station_no).first() or PackingStation.objects.order_by('station_order').first()


def tune_default_mode_weights(apps, schema_editor):
    OptimizeMode = apps.get_model('optimizer', 'OptimizeMode')
    OptimizeModeParameter = apps.get_model('optimizer', 'OptimizeModeParameter')
    PackingStation = apps.get_model('masterdata', 'PackingStation')

    for mode_no, params in TUNED_PARAMS.items():
        mode = OptimizeMode.objects.filter(mode_no=mode_no).first()
        if not mode:
            continue
        for item in params:
            OptimizeModeParameter.objects.update_or_create(
                mode=mode,
                category=item['category'],
                station=_resolve_station(PackingStation, item['station']),
                defaults={'value': item['value'], 'enabled': True},
            )


class Migration(migrations.Migration):

    dependencies = [
        ('masterdata', '0001_initial'),
        ('optimizer', '0007_seed_default_optimize_modes_and_params'),
    ]

    operations = [
        migrations.RunPython(tune_default_mode_weights, migrations.RunPython.noop),
    ]
