from django.contrib import admin
from django.urls import path

from apps.masterdata.admin import pipeline_overview_page, pipeline_strategy_export_page

urlpatterns = [
    path('admin/overview/', admin.site.admin_view(lambda request: pipeline_overview_page(request, admin.site)), name='admin_overview'),
    path('admin/overview/strategy-export/', admin.site.admin_view(lambda request: pipeline_strategy_export_page(request, admin.site)), name='admin_strategy_export'),
    path('admin/', admin.site.urls),
]
