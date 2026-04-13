from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import RunResultStationDetail, RunResultSummary, SortedOrderResult


@admin.register(RunResultSummary)
class RunResultSummaryAdmin(admin.ModelAdmin):
    list_display = (
        'batch_no',
        'run_at',
        'optimize_mode',
        'score',
        'total_seconds',
        'is_best',
        'sorted_order_count',
    )
    list_filter = ('is_best', 'optimize_mode', 'run_at')
    search_fields = ('batch_no', 'remark')
    ordering = ('-run_at',)
    readonly_fields = ('batch_no', 'run_at', 'score', 'total_seconds')

    @admin.display(description='排序订单数')
    def sorted_order_count(self, obj):
        return obj.sorted_orders.count()


@admin.register(RunResultStationDetail)
class RunResultStationDetailAdmin(admin.ModelAdmin):
    list_display = (
        'batch',
        'station',
        'station_span',
        'busy_seconds',
        'idle_seconds',
        'wait_seconds',
    )
    list_filter = ('station', 'batch__optimize_mode', 'batch__run_at')
    search_fields = ('batch__batch_no', 'station__station_no', 'station__station_name')
    ordering = ('-batch__run_at', 'station_id')


@admin.register(SortedOrderResult)
class SortedOrderResultAdmin(admin.ModelAdmin):
    list_display = (
        'seq_no',
        'order_date',
        'batch_link',
        'organization',
        'route',
        'final_position',
        'est_total_seconds',
        'est_start_time',
        'est_finish_time',
    )
    list_filter = ('order_date', 'batch__optimize_mode', 'route')
    search_fields = (
        'batch__batch_no',
        'order__order_no',
        'organization__organization_no',
        'organization__organization_name',
        'route__route_no',
    )
    ordering = ('-order_date', 'final_position', 'seq_no')
    list_select_related = ('batch', 'order', 'organization', 'route')

    @admin.display(description='运行批次')
    def batch_link(self, obj):
        url = reverse('admin:runs_runresultsummary_change', args=[obj.batch_id])
        return format_html('<a href="{}">{}</a>', url, obj.batch.batch_no)
