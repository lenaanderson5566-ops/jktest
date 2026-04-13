from django.db import migrations, models


OBSOLETE_TABLES_SQL = """
DROP TABLE IF EXISTS sorted_order_result;
DROP TABLE IF EXISTS run_result_station_detail;
DROP TABLE IF EXISTS run_result_summary;
DROP TABLE IF EXISTS sorting_job;
DROP TABLE IF EXISTS optimize_mode_parameter;
DROP TABLE IF EXISTS optimize_mode;
"""

CREATE_GLOBAL_CONFIG_IF_NOT_EXISTS_SQL = """
CREATE TABLE IF NOT EXISTS global_config (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(64) NOT NULL UNIQUE,
    config_value VARCHAR(255) NOT NULL,
    enabled BOOL NOT NULL DEFAULT TRUE,
    remark VARCHAR(255) NOT NULL DEFAULT ''
);
"""


def seed_global_configs(apps, schema_editor):
    GlobalConfig = apps.get_model('masterdata', 'GlobalConfig')
    GlobalConfig.objects.update_or_create(
        config_key='MANUAL_PACK_THRESHOLD',
        defaults={
            'config_value': '20',
            'enabled': True,
            'remark': '走人工捆数阈值(捆)',
        },
    )
    GlobalConfig.objects.update_or_create(
        config_key='PIPELINE_BOX_CAPACITY',
        defaults={
            'config_value': '16',
            'enabled': True,
            'remark': '流水线单箱捆数上限(捆)',
        },
    )


def unseed_global_configs(apps, schema_editor):
    GlobalConfig = apps.get_model('masterdata', 'GlobalConfig')
    GlobalConfig.objects.filter(config_key__in=['MANUAL_PACK_THRESHOLD', 'PIPELINE_BOX_CAPACITY']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('masterdata', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=CREATE_GLOBAL_CONFIG_IF_NOT_EXISTS_SQL,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name='GlobalConfig',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('config_key', models.CharField(max_length=64, unique=True, verbose_name='配置项名称')),
                        ('config_value', models.CharField(max_length=255, verbose_name='配置项值')),
                        ('enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                        ('remark', models.CharField(blank=True, max_length=255, verbose_name='备注')),
                    ],
                    options={
                        'db_table': 'global_config',
                        'verbose_name': '全局配置',
                        'verbose_name_plural': '全局配置',
                    },
                ),
            ],
        ),
        migrations.RunSQL(sql=OBSOLETE_TABLES_SQL, reverse_sql=migrations.RunSQL.noop),
        migrations.RunPython(seed_global_configs, unseed_global_configs),
    ]
