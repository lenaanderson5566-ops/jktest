from django.core.management.base import BaseCommand, CommandError

from apps.optimizer.services.sorter import run_sorting_for_date


class Command(BaseCommand):
    help = '执行指定日期订单排序计算，并写入排序结果表'

    def add_arguments(self, parser):
        parser.add_argument('--order-date', required=True, help='订单日期，格式 YYYY-MM-DD')
        parser.add_argument('--mode-no', required=False, help='优化模式编号（可选）')

    def handle(self, *args, **options):
        try:
            summary = run_sorting_for_date(options['order_date'], options.get('mode_no'))
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(
            f"排序完成: batch={summary['batch_no']}, total_seconds={summary['total_seconds']}, score={summary['score']}"
        ))
