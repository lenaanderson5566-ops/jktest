from django.contrib import admin

from .models import GlobalConfig, OptimizeMode, OptimizeModeParameter

admin.site.register(OptimizeMode)
admin.site.register(OptimizeModeParameter)
admin.site.register(GlobalConfig)
