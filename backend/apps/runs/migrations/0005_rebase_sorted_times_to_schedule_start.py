from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db import migrations
from django.utils import timezone


def _load_schedule_start_time(GlobalConfig):
    row = GlobalConfig.objects.filter(config_key='SCHEDULE_START_TIME', enabled=True).first()
    raw = str(row.config_value).strip() if row else ''
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return time(hour=8, minute=0)


def rebase_to_schedule_start(apps, schema_editor):
    SortedOrderResult = apps.get_model('runs', 'SortedOrderResult')
    GlobalConfig = apps.get_model('optimizer', 'GlobalConfig')

    schedule_start = _load_schedule_start_time(GlobalConfig)
    tz = timezone.get_current_timezone()

    batch_ids = SortedOrderResult.objects.values_list('batch_id', flat=True).distinct()
    for batch_id in batch_ids:
        rows = list(
            SortedOrderResult.objects.filter(batch_id=batch_id)
            .only('id', 'order_date', 'est_start_time', 'est_finish_time', 'est_total_seconds')
            .order_by('est_start_time', 'id')
        )
        if not rows:
            continue
        old_base = min((row.est_start_time for row in rows if row.est_start_time is not None), default=None)
        if old_base is None:
            continue

        base_date = min((row.order_date for row in rows if row.order_date is not None), default=None)
        if base_date is None:
            continue

        new_base_naive = datetime.combine(base_date, schedule_start)
        new_base = timezone.make_aware(new_base_naive, tz)

        for row in rows:
            if row.est_start_time is not None:
                start_offset = (row.est_start_time - old_base).total_seconds()
                row.est_start_time = new_base + timedelta(seconds=round(start_offset, 2))
            if row.est_finish_time is not None:
                finish_offset = (row.est_finish_time - old_base).total_seconds()
                row.est_finish_time = new_base + timedelta(seconds=round(finish_offset, 2))
                row.est_total_seconds = Decimal(str(round(max(0.0, finish_offset), 2)))

        SortedOrderResult.objects.bulk_update(rows, ['est_start_time', 'est_finish_time', 'est_total_seconds'])


class Migration(migrations.Migration):

    dependencies = [
        ('optimizer', '0009_seed_schedule_start_time'),
        ('runs', '0004_rebase_sorted_order_times'),
    ]

    operations = [
        migrations.RunPython(rebase_to_schedule_start, migrations.RunPython.noop),
    ]
