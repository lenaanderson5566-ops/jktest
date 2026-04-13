from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from django.contrib import admin, messages
from django.db import IntegrityError
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.urls import path, reverse
from openpyxl import Workbook, load_workbook

from apps.masterdata.models import CurrencyType, DenominationPackagingSpec, Organization, TransportRoute
from .models import OrderStatus, OrganizationOrder


@admin.register(OrganizationOrder)
class OrganizationOrderAdmin(admin.ModelAdmin):
    change_list_template = 'admin/excel_change_list.html'
    list_display = ('order_no', 'order_date', 'organization', 'route', 'currency_type', 'denomination', 'quantity', 'status')
    search_fields = ('order_no', 'organization__org_no', 'organization__org_name')
    list_filter = ('order_date', 'route', 'status', 'currency_type', 'denomination')

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
                messages.success(request, '机构订单长表导入成功')
            except Exception as exc:  # noqa: BLE001
                messages.error(request, f'机构订单导入失败: {exc}')
            return redirect('..')

        token = get_token(request)
        return HttpResponse(
            '<h3>机构订单 Excel 导入（长表）</h3>'
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

                order_no = _system_order_no(order_date)

                denom = Decimal(_normalize_denomination(row[idx['面额']]))
                currency_type = CurrencyType.COIN if denom < Decimal('5') else CurrencyType.BANKNOTE
                qty = _resolve_quantity_from_row(str(denom), row[idx.get('数量')] if idx.get('数量') is not None else None,
                                                 row[idx.get('金额')] if idx.get('金额') is not None else None)
                remark = str(row[idx.get('备注')] or '').strip() if idx.get('备注') is not None else ''

                try:
                    OrganizationOrder.objects.update_or_create(
                        order_no=order_no,
                        order_date=order_date,
                        organization=org,
                        route=route,
                        currency_type=currency_type,
                        denomination=denom,
                        defaults={
                            'quantity': qty,
                            'status': OrderStatus.NEW,
                            'remark': remark,
                        },
                    )
                except IntegrityError as exc:
                    if 'organization_order_order_no_currency_type' in str(exc):
                        raise ValueError(
                            '检测到旧版唯一索引(order_no+currency_type+denomination)。'
                            '请先执行数据库迁移: python manage.py migrate orders 0002'
                        ) from exc
                    raise
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f'长表第{row_no}行导入失败：{exc}') from exc

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


def _system_order_no(order_date: date) -> str:
    return f'ORD{order_date.strftime("%Y%m%d")}'
