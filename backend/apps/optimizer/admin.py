from django.contrib import admin

from .models import GlobalConfig


@admin.register(GlobalConfig)
class GlobalConfigAdmin(admin.ModelAdmin):
    list_display = ('config_key', 'config_value', 'enabled')
    search_fields = ('config_key', 'remark')
    list_filter = ('enabled',)
