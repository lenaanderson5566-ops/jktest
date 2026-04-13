from django.contrib import admin
from django.db.models import Max, Min
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.html import format_html

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
        'board_link',
        'is_best',
    )
    list_filter = ('is_best', 'optimize_mode', 'run_at')
    search_fields = ('batch_no', 'optimize_mode__mode_no', 'optimize_mode__mode_name')
    ordering = ('-run_at',)
    date_hierarchy = 'run_at'
    readonly_fields = ('batch_no', 'run_at', 'optimize_mode', 'total_seconds', 'score', 'is_best', 'remark')
    inlines = (RunResultStationDetailInline, SortedOrderResultInline)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:summary_id>/board/',
                self.admin_site.admin_view(self.board_view),
                name='runs_runresultsummary_board',
            ),
        ]
        return custom_urls + urls

    @admin.display(description='订单数')
    def order_count_display(self, obj: RunResultSummary) -> int:
        return obj.sorted_orders.count()

    @admin.display(description='预计执行窗口')
    def time_window_display(self, obj: RunResultSummary) -> str:
        window = obj.sorted_orders.aggregate(start=Min('est_start_time'), finish=Max('est_finish_time'))
        if not window['start'] or not window['finish']:
            return '-'
        return f"{window['start']:%H:%M:%S} ~ {window['finish']:%H:%M:%S}"

    @admin.display(description='结果看板')
    def board_link(self, obj: RunResultSummary):
        url = reverse('admin:runs_runresultsummary_board', args=[obj.id])
        return format_html('<a href="{}">查看看板</a>', url)

    def board_view(self, request, summary_id: int):
        summary = get_object_or_404(
            RunResultSummary.objects.select_related('optimize_mode'),
            pk=summary_id,
        )
        station_details = list(
            summary.station_details.select_related('station').order_by('station__station_order')
        )
        sorted_orders = list(
            summary.sorted_orders.select_related('order', 'organization', 'route').order_by('seq_no')
        )

        route_stats = {}
        for item in sorted_orders:
            stat = route_stats.setdefault(
                item.route_id,
                {
                    'route': item.route,
                    'count': 0,
                    'start': item.est_start_time,
                    'finish': item.est_finish_time,
                    'seconds': 0.0,
                },
            )
            stat['count'] += 1
            stat['start'] = min(stat['start'], item.est_start_time)
            stat['finish'] = max(stat['finish'], item.est_finish_time)
            stat['seconds'] += float(item.est_total_seconds)

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'summary': summary,
            'station_details': station_details,
            'sorted_orders': sorted_orders,
            'route_stats': sorted(route_stats.values(), key=lambda item: item['count'], reverse=True),
            'title': f'排序结果看板 - {summary.batch_no}',
        }
        return render(request, 'admin/runs/runresultsummary/board.html', context)


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
