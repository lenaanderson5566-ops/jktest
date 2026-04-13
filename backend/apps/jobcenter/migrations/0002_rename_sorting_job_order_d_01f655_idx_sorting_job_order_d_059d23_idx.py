from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('jobcenter', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            SET @idx_exists := (
              SELECT COUNT(1)
              FROM information_schema.statistics
              WHERE table_schema = DATABASE()
                AND table_name = 'sorting_job'
                AND index_name = 'sorting_job_order_d_01f655_idx'
            );
            SET @sql := IF(
              @idx_exists > 0,
              'ALTER TABLE sorting_job RENAME INDEX sorting_job_order_d_01f655_idx TO sorting_job_order_d_059d23_idx',
              'SELECT 1'
            );
            PREPARE stmt FROM @sql;
            EXECUTE stmt;
            DEALLOCATE PREPARE stmt;
            """,
            reverse_sql="""
            SET @idx_exists := (
              SELECT COUNT(1)
              FROM information_schema.statistics
              WHERE table_schema = DATABASE()
                AND table_name = 'sorting_job'
                AND index_name = 'sorting_job_order_d_059d23_idx'
            );
            SET @sql := IF(
              @idx_exists > 0,
              'ALTER TABLE sorting_job RENAME INDEX sorting_job_order_d_059d23_idx TO sorting_job_order_d_01f655_idx',
              'SELECT 1'
            );
            PREPARE stmt FROM @sql;
            EXECUTE stmt;
            DEALLOCATE PREPARE stmt;
            """,
        ),
    ]
