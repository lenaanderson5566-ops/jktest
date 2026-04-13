from django.contrib import admin

from .models import RunResultStationDetail, RunResultSummary, SortedOrderResult

admin.site.register(RunResultSummary)
admin.site.register(RunResultStationDetail)
admin.site.register(SortedOrderResult)
