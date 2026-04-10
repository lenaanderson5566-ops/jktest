from django.contrib import admin

from .models import GlobalConfig, OptimizeMode, OptimizeModeParameter


@admin.register(OptimizeMode)
class OptimizeModeAdmin(admin.ModelAdmin):
    list_display = ('mode_no', 'mode_name', 'mode_type', 'enabled')
    search_fields = ('mode_no', 'mode_name')


@admin.register(OptimizeModeParameter)
class OptimizeModeParameterAdmin(admin.ModelAdmin):
    list_display = ('mode', 'category', 'station', 'value', 'enabled')
    list_filter = ('mode', 'category', 'enabled')


@admin.register(GlobalConfig)
class GlobalConfigAdmin(admin.ModelAdmin):
    list_display = ('config_key', 'config_value', 'enabled')
    search_fields = ('config_key',)
