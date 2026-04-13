from django.db import models


class GlobalConfig(models.Model):
    config_key = models.CharField('配置项名称', max_length=64, unique=True)
    config_value = models.CharField('配置项值', max_length=255)
    enabled = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True)

    class Meta:
        db_table = 'global_config'
        verbose_name = '全局配置'
        verbose_name_plural = verbose_name
