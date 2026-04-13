from django.db import migrations, models
import django.db.models.deletion


def backfill_batch_and_mode(apps, schema_editor):
    SortedOrderResult = apps.get_model('runs', 'SortedOrderResult')
    rows = []
    for row in SortedOrderResult.objects.select_related('batch').only('id', 'batch__batch_no', 'batch__optimize_mode_id').iterator():
        row.batch_no = row.batch.batch_no
        row.optimize_mode_id = row.batch.optimize_mode_id
        rows.append(row)
    if rows:
        SortedOrderResult.objects.bulk_update(rows, ['batch_no', 'optimize_mode'])


class Migration(migrations.Migration):

    dependencies = [
        ('optimizer', '0010_seed_adjacent_weights'),
        ('runs', '0005_rebase_sorted_times_to_schedule_start'),
    ]

    operations = [
        migrations.AddField(
            model_name='sortedorderresult',
            name='batch_no',
            field=models.CharField(db_index=True, default='', max_length=64, verbose_name='运行批次号'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='sortedorderresult',
            name='optimize_mode',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='sorted_order_results', to='optimizer.optimizemode', verbose_name='优化模式'),
        ),
        migrations.RunPython(backfill_batch_and_mode, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='sortedorderresult',
            unique_together={('batch_no', 'seq_no')},
        ),
        migrations.RemoveField(
            model_name='sortedorderresult',
            name='batch',
        ),
        migrations.DeleteModel(
            name='RunResultSummary',
        ),
    ]
