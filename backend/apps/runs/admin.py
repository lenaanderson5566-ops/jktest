from django.contrib import admin
from datetime import timedelta

from .models import SortedOrderResult


@admin.register(SortedOrderResult)
class SortedOrderResultAdmin(admin.ModelAdmin):
    list_display = (
        'seq_no',
        'final_position',
        'sort_change',
        'remark',
        'order_date',
        'batch_no',
        'optimize_mode',
        'order',
        'organization',
        'route',
        'box_track_duration',
        'est_start_duration',
        'est_finish_duration',
        'est_total_seconds',
    )
    list_filter = ('order_date', 'optimize_mode', 'route', 'batch_no')
    search_fields = (
        'batch_no',
        'order__order_no',
        'organization__organization_no',
        'organization__organization_name',
        'route__route_no',
        'remark',
    )
    ordering = ('-order_date', 'final_position', 'seq_no')
    list_select_related = ('optimize_mode', 'order', 'organization', 'route')

    @admin.display(description='排序变化')
    def sort_change(self, obj):
        delta = obj.seq_no - obj.final_position
        if delta > 0:
            return f'↑提前 {delta} 位'
        if delta < 0:
            return f'↓延后 {abs(delta)} 位'
        return '→不变'

    @staticmethod
    def _format_hms(seconds: float) -> str:
        total = max(0, int(round(seconds)))
        hour = total // 3600
        minute = (total % 3600) // 60
        sec = total % 60
        return f'{hour:02d}:{minute:02d}:{sec:02d}'

    @admin.display(description='在轨时长(HH:MM:SS)')
    def box_track_duration(self, obj):
        if not obj.est_start_time or not obj.est_finish_time:
            return '-'
        return self._format_hms((obj.est_finish_time - obj.est_start_time).total_seconds())

    @admin.display(description='预计开始时长(HH:MM:SS)')
    def est_start_duration(self, obj):
        if not obj.est_start_time or not obj.est_finish_time or obj.est_total_seconds is None:
            return '-'
        batch_start = obj.est_finish_time - timedelta(seconds=float(obj.est_total_seconds))
        return self._format_hms((obj.est_start_time - batch_start).total_seconds())

    @admin.display(description='预计结束时长(HH:MM:SS)')
    def est_finish_duration(self, obj):
        if obj.est_total_seconds is None:
            return '-'
        return self._format_hms(float(obj.est_total_seconds))
