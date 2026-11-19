"""
Excel generator module for the automated report builder.
Creates a multi-sheet Excel workbook with KPI summary, monthly trends,
and overdue receivables details.
"""

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, BarChart, Reference
from openpyxl.chart.axis import DateAxis
from datetime import date, datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import logging

# Handle both module and direct execution
try:
    from .data_fetcher import format_value, get_kpi_metadata
except ImportError:
    from data_fetcher import format_value, get_kpi_metadata

logger = logging.getLogger(__name__)

# Style definitions
HEADER_FONT = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
HEADER_FILL = PatternFill(start_color='1B3A5C', end_color='1B3A5C', fill_type='solid')
SUBHEADER_FONT = Font(name='Calibri', bold=True, size=11, color='1B3A5C')
SUBHEADER_FILL = PatternFill(start_color='D6EAF8', end_color='D6EAF8', fill_type='solid')
TITLE_FONT = Font(name='Calibri', bold=True, size=16, color='1B3A5C')
SECTION_FONT = Font(name='Calibri', bold=True, size=13, color='1B3A5C')
NORMAL_FONT = Font(name='Calibri', size=10, color='333333')
BOLD_FONT = Font(name='Calibri', bold=True, size=10, color='333333')
SMALL_FONT = Font(name='Calibri', size=9, color='666666')
FOOTER_FONT = Font(name='Calibri', italic=True, size=8, color='999999')

ALT_ROW_FILL = PatternFill(start_color='EBF5FB', end_color='EBF5FB', fill_type='solid')
WHITE_FILL = PatternFill(start_color='FFFFFF', end_color='FFFFFF', fill_type='solid')
GREEN_FILL = PatternFill(start_color='E8F8F5', end_color='E8F8F5', fill_type='solid')
RED_FILL = PatternFill(start_color='FDEDEC', end_color='FDEDEC', fill_type='solid')
YELLOW_FILL = PatternFill(start_color='FEF9E7', end_color='FEF9E7', fill_type='solid')

THIN_BORDER = Border(
    left=Side(style='thin', color='CCCCCC'),
    right=Side(style='thin', color='CCCCCC'),
    top=Side(style='thin', color='CCCCCC'),
    bottom=Side(style='thin', color='CCCCCC')
)

CENTER_ALIGN = Alignment(horizontal='center', vertical='center', wrap_text=True)
LEFT_ALIGN = Alignment(horizontal='left', vertical='center', wrap_text=True)
RIGHT_ALIGN = Alignment(horizontal='right', vertical='center', wrap_text=True)


def apply_header_style(ws, row: int, max_col: int):
    """Apply header style to a row."""
    for col in range(1, max_col + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER_ALIGN
        cell.border = THIN_BORDER


def apply_cell_style(ws, row: int, col: int, font=NORMAL_FONT, fill=None, align=CENTER_ALIGN, number_format=None):
    """Apply style to a cell."""
    cell = ws.cell(row=row, column=col)
    cell.font = font
    if fill:
        cell.fill = fill
    else:
        # Alternate row coloring
        if row % 2 == 0:
            cell.fill = ALT_ROW_FILL
        else:
            cell.fill = WHITE_FILL
    cell.alignment = align
    cell.border = THIN_BORDER
    if number_format:
        cell.number_format = number_format


def auto_width(ws, min_width=10, max_width=40):
    """Auto-adjust column widths."""
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        adjusted_width = min(max(max_length + 2, min_width), max_width)
        ws.column_dimensions[column].width = adjusted_width


class ExcelReportGenerator:
    """Generates multi-sheet Excel workbook for executive reporting."""

    def __init__(self, report_month: date, data: Dict[str, Any]):
        self.report_month = report_month
        self.data = data
        self.wb = openpyxl.Workbook()
        self.meta = get_kpi_metadata()

    def _write_title_block(self, ws, start_row: int, title: str, subtitle: str = "") -> int:
        """Write title block and return next row."""
        ws.cell(row=start_row, column=1, value="PULSEIQ").font = Font(name='Calibri', bold=True, size=20, color='1B3A5C')
        ws.cell(row=start_row, column=1).alignment = LEFT_ALIGN
        ws.cell(row=start_row+1, column=1, value=title).font = TITLE_FONT
        ws.cell(row=start_row+1, column=1).alignment = LEFT_ALIGN
        if subtitle:
            ws.cell(row=start_row+2, column=1, value=subtitle).font = Font(name='Calibri', size=11, color='2E6DA4')
            ws.cell(row=start_row+2, column=1).alignment = LEFT_ALIGN
            return start_row + 4
        return start_row + 3

    def _write_metadata_block(self, ws, start_row: int) -> int:
        """Write report metadata."""
        meta_items = [
            ('Report Period:', self.report_month.strftime('%B %Y')),
            ('Data Cut-off:', 'September 30, 2026'),
            ('Generated:', datetime.now().strftime('%Y-%m-%d %H:%M')),
            ('Data Source:', 'star_schema.pq15_company_scorecard'),
            ('Classification:', 'Confidential'),
        ]
        row = start_row
        for label, value in meta_items:
            ws.cell(row=row, column=1, value=label).font = BOLD_FONT
            ws.cell(row=row, column=1).alignment = LEFT_ALIGN
            ws.cell(row=row, column=2, value=value).font = NORMAL_FONT
            ws.cell(row=row, column=2).alignment = LEFT_ALIGN
            row += 1
        return row + 1

    def build_kpi_summary_sheet(self):
        """Build the KPI Summary sheet."""
        ws = self.wb.active
        ws.title = "KPI Summary"
        ws.sheet_properties.tabColor = "1B3A5C"

        row = 1
        row = self._write_title_block(ws, row, "Monthly Executive Report - KPI Summary",
                                       f"Reporting Period: {self.report_month.strftime('%B %Y')}")
        row = self._write_metadata_block(ws, row)

        # Current month KPIs
        ws.cell(row=row, column=1, value="CURRENT MONTH KPIs").font = SECTION_FONT
        row += 1

        scorecard = self.data.get('scorecard_current', {})
        prev_scorecard = self.data.get('scorecard_previous', {})
        targets = self.data.get('targets', pd.DataFrame())

        # Convert targets to dict
        target_dict = {}
        if not targets.empty:
            for _, trow in targets.iterrows():
                kpi_name = trow['kpi_name'].lower().replace(' ', '_')
                name_map = {
                    'revenue': 'revenue',
                    'net_profit': 'net_profit',
                    'operating_margin': 'operating_margin_pct',
                    'dso': 'dso_days',
                    'total_headcount': 'total_headcount',
                    'rolling_12m_attrition': 'attrition_rolling_12m_pct',
                    'attendance_rate': 'attendance_rate_pct',
                    'overtime_share': 'overtime_share_pct',
                }
                col = name_map.get(kpi_name, kpi_name)
                target_dict[col] = trow['target_status']

        kpi_order = [
            'revenue', 'net_profit', 'operating_margin_pct', 'dso_days',
            'total_headcount', 'attrition_rolling_12m_pct',
            'attendance_rate_pct', 'overtime_share_pct'
        ]

        # Headers
        headers = ['KPI', 'Current Value', 'Previous Month', 'Change (%)', 'Target Status', 'Direction']
        for col_idx, header in enumerate(headers, 1):
            ws.cell(row=row, column=col_idx, value=header)
        apply_header_style(ws, row, len(headers))
        row += 1

        for kpi_key in kpi_order:
            value = scorecard.get(kpi_key)
            prev_value = prev_scorecard.get(kpi_key)
            meta = self.meta.get(kpi_key, {})
            unit = meta.get('unit', '')
            direction = meta.get('direction', '')
            target_status = target_dict.get(kpi_key, 'Not Set')
            kpi_name = meta.get('name', kpi_key)

            # Format current value
            if value is not None:
                if kpi_key == 'overtime_share_pct':
                    curr_display = value * 100
                    curr_str = f"{curr_display:.2f}%"
                elif kpi_key == 'dso_days':
                    curr_display = value
                    curr_str = f"{curr_display:.2f} days"
                elif unit == 'INR':
                    curr_display = value
                    curr_str = f"₹{curr_display:,.2f}"
                elif unit == '%':
                    curr_display = value
                    curr_str = f"{curr_display:.2f}%"
                elif unit == 'count':
                    curr_display = value
                    curr_str = f"{int(curr_display):,}"
                elif unit == 'days':
                    curr_display = value
                    curr_str = f"{curr_display:.2f} days"
                else:
                    curr_display = value
                    curr_str = str(curr_display)
            else:
                curr_display = None
                curr_str = "N/A"

            # Format previous value
            if prev_value is not None:
                if kpi_key == 'overtime_share_pct':
                    prev_display = prev_value * 100
                    prev_str = f"{prev_display:.2f}%"
                elif kpi_key == 'dso_days':
                    prev_display = prev_value
                    prev_str = f"{prev_display:.2f} days"
                elif unit == 'INR':
                    prev_display = prev_value
                    prev_str = f"₹{prev_display:,.2f}"
                elif unit == '%':
                    prev_display = prev_value
                    prev_str = f"{prev_display:.2f}%"
                elif unit == 'count':
                    prev_display = prev_value
                    prev_str = f"{int(prev_display):,}"
                elif unit == 'days':
                    prev_display = prev_value
                    prev_str = f"{prev_display:.2f} days"
                else:
                    prev_display = prev_value
                    prev_str = str(prev_display)
            else:
                prev_display = None
                prev_str = "N/A"

            # Calculate change
            if curr_display is not None and prev_display is not None and prev_display != 0:
                change_pct = ((curr_display - prev_display) / prev_display) * 100
                change_str = f"{change_pct:+.2f}%"
                # Color coding
                if direction == 'Higher is better':
                    fill = GREEN_FILL if change_pct >= 0 else RED_FILL
                elif direction == 'Lower is better':
                    fill = GREEN_FILL if change_pct <= 0 else RED_FILL
                else:
                    fill = None
            else:
                change_str = "N/A"
                fill = None

            # Write row
            ws.cell(row=row, column=1, value=kpi_name).font = BOLD_FONT
            ws.cell(row=row, column=1).alignment = LEFT_ALIGN
            ws.cell(row=row, column=1).border = THIN_BORDER

            ws.cell(row=row, column=2, value=curr_str).font = NORMAL_FONT
            ws.cell(row=row, column=2).alignment = RIGHT_ALIGN
            ws.cell(row=row, column=2).border = THIN_BORDER

            ws.cell(row=row, column=3, value=prev_str).font = NORMAL_FONT
            ws.cell(row=row, column=3).alignment = RIGHT_ALIGN
            ws.cell(row=row, column=3).border = THIN_BORDER

            ws.cell(row=row, column=4, value=change_str).font = BOLD_FONT
            ws.cell(row=row, column=4).alignment = RIGHT_ALIGN
            ws.cell(row=row, column=4).border = THIN_BORDER
            if fill:
                ws.cell(row=row, column=4).fill = fill

            ws.cell(row=row, column=5, value=target_status).font = NORMAL_FONT
            ws.cell(row=row, column=5).alignment = CENTER_ALIGN
            ws.cell(row=row, column=5).border = THIN_BORDER
            if target_status == 'On Track':
                ws.cell(row=row, column=5).fill = GREEN_FILL
            elif target_status in ['Warning', 'Critical']:
                ws.cell(row=row, column=5).fill = RED_FILL
            elif target_status == 'Not Set':
                ws.cell(row=row, column=5).fill = YELLOW_FILL

            ws.cell(row=row, column=6, value=direction).font = SMALL_FONT
            ws.cell(row=row, column=6).alignment = CENTER_ALIGN
            ws.cell(row=row, column=6).border = THIN_BORDER

            row += 1

        # Add note about targets
        row += 1
        ws.cell(row=row, column=1, value="Note: Company KPI targets are currently not set. Target status shows 'Not Set' for all metrics.").font = FOOTER_FONT
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)

        auto_width(ws)
        return ws

    def build_monthly_trends_sheet(self):
        """Build the Monthly Trends sheet."""
        ws = self.wb.create_sheet("Monthly Trends")
        ws.sheet_properties.tabColor = "2E6DA4"

        trends_df = self.data.get('trends', pd.DataFrame())
        if trends_df.empty:
            ws.cell(row=1, column=1, value="No trend data available.").font = NORMAL_FONT
            return ws

        row = 1
        row = self._write_title_block(ws, row, "Monthly KPI Trends (18 Months)",
                                       f"April 2025 - September 2026")
        row = self._write_metadata_block(ws, row)

        # Pivot trends
        kpi_order = [
            'Revenue', 'Net Profit', 'Operating Margin', 'DSO',
            'Total Headcount', 'Rolling 12M Attrition', 'Attendance Rate', 'Overtime Share'
        ]

        months = sorted(trends_df['month'].unique())
        month_labels = [m.strftime('%b %Y') for m in months]

        # Headers
        headers = ['KPI'] + month_labels
        for col_idx, header in enumerate(headers, 1):
            ws.cell(row=row, column=col_idx, value=header)
        apply_header_style(ws, row, len(headers))
        row += 1

        name_to_key = {
            'Revenue': 'revenue',
            'Net Profit': 'net_profit',
            'Operating Margin': 'operating_margin_pct',
            'DSO': 'dso_days',
            'Total Headcount': 'total_headcount',
            'Rolling 12M Attrition': 'attrition_rolling_12m_pct',
            'Attendance Rate': 'attendance_rate_pct',
            'Overtime Share': 'overtime_share_pct',
        }

        for kpi in kpi_order:
            key = name_to_key.get(kpi, '')
            meta = self.meta.get(key, {})
            unit = meta.get('unit', '')

            ws.cell(row=row, column=1, value=kpi).font = BOLD_FONT
            ws.cell(row=row, column=1).alignment = LEFT_ALIGN
            ws.cell(row=row, column=1).border = THIN_BORDER

            kpi_data = trends_df[trends_df['kpi_name'] == kpi].set_index('month')['value']

            for col_idx, m in enumerate(months, 2):
                val = kpi_data.get(m)
                if val is not None:
                    if key == 'overtime_share_pct':
                        cell_val = val * 100
                        cell_str = f"{cell_val:.2f}%"
                    elif key == 'dso_days':
                        cell_val = val
                        cell_str = f"{cell_val:.2f}"
                    elif unit == 'INR':
                        cell_val = val
                        cell_str = f"{cell_val:,.2f}"
                    elif unit == '%':
                        cell_val = val
                        cell_str = f"{cell_val:.2f}"
                    elif unit == 'count':
                        cell_val = val
                        cell_str = f"{int(cell_val):,}"
                    elif unit == 'days':
                        cell_val = val
                        cell_str = f"{cell_val:.2f}"
                    else:
                        cell_val = val
                        cell_str = str(cell_val)
                else:
                    cell_val = None
                    cell_str = "N/A"

                cell = ws.cell(row=row, column=col_idx, value=cell_str)
                cell.font = NORMAL_FONT
                cell.alignment = CENTER_ALIGN
                cell.border = THIN_BORDER
                if row % 2 == 0:
                    cell.fill = ALT_ROW_FILL
                else:
                    cell.fill = WHITE_FILL

                # Store numeric value for charts (hidden)
                if cell_val is not None:
                    cell.value = cell_val
                    if unit == 'INR':
                        cell.number_format = '#,##0.00'
                    elif unit in ['%', 'days']:
                        cell.number_format = '0.00'
                    elif unit == 'count':
                        cell.number_format = '#,##0'

            row += 1

        # Add note about DSO
        row += 1
        ws.cell(row=row, column=1, value="Note: DSO data is only available for September 2026. Earlier months show N/A.").font = FOOTER_FONT
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(headers))

        # Add charts
        chart_row = row + 2
        self._add_trend_charts(ws, chart_row, months, kpi_order, name_to_key)

        auto_width(ws, min_width=12, max_width=18)
        return ws

    def _add_trend_charts(self, ws, start_row: int, months: List, kpi_order: List[str], name_to_key: Dict[str, str]):
        """Add line charts for KPI trends."""
        num_months = len(months)
        num_kpis = len(kpi_order)
        data_start_row = 5  # After title block and metadata
        data_end_row = data_start_row + num_kpis - 1

        # Chart 1: Financial KPIs (Revenue, Net Profit, Operating Margin)
        financial_kpis = ['Revenue', 'Net Profit', 'Operating Margin']
        financial_rows = [data_start_row + kpi_order.index(k) for k in financial_kpis if k in kpi_order]

        if financial_rows:
            chart1 = LineChart()
            chart1.title = "Financial KPI Trends"
            chart1.style = 10
            chart1.x_axis.title = "Month"
            chart1.y_axis.title = "Value"
            chart1.width = 25
            chart1.height = 15

            # Categories (months)
            cats = Reference(ws, min_col=2, max_col=num_months + 1, min_row=data_start_row, max_row=data_start_row)
            chart1.set_categories(cats)

            for i, kpi_row in enumerate(financial_rows):
                data_ref = Reference(ws, min_col=2, max_col=num_months + 1, min_row=kpi_row, max_row=kpi_row)
                chart1.add_data(data_ref, titles_from_data=False)
                # Set series name using SeriesLabel
                from openpyxl.chart.series import SeriesLabel
                chart1.series[i].title = SeriesLabel(v=kpi_order[kpi_row - data_start_row])

            ws.add_chart(chart1, f"A{start_row}")

        # Chart 2: Operational KPIs
        ops_kpis = ['Total Headcount', 'Rolling 12M Attrition', 'Attendance Rate', 'Overtime Share']
        ops_rows = [data_start_row + kpi_order.index(k) for k in ops_kpis if k in kpi_order]

        if ops_rows:
            chart2 = LineChart()
            chart2.title = "Operational KPI Trends"
            chart2.style = 11
            chart2.x_axis.title = "Month"
            chart2.y_axis.title = "Value"
            chart2.width = 25
            chart2.height = 15

            cats = Reference(ws, min_col=2, max_col=num_months + 1, min_row=data_start_row, max_row=data_start_row)
            chart2.set_categories(cats)

            for i, kpi_row in enumerate(ops_rows):
                data_ref = Reference(ws, min_col=2, max_col=num_months + 1, min_row=kpi_row, max_row=kpi_row)
                chart2.add_data(data_ref, titles_from_data=False)
                chart2.series[i].title = SeriesLabel(v=kpi_order[kpi_row - data_start_row])

            ws.add_chart(chart2, f"A{start_row + 20}")

    def build_overdue_receivables_sheet(self):
        """Build the Overdue Receivables sheet."""
        ws = self.wb.create_sheet("Overdue Receivables")
        ws.sheet_properties.tabColor = "E74C3C"

        overdue_df = self.data.get('overdue_receivables', pd.DataFrame())

        row = 1
        row = self._write_title_block(ws, row, "Overdue Receivables Detail",
                                       f"As of {self.report_month.strftime('%B %d, %Y')}")
        row = self._write_metadata_block(ws, row)

        if overdue_df.empty:
            ws.cell(row=row, column=1, value="No overdue receivables data available for this period.").font = NORMAL_FONT
            return ws

        # Filter to only rows with overdue amounts > 0
        overdue_df = overdue_df[overdue_df['total_overdue_receivables'] > 0].copy()
        if overdue_df.empty:
            ws.cell(row=row, column=1, value="No overdue receivables for this period.").font = NORMAL_FONT
            return ws

        # Sort by total overdue descending
        overdue_df = overdue_df.sort_values('total_overdue_receivables', ascending=False)

        # Summary
        total_overdue = overdue_df['total_overdue_receivables'].sum()
        total_clients = len(overdue_df)
        ws.cell(row=row, column=1, value="Summary").font = SECTION_FONT
        row += 1
        ws.cell(row=row, column=1, value="Total Overdue (INR)").font = BOLD_FONT
        ws.cell(row=row, column=1).alignment = LEFT_ALIGN
        ws.cell(row=row, column=2, value=total_overdue).font = NORMAL_FONT
        ws.cell(row=row, column=2).number_format = '#,##0.00'
        ws.cell(row=row, column=2).alignment = RIGHT_ALIGN
        row += 1
        ws.cell(row=row, column=1, value="Number of Clients with Overdue").font = BOLD_FONT
        ws.cell(row=row, column=1).alignment = LEFT_ALIGN
        ws.cell(row=row, column=2, value=total_clients).font = NORMAL_FONT
        ws.cell(row=row, column=2).alignment = RIGHT_ALIGN
        row += 2

        # Detail table
        ws.cell(row=row, column=1, value="Client Details").font = SECTION_FONT
        row += 1

        headers = ['Client ID', 'Client Name', 'Overdue Invoice Count',
                   'Total Overdue (INR)', 'Carried Overdue (INR)', 'New Overdue (INR)']
        for col_idx, header in enumerate(headers, 1):
            ws.cell(row=row, column=col_idx, value=header)
        apply_header_style(ws, row, len(headers))
        row += 1

        for _, orow in overdue_df.iterrows():
            ws.cell(row=row, column=1, value=orow['client_id']).font = NORMAL_FONT
            ws.cell(row=row, column=1).alignment = CENTER_ALIGN
            ws.cell(row=row, column=1).border = THIN_BORDER

            ws.cell(row=row, column=2, value=orow['client_name']).font = NORMAL_FONT
            ws.cell(row=row, column=2).alignment = LEFT_ALIGN
            ws.cell(row=row, column=2).border = THIN_BORDER

            ws.cell(row=row, column=3, value=int(orow['overdue_invoice_count'])).font = NORMAL_FONT
            ws.cell(row=row, column=3).alignment = CENTER_ALIGN
            ws.cell(row=row, column=3).border = THIN_BORDER

            ws.cell(row=row, column=4, value=orow['total_overdue_receivables']).font = NORMAL_FONT
            ws.cell(row=row, column=4).alignment = RIGHT_ALIGN
            ws.cell(row=row, column=4).number_format = '#,##0.00'
            ws.cell(row=row, column=4).border = THIN_BORDER

            ws.cell(row=row, column=5, value=orow['carried_in_overdue']).font = NORMAL_FONT
            ws.cell(row=row, column=5).alignment = RIGHT_ALIGN
            ws.cell(row=row, column=5).number_format = '#,##0.00'
            ws.cell(row=row, column=5).border = THIN_BORDER

            ws.cell(row=row, column=6, value=orow['new_invoice_overdue']).font = NORMAL_FONT
            ws.cell(row=row, column=6).alignment = RIGHT_ALIGN
            ws.cell(row=row, column=6).number_format = '#,##0.00'
            ws.cell(row=row, column=6).border = THIN_BORDER

            if row % 2 == 0:
                for col in range(1, 7):
                    ws.cell(row=row, column=col).fill = ALT_ROW_FILL
            else:
                for col in range(1, 7):
                    ws.cell(row=row, column=col).fill = WHITE_FILL

            row += 1

        # Totals row
        ws.cell(row=row, column=1, value="TOTAL").font = BOLD_FONT
        ws.cell(row=row, column=1).alignment = CENTER_ALIGN
        ws.cell(row=row, column=1).border = THIN_BORDER
        ws.cell(row=row, column=1).fill = SUBHEADER_FILL

        ws.cell(row=row, column=2, value="").font = BOLD_FONT
        ws.cell(row=row, column=2).border = THIN_BORDER
        ws.cell(row=row, column=2).fill = SUBHEADER_FILL

        ws.cell(row=row, column=3, value=overdue_df['overdue_invoice_count'].sum()).font = BOLD_FONT
        ws.cell(row=row, column=3).alignment = CENTER_ALIGN
        ws.cell(row=row, column=3).border = THIN_BORDER
        ws.cell(row=row, column=3).fill = SUBHEADER_FILL

        ws.cell(row=row, column=4, value=overdue_df['total_overdue_receivables'].sum()).font = BOLD_FONT
        ws.cell(row=row, column=4).alignment = RIGHT_ALIGN
        ws.cell(row=row, column=4).number_format = '#,##0.00'
        ws.cell(row=row, column=4).border = THIN_BORDER
        ws.cell(row=row, column=4).fill = SUBHEADER_FILL

        ws.cell(row=row, column=5, value=overdue_df['carried_in_overdue'].sum()).font = BOLD_FONT
        ws.cell(row=row, column=5).alignment = RIGHT_ALIGN
        ws.cell(row=row, column=5).number_format = '#,##0.00'
        ws.cell(row=row, column=5).border = THIN_BORDER
        ws.cell(row=row, column=5).fill = SUBHEADER_FILL

        ws.cell(row=row, column=6, value=overdue_df['new_invoice_overdue'].sum()).font = BOLD_FONT
        ws.cell(row=row, column=6).alignment = RIGHT_ALIGN
        ws.cell(row=row, column=6).number_format = '#,##0.00'
        ws.cell(row=row, column=6).border = THIN_BORDER
        ws.cell(row=row, column=6).fill = SUBHEADER_FILL

        auto_width(ws, min_width=12, max_width=30)
        return ws

    def build_dso_sheet(self):
        """Build the DSO Detail sheet."""
        ws = self.wb.create_sheet("DSO Detail")
        ws.sheet_properties.tabColor = "F39C12"

        dso_df = self.data.get('dso', pd.DataFrame())

        row = 1
        row = self._write_title_block(ws, row, "Days Sales Outstanding (DSO) Detail",
                                       f"Report Date: {self.report_month.strftime('%B %d, %Y')}")
        row = self._write_metadata_block(ws, row)

        if dso_df.empty:
            ws.cell(row=row, column=1, value="No DSO data available.").font = NORMAL_FONT
            return ws

        dso_current = dso_df[dso_df['report_date'] == self.report_month]
        if dso_current.empty:
            ws.cell(row=row, column=1, value=f"No DSO data for {self.report_month.strftime('%B %Y')}.").font = NORMAL_FONT
            return ws

        dso_row = dso_current.iloc[0]

        headers = ['Metric', 'Value']
        for col_idx, header in enumerate(headers, 1):
            ws.cell(row=row, column=col_idx, value=header)
        apply_header_style(ws, row, len(headers))
        row += 1

        metrics = [
            ('Report Date', dso_row['report_date'].strftime('%B %d, %Y'), 'text'),
            ('Closing Receivables (INR)', dso_row['closing_receivables'], 'currency'),
            ('Revenue incl. GST (INR)', dso_row['revenue_incl_gst'], 'currency'),
            ('DSO (days)', dso_row['dso_days'], 'number'),
        ]

        for label, value, fmt in metrics:
            ws.cell(row=row, column=1, value=label).font = BOLD_FONT
            ws.cell(row=row, column=1).alignment = LEFT_ALIGN
            ws.cell(row=row, column=1).border = THIN_BORDER

            cell = ws.cell(row=row, column=2, value=value)
            cell.font = NORMAL_FONT
            cell.alignment = RIGHT_ALIGN
            cell.border = THIN_BORDER
            if fmt == 'currency':
                cell.number_format = '#,##0.00'
            elif fmt == 'number':
                cell.number_format = '0.00'

            if row % 2 == 0:
                for col in range(1, 3):
                    ws.cell(row=row, column=col).fill = ALT_ROW_FILL
            else:
                for col in range(1, 3):
                    ws.cell(row=row, column=col).fill = WHITE_FILL
            row += 1

        auto_width(ws, min_width=25, max_width=40)
        return ws

    def build_revenue_profit_sheet(self):
        """Build the Revenue & Profit Detail sheet."""
        ws = self.wb.create_sheet("Revenue & Profit")
        ws.sheet_properties.tabColor = "27AE60"

        rev_df = self.data.get('revenue_detail', pd.DataFrame())
        np_df = self.data.get('net_profit_detail', pd.DataFrame())
        om_df = self.data.get('operating_margin_detail', pd.DataFrame())

        row = 1
        row = self._write_title_block(ws, row, "Revenue & Profit Detail",
                                       f"Current Month: {self.report_month.strftime('%B %Y')}")
        row = self._write_metadata_block(ws, row)

        # Current month breakdown
        ws.cell(row=row, column=1, value="Current Month Breakdown").font = SECTION_FONT
        row += 1

        headers = ['Metric', 'Value (INR)']
        for col_idx, header in enumerate(headers, 1):
            ws.cell(row=row, column=col_idx, value=header)
        apply_header_style(ws, row, len(headers))
        row += 1

        # Revenue
        if not rev_df.empty:
            rev_current = rev_df[rev_df['month'] == self.report_month.strftime('%Y-%m')]
            if not rev_current.empty:
                ws.cell(row=row, column=1, value="Revenue").font = BOLD_FONT
                ws.cell(row=row, column=1).alignment = LEFT_ALIGN
                ws.cell(row=row, column=1).border = THIN_BORDER
                cell = ws.cell(row=row, column=2, value=rev_current.iloc[0]['revenue'])
                cell.font = NORMAL_FONT
                cell.alignment = RIGHT_ALIGN
                cell.number_format = '#,##0.00'
                cell.border = THIN_BORDER
                row += 1

        # Net Profit detail
        if not np_df.empty:
            np_current = np_df[np_df['month'] == self.report_month.strftime('%Y-%m')]
            if not np_current.empty:
                np_row = np_current.iloc[0]
                for label, val in [('Total Income', np_row['total_income']),
                                    ('Total Expense', np_row['total_expense']),
                                    ('Net Profit', np_row['net_profit'])]:
                    ws.cell(row=row, column=1, value=label).font = BOLD_FONT
                    ws.cell(row=row, column=1).alignment = LEFT_ALIGN
                    ws.cell(row=row, column=1).border = THIN_BORDER
                    cell = ws.cell(row=row, column=2, value=val)
                    cell.font = NORMAL_FONT if label != 'Net Profit' else BOLD_FONT
                    cell.alignment = RIGHT_ALIGN
                    cell.number_format = '#,##0.00'
                    cell.border = THIN_BORDER
                    if label == 'Net Profit':
                        cell.fill = GREEN_FILL if val >= 0 else RED_FILL
                    row += 1

        # Operating Margin
        if not om_df.empty:
            om_current = om_df[om_df['month'] == self.report_month.strftime('%Y-%m')]
            if not om_current.empty:
                ws.cell(row=row, column=1, value="Operating Margin (%)").font = BOLD_FONT
                ws.cell(row=row, column=1).alignment = LEFT_ALIGN
                ws.cell(row=row, column=1).border = THIN_BORDER
                cell = ws.cell(row=row, column=2, value=om_current.iloc[0]['operating_margin_pct'])
                cell.font = NORMAL_FONT
                cell.alignment = RIGHT_ALIGN
                cell.number_format = '0.00'
                cell.border = THIN_BORDER
                row += 1

        row += 1

        # Historical Revenue
        ws.cell(row=row, column=1, value="Historical Revenue (All Months)").font = SECTION_FONT
        row += 1

        if not rev_df.empty:
            headers = ['Month', 'Revenue (INR)']
            for col_idx, header in enumerate(headers, 1):
                ws.cell(row=row, column=col_idx, value=header)
            apply_header_style(ws, row, len(headers))
            row += 1

            for _, rrow in rev_df.iterrows():
                ws.cell(row=row, column=1, value=rrow['month']).font = NORMAL_FONT
                ws.cell(row=row, column=1).alignment = CENTER_ALIGN
                ws.cell(row=row, column=1).border = THIN_BORDER
                cell = ws.cell(row=row, column=2, value=rrow['revenue'])
                cell.font = NORMAL_FONT
                cell.alignment = RIGHT_ALIGN
                cell.number_format = '#,##0.00'
                cell.border = THIN_BORDER
                if row % 2 == 0:
                    for col in range(1, 3):
                        ws.cell(row=row, column=col).fill = ALT_ROW_FILL
                else:
                    for col in range(1, 3):
                        ws.cell(row=row, column=col).fill = WHITE_FILL
                row += 1

        auto_width(ws, min_width=18, max_width=30)
        return ws

    def generate(self, output_path: str) -> str:
        """Generate the Excel workbook."""
        self.build_kpi_summary_sheet()
        self.build_monthly_trends_sheet()
        self.build_overdue_receivables_sheet()
        self.build_dso_sheet()
        self.build_revenue_profit_sheet()

        # Remove default sheet if it exists and wasn't used
        if 'Sheet' in self.wb.sheetnames and self.wb['Sheet'] != self.wb.active:
            self.wb.remove(self.wb['Sheet'])

        self.wb.save(output_path)
        logger.info(f"Excel report generated: {output_path}")
        return output_path


def generate_excel_report(report_month: date, data: Dict[str, Any], output_dir: str = "reports") -> str:
    """Convenience function to generate Excel report."""
    import os
    os.makedirs(output_dir, exist_ok=True)
    filename = f"pulseiq_executive_report_{report_month.strftime('%Y_%m')}.xlsx"
    output_path = os.path.join(output_dir, filename)
    generator = ExcelReportGenerator(report_month, data)
    return generator.generate(output_path)