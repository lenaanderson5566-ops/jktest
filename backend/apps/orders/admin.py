from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from django.contrib import admin, messages
from django.db import IntegrityError
from django.db.models import Sum
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.urls import path, reverse
from openpyxl import Workbook, load_workbook

from apps.masterdata.models import CurrencyType, DenominationPackagingSpec, GlobalConfig, Organization, TransportRoute
from .models import (
    ManualPackTask,
    OrderImportBatch,
    OrderSplitDetail,
    OrderStatus,
    OrganizationOrder,
    PipelineBoxTask,
    SplitType,
)


class OrganizationOrderInline(admin.TabularInline):
    model = OrganizationOrder
    extra = 0
    fields = ('line_no', 'organization', 'route', 'currency_type', 'denomination', 'quantity', 'status', 'remark')
    readonly_fields = fields
    can_delete = False


class OrderSplitDetailInline(admin.TabularInline):
    model = OrderSplitDetail
    extra = 0
    fields = ('split_type', 'seq_no', 'bundle_count')
    readonly_fields = fields
    can_delete = False


@admin.register(OrderImportBatch)
class OrderImportBatchAdmin(admin.ModelAdmin):
    list_display = ('order_no', 'order_date', 'source_filename', 'total_rows', 'created_at')
    search_fields = ('order_no', 'source_filename')
    list_filter = ('order_date', 'created_at')
    inlines = [OrganizationOrderInline]


@admin.register(ManualPackTask)
class ManualPackTaskAdmin(admin.ModelAdmin):
    list_display = ('order_no', 'order_date', 'organization_no', 'organization_name', 'denomination', 'bundle_count')
    list_filter = ('order__order_date', 'order__organization', 'order__denomination')
    search_fields = ('order__order_no', 'order__organization__org_no', 'order__organization__org_name')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return ManualPackTask.objects.select_related('order', 'order__organization')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('export-excel/', self.admin_site.admin_view(self.export_excel), name='orders_manual_pack_export'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'excel_export_url': reverse('admin:orders_manual_pack_export'),
        })
        return super().changelist_view(request, extra_context)

    @staticmethod
    def order_no(obj):
        return obj.order.order_no

    @staticmethod
    def order_date(obj):
        return obj.order.order_date

    @staticmethod
    def organization_no(obj):
        return obj.order.organization.org_no

    @staticmethod
    def organization_name(obj):
        return obj.order.organization.org_name

    @staticmethod
    def denomination(obj):
        return obj.order.denomination

    def export_excel(self, request):
        rows = (
            OrderSplitDetail.objects.filter(split_type=SplitType.MANUAL_PACK)
            .values('order__order_date', 'order__organization__org_no', 'order__organization__org_name', 'order__denomination')
            .annotate(total_bundles=Sum('bundle_count'))
            .order_by('order__order_date', 'order__organization__org_no', 'order__denomination')
        )
        wb = Workbook()
        ws = wb.active
        ws.title = '人工清单'
        ws.append(['订单日期', '机构号', '机构名称', '面额', '人工捆数汇总'])
        for row in rows:
            ws.append([
                row['order__order_date'],
                row['order__organization__org_no'],
                row['order__organization__org_name'],
                str(row['order__denomination']),
                int(row['total_bundles'] or 0),
            ])
        return OrganizationOrderAdmin._wb_response(wb, 'manual_pack_summary.xlsx')


@admin.register(PipelineBoxTask)
class PipelineBoxTaskAdmin(admin.ModelAdmin):
    list_display = ('order_no', 'order_date', 'organization_no', 'route_no', 'denomination', 'seq_no', 'bundle_count')
    list_filter = ('order__order_date', 'order__route', 'order__organization', 'order__denomination')
    search_fields = ('order__order_no', 'order__organization__org_no', 'order__route__route_no')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return PipelineBoxTask.objects.select_related('order', 'order__organization', 'order__route')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('export-excel/', self.admin_site.admin_view(self.export_excel), name='orders_pipeline_box_export'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'excel_export_url': reverse('admin:orders_pipeline_box_export'),
        })
        return super().changelist_view(request, extra_context)

    @staticmethod
    def order_no(obj):
        return obj.order.order_no

    @staticmethod
    def order_date(obj):
        return obj.order.order_date

    @staticmethod
    def organization_no(obj):
        return obj.order.organization.org_no

    @staticmethod
    def route_no(obj):
        return obj.order.route.route_no

    @staticmethod
    def denomination(obj):
        return obj.order.denomination

    def export_excel(self, request):
        qs = PipelineBoxTask.objects.select_related('order', 'order__organization', 'order__route').order_by(
            'order__order_date', 'order__order_no', 'order__organization__org_no', 'order__denomination', 'seq_no'
        )
        wb = Workbook()
        ws = wb.active
        ws.title = '流水线箱清单'
        ws.append(['订单编号', '订单日期', '机构号', '线路号', '面额', '箱序号', '箱内捆数'])
        for row in qs:
            ws.append([
                row.order.order_no,
                row.order.order_date,
                row.order.organization.org_no,
                row.order.route.route_no,
                str(row.order.denomination),
                row.seq_no,
                row.bundle_count,
            ])
        return OrganizationOrderAdmin._wb_response(wb, 'pipeline_box_list.xlsx')


@admin.register(OrganizationOrder)
class OrganizationOrderAdmin(admin.ModelAdmin):
    change_list_template = 'admin/excel_change_list.html'
    list_display = ('order_no', 'order_date', 'organization', 'route', 'currency_type', 'denomination', 'quantity', 'status')
    search_fields = ('order_no', 'organization__org_no', 'organization__org_name')
    list_filter = ('order_date', 'route', 'status', 'currency_type', 'denomination')
    inlines = [OrderSplitDetailInline]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-excel/', self.admin_site.admin_view(self.import_excel), name='orders_order_import'),
            path('export-excel/', self.admin_site.admin_view(self.export_excel), name='orders_order_export'),
            path('template-excel/', self.admin_site.admin_view(self.template_excel), name='orders_order_template'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'excel_import_url': reverse('admin:orders_order_import'),
            'excel_export_url': reverse('admin:orders_order_export'),
            'excel_template_url': reverse('admin:orders_order_template'),
        })
        return super().changelist_view(request, extra_context)

    def import_excel(self, request):
        if request.method == 'POST' and request.FILES.get('file'):
            try:
                self._import_long(request.FILES['file'])
                messages.success(request, '订单导入长表导入成功')
            except Exception as exc:  # noqa: BLE001
                messages.error(request, f'订单导入失败: {exc}')
            return redirect('..')

        token = get_token(request)
        return HttpResponse(
            '<h3>订单导入 Excel 导入（长表）</h3>'
            '<form method="post" enctype="multipart/form-data">'
            f'<input type="hidden" name="csrfmiddlewaretoken" value="{token}" />'
            '<input type="file" name="file" accept=".xlsx" required />'
            '<button type="submit">上传并导入</button>'
            '</form>'
        )

    @classmethod
    def _import_long(cls, file_obj):
        wb = load_workbook(file_obj)
        ws = wb.active
        headers = [str(v).strip() if v is not None else '' for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
        idx = {name: i for i, name in enumerate(headers)}
        required = {'订单日期', '机构号', '线路号', '面额'}
        if not required.issubset(set(headers)):
            raise ValueError('请使用系统提供的长表模板导入')

        batch_order_date = None
        details: list[dict] = []
        for row_no, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            try:
                if not row:
                    continue

                order_date = _to_date(row[idx['订单日期']])
                if batch_order_date is None:
                    batch_order_date = order_date
                elif order_date != batch_order_date:
                    raise ValueError('同一份Excel仅支持一个订单日期，请按日期拆分导入')
                org_no = str(row[idx['机构号']] or '').strip()
                route_no = str(row[idx['线路号']] or '').strip()
                if not org_no or not route_no:
                    continue
                org = Organization.objects.filter(org_no=org_no).first()
                route = TransportRoute.objects.filter(route_no=route_no).first()
                if not org:
                    raise ValueError(f'找不到机构号: {org_no}')
                if not route:
                    raise ValueError(f'找不到线路号: {route_no}')

                denom = Decimal(_normalize_denomination(row[idx['面额']]))
                currency_type = CurrencyType.COIN if denom < Decimal('5') else CurrencyType.BANKNOTE
                qty = _resolve_quantity_from_row(str(denom), row[idx.get('数量')] if idx.get('数量') is not None else None,
                                                 row[idx.get('金额')] if idx.get('金额') is not None else None)
                remark = str(row[idx.get('备注')] or '').strip() if idx.get('备注') is not None else ''
                details.append(
                    {
                        'line_no': row_no,
                        'order_date': order_date,
                        'organization': org,
                        'route': route,
                        'currency_type': currency_type,
                        'denomination': denom,
                        'quantity': qty,
                        'status': OrderStatus.NEW,
                        'remark': remark,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f'长表第{row_no}行导入失败：{exc}') from exc

        if not details:
            raise ValueError('未解析到可导入的订单明细')

        order_date = details[0]['order_date']
        order_no = _next_order_no(order_date)
        batch = OrderImportBatch.objects.create(
            order_no=order_no,
            order_date=order_date,
            source_filename=getattr(file_obj, 'name', ''),
            total_rows=len(details),
        )
        created_orders = []
        for detail in details:
            try:
                created_order = OrganizationOrder.objects.create(
                    import_batch=batch,
                    line_no=detail['line_no'],
                    order_no=order_no,
                    order_date=detail['order_date'],
                    organization=detail['organization'],
                    route=detail['route'],
                    currency_type=detail['currency_type'],
                    denomination=detail['denomination'],
                    quantity=detail['quantity'],
                    status=OrderStatus.NEW,
                    remark=detail['remark'],
                )
                created_orders.append(created_order)
            except IntegrityError as exc:
                if 'organization_order_order_no_currency_type' in str(exc):
                    raise ValueError(
                        '检测到旧版唯一索引(order_no+currency_type+denomination)。'
                        '请先执行数据库迁移: python manage.py migrate orders 0002'
                    ) from exc
                raise
        _rebuild_batch_splits(created_orders)

    def export_excel(self, request):
        wb = Workbook()
        ws = wb.active
        ws.title = '长表导出'
        ws.append(['订单编号', '订单日期', '机构号', '线路号', '面额', '数量', '订单状态', '备注'])

        qs = OrganizationOrder.objects.select_related('organization', 'route').order_by('order_date', 'order_no', 'denomination')
        for row in qs:
            ws.append([
                row.order_no,
                row.order_date,
                row.organization.org_no,
                row.route.route_no,
                str(row.denomination),
                row.quantity,
                row.status,
                row.remark,
            ])

        return self._wb_response(wb, 'organization_order_export_long.xlsx')

    def template_excel(self, request):
        wb = Workbook()
        ws = wb.active
        ws.title = '长表样例'
        ws.append(['订单日期', '机构号', '线路号', '面额', '数量', '金额', '备注'])
        ws.append(['2026-04-10', 'ORG001', 'R001', 100, 10, '', '长表数量样例'])
        ws.append(['2026-04-10', 'ORG001', 'R001', 0.5, '', 500, '长表金额样例'])
        return self._wb_response(wb, 'organization_order_template_long.xlsx')

    @staticmethod
    def _wb_response(wb, filename):
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response


def _to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), '%Y-%m-%d').date()


def _normalize_denomination(value) -> str:
    d = Decimal(str(value)).normalize()
    txt = format(d, 'f')
    if '.' in txt:
        txt = txt.rstrip('0').rstrip('.')
    return txt if txt else '0'


def _resolve_quantity_from_row(denom_text: str, qty_raw, amount_raw) -> int:
    if qty_raw not in (None, ''):
        return int(qty_raw)
    if amount_raw in (None, ''):
        raise ValueError(f'面额 {denom_text} 未填写数量或金额')

    denomination = Decimal(denom_text)
    currency_type = CurrencyType.COIN if denomination < Decimal('5') else CurrencyType.BANKNOTE
    spec = DenominationPackagingSpec.objects.filter(
        currency_type=currency_type,
        denomination=denomination,
        enabled=True,
    ).first()
    if not spec:
        raise ValueError(f'面额 {denom_text} 缺少启用的面额封装规格')

    units = int(spec.units_per_package)
    if units <= 0:
        raise ValueError(f'面额 {denom_text} 封装规格单位必须大于0')

    amount = _to_decimal(amount_raw)
    qty = amount / (denomination * units)
    if qty != qty.to_integral_value():
        raise ValueError(f'面额 {denom_text} 金额 {amount_raw} 不能换算为整数包(捆)数')
    return int(qty)


def _to_decimal(value) -> Decimal:
    normalized = str(value).replace(',', '').strip()
    return Decimal(normalized)


def _next_order_no(order_date: date) -> str:
    date_prefix = order_date.strftime('%Y%m%d')
    prefix = f'ORD{date_prefix}-'
    max_no = 0
    for order_no in OrderImportBatch.objects.filter(order_no__startswith=prefix).values_list('order_no', flat=True):
        suffix = order_no.replace(prefix, '', 1)
        if suffix.isdigit():
            max_no = max(max_no, int(suffix))
    return f'{prefix}{max_no + 1:03d}'


def _rebuild_batch_splits(orders: list[OrganizationOrder]) -> None:
    manual_threshold = _int_config('MANUAL_PACK_THRESHOLD', 20)
    box_capacity = _int_config('PIPELINE_BOX_CAPACITY', 16)

    grouped: dict[tuple[str, object, int, int], list[OrganizationOrder]] = {}
    for order in orders:
        order.split_details.all().delete()
        group_key = (order.order_no, order.order_date, order.organization_id, order.route_id)
        grouped.setdefault(group_key, []).append(order)

    for _, group_orders in grouped.items():
        pipeline_remain: list[tuple[OrganizationOrder, int]] = []
        for order in group_orders:
            total_qty = int(order.quantity)
            if order.currency_type != CurrencyType.BANKNOTE:
                pipeline_remain.append((order, total_qty))
                continue

            manual_qty = (total_qty // manual_threshold) * manual_threshold
            remain_qty = total_qty - manual_qty
            for i in range(manual_qty // manual_threshold):
                OrderSplitDetail.objects.create(
                    order=order,
                    split_type=SplitType.MANUAL_PACK,
                    seq_no=i + 1,
                    bundle_count=manual_threshold,
                )
            pipeline_remain.append((order, remain_qty))

        box_seq = 1
        capacity_left = box_capacity
        for order, remain in sorted(pipeline_remain, key=lambda item: item[0].denomination, reverse=True):
            while remain > 0:
                if capacity_left == 0:
                    box_seq += 1
                    capacity_left = box_capacity
                bundles = min(remain, capacity_left)
                OrderSplitDetail.objects.create(
                    order=order,
                    split_type=SplitType.PIPELINE_BOX,
                    seq_no=box_seq,
                    bundle_count=bundles,
                )
                remain -= bundles
                capacity_left -= bundles


def _int_config(key: str, default: int) -> int:
    row = GlobalConfig.objects.filter(config_key=key, enabled=True).first()
    if not row:
        return default
    try:
        value = int(str(row.config_value).strip())
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default
