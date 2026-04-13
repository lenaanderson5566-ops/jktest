from django.contrib import admin

from .models import OptimizeMode, OptimizeModeParameter


@admin.register(OptimizeMode)
class OptimizeModeAdmin(admin.ModelAdmin):
    list_display = ('mode_no', 'mode_name', 'mode_type', 'enabled')
    search_fields = ('mode_no', 'mode_name')


@admin.register(OptimizeModeParameter)
class OptimizeModeParameterAdmin(admin.ModelAdmin):
    list_display = ('mode', 'category', 'station', 'value', 'enabled')
    list_filter = ('mode', 'category', 'enabled')
