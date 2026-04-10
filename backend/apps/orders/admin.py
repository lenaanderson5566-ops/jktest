from __future__ import annotations

from io import BytesIO

from django.contrib import admin, messages
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.urls import path, reverse
from openpyxl import Workbook, load_workbook

from apps.masterdata.models import Organization, TransportRoute
from .models import OrganizationOrder


@admin.register(OrganizationOrder)
class OrganizationOrderAdmin(admin.ModelAdmin):
    change_list_template = 'admin/excel_change_list.html'
    list_display = ('order_no', 'order_date', 'organization', 'route', 'status')
    search_fields = ('order_no', 'organization__org_no', 'organization__org_name')
    list_filter = ('order_date', 'route', 'status')

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
                self._handle_upload(request.FILES['file'])
                messages.success(request, '机构订单导入成功')
            except Exception as exc:  # noqa: BLE001
                messages.error(request, f'机构订单导入失败: {exc}')
            return redirect('..')

        token = get_token(request)
        return HttpResponse(
            '<h3>机构订单 Excel 导入</h3>'
            '<form method="post" enctype="multipart/form-data">'
            f'<input type="hidden" name="csrfmiddlewaretoken" value="{token}" />'
            '<input type="file" name="file" accept=".xlsx" required />'
            '<button type="submit">上传并导入</button>'
            '</form>'
        )

    @staticmethod
    def _handle_upload(file_obj):
        wb = load_workbook(file_obj)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            org_no = str(row[2] or '').strip()
            route_no = str(row[3] or '').strip()
            org = Organization.objects.filter(org_no=org_no).first()
            route = TransportRoute.objects.filter(route_no=route_no).first()
            if not org:
                raise ValueError(f'找不到机构号: {org_no}')
            if not route:
                raise ValueError(f'找不到线路号: {route_no}')
            OrganizationOrder.objects.update_or_create(
                order_no=str(row[0]).strip(),
                defaults={
                    'order_date': row[1],
                    'organization': org,
                    'route': route,
                    'qty_100': int(row[4] or 0),
                    'qty_50': int(row[5] or 0),
                    'qty_20': int(row[6] or 0),
                    'qty_10': int(row[7] or 0),
                    'qty_5': int(row[8] or 0),
                    'qty_coin_1': int(row[9] or 0),
                    'qty_coin_05': int(row[10] or 0),
                    'qty_coin_01': int(row[11] or 0),
                    'status': str(row[12] or 'NEW'),
                    'remark': str(row[13] or '').strip(),
                },
            )

    def export_excel(self, request):
        wb = Workbook()
        ws = wb.active
        ws.append([
            '订单编号', '订单日期', '机构号', '线路号',
            '100元捆数', '50元捆数', '20元捆数', '10元捆数', '5元捆数',
            '1元包数', '0.5元包数', '0.1元包数', '订单状态', '备注',
        ])
        for obj in OrganizationOrder.objects.select_related('organization', 'route').all().order_by('order_date', 'order_no'):
            ws.append([
                obj.order_no, obj.order_date, obj.organization.org_no, obj.route.route_no,
                obj.qty_100, obj.qty_50, obj.qty_20, obj.qty_10, obj.qty_5,
                obj.qty_coin_1, obj.qty_coin_05, obj.qty_coin_01, obj.status, obj.remark,
            ])
        return self._wb_response(wb, 'organization_order_export.xlsx')

    def template_excel(self, request):
        wb = Workbook()
        ws = wb.active
        ws.append([
            '订单编号', '订单日期', '机构号', '线路号',
            '100元捆数', '50元捆数', '20元捆数', '10元捆数', '5元捆数',
            '1元包数', '0.5元包数', '0.1元包数', '订单状态', '备注',
        ])
        ws.append(['ORD20260410001', '2026-04-10', 'ORG001', 'R001', 10, 2, 0, 0, 1, 0, 0, 0, 'NEW', '样例订单'])
        return self._wb_response(wb, 'organization_order_template.xlsx')

    @staticmethod
    def _wb_response(wb, filename):
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response
