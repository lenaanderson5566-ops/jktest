from decimal import Decimal
from datetime import timedelta

from django.db import migrations


def rebase_sorted_order_times(apps, schema_editor):
    RunResultSummary = apps.get_model('runs', 'RunResultSummary')
    SortedOrderResult = apps.get_model('runs', 'SortedOrderResult')

    for summary in RunResultSummary.objects.only('id', 'run_at').iterator():
        rows = list(
            SortedOrderResult.objects.filter(batch_id=summary.id)
            .only('id', 'est_start_time', 'est_finish_time', 'est_total_seconds')
            .order_by('est_start_time', 'id')
        )
        if not rows:
            continue

        old_base = min((row.est_start_time for row in rows if row.est_start_time is not None), default=None)
        if old_base is None or summary.run_at is None:
            continue

        for row in rows:
            if row.est_start_time is not None:
                start_offset = (row.est_start_time - old_base).total_seconds()
                row.est_start_time = summary.run_at + timedelta(seconds=round(start_offset, 2))
            if row.est_finish_time is not None:
                finish_offset = (row.est_finish_time - old_base).total_seconds()
                row.est_finish_time = summary.run_at + timedelta(seconds=round(finish_offset, 2))
                row.est_total_seconds = Decimal(str(round(max(0.0, finish_offset), 2)))

        SortedOrderResult.objects.bulk_update(rows, ['est_start_time', 'est_finish_time', 'est_total_seconds'])


class Migration(migrations.Migration):

    dependencies = [
        ('runs', '0003_backfill_sorted_order_total_seconds'),
    ]

    operations = [
        migrations.RunPython(rebase_sorted_order_times, migrations.RunPython.noop),
    ]
