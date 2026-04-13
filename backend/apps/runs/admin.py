from django.contrib import admin
from django.db.models import Max, Min

from .models import RunResultStationDetail, RunResultSummary, SortedOrderResult


class RunResultStationDetailInline(admin.TabularInline):
    model = RunResultStationDetail
    extra = 0
    can_delete = False
    fields = ('station', 'station_span', 'busy_seconds', 'idle_seconds', 'wait_seconds')
    readonly_fields = fields
    ordering = ('station__station_order',)


class SortedOrderResultInline(admin.TabularInline):
    model = SortedOrderResult
    extra = 0
    can_delete = False
    fields = (
        'seq_no',
        'order',
        'organization',
        'route',
        'est_start_time',
        'est_finish_time',
        'est_total_seconds',
    )
    readonly_fields = fields
    ordering = ('seq_no',)
    show_change_link = True


@admin.register(RunResultSummary)
class RunResultSummaryAdmin(admin.ModelAdmin):
    list_display = (
        'batch_no',
        'run_at',
        'optimize_mode',
        'total_seconds',
        'score',
        'order_count_display',
        'time_window_display',
        'is_best',
    )
    list_filter = ('is_best', 'optimize_mode', 'run_at')
    search_fields = ('batch_no', 'optimize_mode__mode_no', 'optimize_mode__mode_name')
    ordering = ('-run_at',)
    date_hierarchy = 'run_at'
    readonly_fields = ('batch_no', 'run_at', 'optimize_mode', 'total_seconds', 'score', 'is_best', 'remark')
    inlines = (RunResultStationDetailInline, SortedOrderResultInline)

    @admin.display(description='订单数')
    def order_count_display(self, obj: RunResultSummary) -> int:
        return obj.sorted_orders.count()

    @admin.display(description='预计执行窗口')
    def time_window_display(self, obj: RunResultSummary) -> str:
        window = obj.sorted_orders.aggregate(start=Min('est_start_time'), finish=Max('est_finish_time'))
        if not window['start'] or not window['finish']:
            return '-'
        return f"{window['start']:%H:%M:%S} ~ {window['finish']:%H:%M:%S}"


@admin.register(RunResultStationDetail)
class RunResultStationDetailAdmin(admin.ModelAdmin):
    list_display = ('batch', 'station', 'station_span', 'busy_seconds', 'idle_seconds', 'wait_seconds')
    list_filter = ('station', 'batch__optimize_mode')
    search_fields = ('batch__batch_no', 'station__station_name', 'station__station_no')
    ordering = ('-batch__run_at', 'station__station_order')


@admin.register(SortedOrderResult)
class SortedOrderResultAdmin(admin.ModelAdmin):
    list_display = (
        'batch',
        'seq_no',
        'order',
        'organization',
        'route',
        'est_start_time',
        'est_finish_time',
        'est_total_seconds',
    )
    list_filter = ('order_date', 'route', 'batch__optimize_mode')
    search_fields = ('batch__batch_no', 'order__order_no', 'organization__org_name', 'route__route_name')
    ordering = ('-batch__run_at', 'seq_no')
