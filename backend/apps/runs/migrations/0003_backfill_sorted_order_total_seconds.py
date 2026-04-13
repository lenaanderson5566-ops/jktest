from decimal import Decimal

from django.db import migrations


def backfill_est_total_seconds(apps, schema_editor):
    SortedOrderResult = apps.get_model('runs', 'SortedOrderResult')

    batch_ids = SortedOrderResult.objects.values_list('batch_id', flat=True).distinct()
    for batch_id in batch_ids:
        rows = list(
            SortedOrderResult.objects.filter(batch_id=batch_id)
            .only('id', 'est_start_time', 'est_finish_time')
            .order_by('est_finish_time', 'id')
        )
        if not rows:
            continue
        batch_start = min((row.est_start_time for row in rows if row.est_start_time is not None), default=None)
        if batch_start is None:
            continue
        for row in rows:
            if row.est_finish_time is None:
                continue
            elapsed = (row.est_finish_time - batch_start).total_seconds()
            row.est_total_seconds = Decimal(str(round(max(0.0, elapsed), 2)))
        SortedOrderResult.objects.bulk_update(rows, ['est_total_seconds'])


class Migration(migrations.Migration):

    dependencies = [
        ('runs', '0002_delete_runresultstationdetail'),
    ]

    operations = [
        migrations.RunPython(backfill_est_total_seconds, migrations.RunPython.noop),
    ]
