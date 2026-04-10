from uuid import uuid4

from django.contrib import admin, messages
from django.utils import timezone

from .models import SortingJob, SortingJobStatus
from .services.job_runner import start_sorting_job_in_background


@admin.action(description='将选中任务放入后台执行')
def run_jobs_in_background(modeladmin, request, queryset):
    candidates = queryset.filter(status__in=[SortingJobStatus.PENDING, SortingJobStatus.FAILED])
    count = 0
    for job in candidates:
        start_sorting_job_in_background(job.id)
        count += 1
    messages.success(request, f'已启动 {count} 个后台排序任务。')


@admin.register(SortingJob)
class SortingJobAdmin(admin.ModelAdmin):
    list_display = (
        'job_no', 'order_date', 'mode', 'status', 'result_batch_no', 'started_at', 'finished_at', 'created_at'
    )
    list_filter = ('status', 'order_date', 'mode')
    search_fields = ('job_no', 'result_batch_no', 'message')
    readonly_fields = ('status', 'result_batch_no', 'message', 'started_at', 'finished_at', 'created_at', 'updated_at')
    actions = [run_jobs_in_background]

    fieldsets = (
        ('任务配置', {'fields': ('job_no', 'order_date', 'mode')}),
        ('运行结果', {'fields': ('status', 'result_batch_no', 'message', 'started_at', 'finished_at')}),
        ('系统字段', {'fields': ('created_at', 'updated_at')}),
    )

    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None
        if not obj.job_no:
            obj.job_no = f'JOB-{timezone.now().strftime("%Y%m%d%H%M%S")}-{str(uuid4())[:8]}'
        super().save_model(request, obj, form, change)
        if is_new and obj.status == SortingJobStatus.PENDING:
            start_sorting_job_in_background(obj.id)
            messages.info(request, f'任务 {obj.job_no} 已提交后台执行。')
