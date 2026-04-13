from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import RunResultSummary, SortedOrderResult


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


@admin.register(SortedOrderResult)
class SortedOrderResultAdmin(admin.ModelAdmin):
    list_display = (
        'seq_no',
        'final_position',
        'sort_change',
        'remark',
        'order_date',
        'batch_link',
        'order',
        'organization',
        'route',
        'est_total_seconds',
        'est_start_time',
        'est_finish_time',
    )
    list_filter = ('order_date', 'batch__optimize_mode', 'route', 'batch')
    search_fields = (
        'batch__batch_no',
        'order__order_no',
        'organization__organization_no',
        'organization__organization_name',
        'route__route_no',
        'remark',
    )
    ordering = ('-order_date', 'final_position', 'seq_no')
    list_select_related = ('batch', 'order', 'organization', 'route')

    @admin.display(description='运行批次')
    def batch_link(self, obj):
        url = reverse('admin:runs_runresultsummary_change', args=[obj.batch_id])
        return format_html('<a href="{}">{}</a>', url, obj.batch.batch_no)

    @admin.display(description='排序变化')
    def sort_change(self, obj):
        delta = obj.seq_no - obj.final_position
        if delta > 0:
            return f'↑提前 {delta} 位'
        if delta < 0:
            return f'↓延后 {abs(delta)} 位'
        return '→不变'
