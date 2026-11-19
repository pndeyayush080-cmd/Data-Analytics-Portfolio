"""
PDF generator module for the automated report builder.
Creates professional executive PDF reports using reportlab.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm, mm
from reportlab.lib.colors import HexColor, black, white, grey
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable, Frame, PageTemplate,
    BaseDocTemplate, NextPageTemplate
)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing, Rect, Line
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib import colors
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.textlabels import Label
from datetime import date, datetime
from typing import Dict, List, Optional, Any
import pandas as pd
import logging

# Handle both module and direct execution
try:
    from .data_fetcher import format_value, get_kpi_metadata
except ImportError:
    from data_fetcher import format_value, get_kpi_metadata

logger = logging.getLogger(__name__)

# Color palette
DARK_BLUE = HexColor("#1B3A5C")
MEDIUM_BLUE = HexColor("#2E6DA4")
LIGHT_BLUE = HexColor("#D6EAF8")
ACCENT_GREEN = HexColor("#27AE60")
ACCENT_RED = HexColor("#E74C3C")
ACCENT_ORANGE = HexColor("#F39C12")
WHITE = HexColor("#FFFFFF")
LIGHT_GREY = HexColor("#F2F2F2")
MEDIUM_GREY = HexColor("#CCCCCC")
DARK_GREY = HexColor("#333333")
TABLE_HEADER_BG = HexColor("#1B3A5C")
TABLE_ALT_ROW = HexColor("#EBF5FB")


class ColorBox(Flowable):
    """A colored box for KPI cards."""
    def __init__(self, width, height, fill_color, border_color=None):
        Flowable.__init__(self)
        self.width = width
        self.height = height
        self.fill_color = fill_color
        self.border_color = border_color or fill_color

    def draw(self):
        self.canv.setFillColor(self.fill_color)
        self.canv.setStrokeColor(self.border_color)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=1)


def create_kpi_card(kpi_name: str, value: str, unit: str, trend: str = "",
                    target_status: str = "Not Set", width: float = 1.8*inch) -> Table:
    """Create a KPI card as a table."""
    meta = get_kpi_metadata().get(kpi_name, {})
    direction = meta.get('direction', '')

    # Determine card color based on target status and direction
    if target_status == "Not Set":
        header_color = MEDIUM_BLUE
    elif target_status == "On Track":
        header_color = ACCENT_GREEN
    elif target_status in ["Warning", "Critical"]:
        header_color = ACCENT_RED
    else:
        header_color = MEDIUM_BLUE

    data = [
        [Paragraph(f"<b>{kpi_name}</b>", ParagraphStyle('kpi_name', fontSize=9, textColor=WHITE, alignment=TA_CENTER))],
        [Paragraph(f"<font size=14><b>{value}</b></font>", ParagraphStyle('kpi_val', fontSize=14, textColor=DARK_BLUE, alignment=TA_CENTER))],
        [Paragraph(f"<font size=7>{trend}</font>", ParagraphStyle('kpi_trend', fontSize=7, textColor=DARK_GREY, alignment=TA_CENTER))],
        [Paragraph(f"<font size=6>Target: {target_status}</font>", ParagraphStyle('kpi_target', fontSize=6, textColor=DARK_GREY, alignment=TA_CENTER))],
    ]

    table = Table(data, colWidths=[width])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), header_color),
        ('BACKGROUND', (0, 1), (0, -1), WHITE),
        ('BOX', (0, 0), (-1, -1), 0.5, MEDIUM_GREY),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return table


class PDFReportGenerator:
    """Generates professional executive PDF reports."""

    def __init__(self, report_month: date, data: Dict[str, Any]):
        self.report_month = report_month
        self.data = data
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        # Data cut-off: latest date in source data (hardcoded based on known warehouse state)
        self.data_cutoff = date(2026, 9, 30)

    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            fontName='Helvetica-Bold',
            fontSize=24,
            textColor=DARK_BLUE,
            spaceAfter=6,
            alignment=TA_CENTER,
        ))
        self.styles.add(ParagraphStyle(
            name='ReportSubtitle',
            fontName='Helvetica',
            fontSize=12,
            textColor=MEDIUM_BLUE,
            spaceAfter=20,
            alignment=TA_CENTER,
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=DARK_BLUE,
            spaceBefore=16,
            spaceAfter=8,
            borderWidth=0,
            borderPadding=0,
        ))
        self.styles.add(ParagraphStyle(
            name='SubSectionHeader',
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=MEDIUM_BLUE,
            spaceBefore=12,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name='BodyText2',
            fontName='Helvetica',
            fontSize=9,
            textColor=DARK_GREY,
            spaceAfter=6,
            leading=13,
            alignment=TA_JUSTIFY,
        ))
        self.styles.add(ParagraphStyle(
            name='TableHeader',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=WHITE,
            alignment=TA_CENTER,
        ))
        self.styles.add(ParagraphStyle(
            name='TableCell',
            fontName='Helvetica',
            fontSize=8,
            textColor=DARK_GREY,
            alignment=TA_CENTER,
        ))
        self.styles.add(ParagraphStyle(
            name='TableCellLeft',
            fontName='Helvetica',
            fontSize=8,
            textColor=DARK_GREY,
            alignment=TA_LEFT,
        ))
        self.styles.add(ParagraphStyle(
            name='FooterText',
            fontName='Helvetica',
            fontSize=7,
            textColor=grey,
            alignment=TA_CENTER,
        ))

    def _header_footer(self, canvas, doc):
        """Add header and footer to each page."""
        canvas.saveState()
        # Header line
        canvas.setStrokeColor(MEDIUM_BLUE)
        canvas.setLineWidth(1.5)
        canvas.line(0.75*inch, A4[1] - 0.6*inch, A4[0] - 0.75*inch, A4[1] - 0.6*inch)

        # Footer
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(grey)
        canvas.drawCentredString(A4[0]/2, 0.5*inch,
            f"PulseIQ Executive Report | {self.report_month.strftime('%B %Y')} | Data as of {self.data_cutoff.strftime('%b %d, %Y')} | Confidential | Page {doc.page}")
        canvas.drawCentredString(A4[0]/2, 0.35*inch,
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        canvas.restoreState()

    def _first_page_header_footer(self, canvas, doc):
        """Header/footer for first page (no header line)."""
        canvas.saveState()
        # Footer only
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(grey)
        canvas.drawCentredString(A4[0]/2, 0.5*inch,
            f"PulseIQ Executive Report | {self.report_month.strftime('%B %Y')} | Data as of {self.data_cutoff.strftime('%b %d, %Y')} | Confidential | Page {doc.page}")
        canvas.drawCentredString(A4[0]/2, 0.35*inch,
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        canvas.restoreState()

    def build_cover_page(self) -> List:
        """Build the cover page elements."""
        elements = []

        # Spacer at top
        elements.append(Spacer(1, 1.5*inch))

        # Company logo placeholder
        elements.append(Paragraph("PULSEIQ", ParagraphStyle('logo', fontName='Helvetica-Bold', fontSize=36, textColor=DARK_BLUE, alignment=TA_CENTER, spaceAfter=4)))
        elements.append(Paragraph("Workforce Analytics", ParagraphStyle('tagline', fontName='Helvetica', fontSize=14, textColor=MEDIUM_BLUE, alignment=TA_CENTER, spaceAfter=30)))

        # Horizontal rule
        elements.append(HRFlowable(width="80%", thickness=2, color=MEDIUM_BLUE, spaceAfter=20))

        # Report title
        elements.append(Paragraph("Monthly Executive Report", self.styles['ReportTitle']))
        elements.append(Paragraph(self.report_month.strftime('%B %Y'), self.styles['ReportSubtitle']))

        elements.append(Spacer(1, 1*inch))

        # Report info table
        info_data = [
            ['Report Period:', self.report_month.strftime('%B %Y')],
            ['Report Type:', 'Executive Summary'],
            ['Data Source:', 'PulseIQ Data Warehouse (star_schema.pq15_company_scorecard)'],
            ['Data Cut-off:', self.data_cutoff.strftime('%B %d, %Y')],
            ['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M')],
            ['Classification:', 'Confidential'],
        ]
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), DARK_BLUE),
            ('TEXTCOLOR', (1, 0), (1, -1), DARK_GREY),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, MEDIUM_GREY),
        ]))
        elements.append(info_table)

        elements.append(Spacer(1, 1.5*inch))

        # Disclaimer
        disclaimer = (
            "This report contains confidential and proprietary information of PulseIQ. "
            "Unauthorized reproduction or distribution is strictly prohibited. "
            "All financial figures are in Indian Rupees (INR) unless otherwise noted. "
            "N/A indicates data not available for the period."
        )
        elements.append(Paragraph(disclaimer, ParagraphStyle('disclaimer', fontName='Helvetica-Oblique', fontSize=8, textColor=grey, alignment=TA_CENTER, leading=11)))

        return elements

    def build_executive_summary(self) -> List:
        """Build the executive summary section."""
        elements = []
        elements.append(Paragraph("1. Executive Summary", self.styles['SectionHeader']))

        scorecard = self.data.get('scorecard_current', {})
        prev_scorecard = self.data.get('scorecard_previous', {})

        # Key highlights
        revenue = scorecard.get('revenue')
        net_profit = scorecard.get('net_profit')
        op_margin = scorecard.get('operating_margin_pct')
        headcount = scorecard.get('total_headcount')
        attrition = scorecard.get('attrition_rolling_12m_pct')
        attendance = scorecard.get('attendance_rate_pct')
        overtime = scorecard.get('overtime_share_pct')
        dso = scorecard.get('dso_days')

        highlights = []

        if revenue is not None:
            prev_rev = prev_scorecard.get('revenue')
            if prev_rev and prev_rev > 0:
                change_pct = ((revenue - prev_rev) / prev_rev) * 100
                direction = "increase" if change_pct >= 0 else "decrease"
                highlights.append(f"Revenue reached {format_value(revenue, 'INR')}, a {abs(change_pct):.1f}% {direction} from prior month.")

        if net_profit is not None:
            highlights.append(f"Net Profit stood at {format_value(net_profit, 'INR')}.")

        if op_margin is not None:
            highlights.append(f"Operating Margin was {format_value(op_margin, '%')}.")

        if headcount is not None:
            highlights.append(f"Total headcount: {format_value(headcount, 'count')} employees.")

        if attrition is not None:
            highlights.append(f"Rolling 12-month attrition: {format_value(attrition, '%')}.")

        if attendance is not None:
            highlights.append(f"Attendance rate: {format_value(attendance, '%')}.")

        if overtime is not None:
            highlights.append(f"Overtime share: {format_value(overtime * 100, '%')}.")

        if dso is not None:
            highlights.append(f"Days Sales Outstanding (DSO): {format_value(dso, 'days')}.")

        for h in highlights:
            elements.append(Paragraph(f"• {h}", self.styles['BodyText2']))

        elements.append(Spacer(1, 12))
        return elements

    def build_kpi_dashboard(self) -> List:
        """Build the KPI dashboard with cards."""
        elements = []
        elements.append(Paragraph("2. KPI Dashboard", self.styles['SectionHeader']))

        scorecard = self.data.get('scorecard_current', {})
        targets = self.data.get('targets', pd.DataFrame())

        # Convert targets to dict
        target_dict = {}
        if not targets.empty:
            for _, row in targets.iterrows():
                kpi_name = row['kpi_name'].lower().replace(' ', '_')
                # Map display names to column names
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
                target_dict[col] = row['target_status']

        kpi_order = [
            'revenue', 'net_profit', 'operating_margin_pct', 'dso_days',
            'total_headcount', 'attrition_rolling_12m_pct',
            'attendance_rate_pct', 'overtime_share_pct'
        ]

        meta = get_kpi_metadata()

        # Create rows of 4 cards each
        cards = []
        for kpi_key in kpi_order:
            value = scorecard.get(kpi_key)
            unit = meta.get(kpi_key, {}).get('unit', '')
            target_status = target_dict.get(kpi_key, 'Not Set')

            # Format value
            if kpi_key == 'overtime_share_pct' and value is not None:
                display_value = format_value(value * 100, '%')
            elif kpi_key == 'dso_days' and value is not None:
                display_value = format_value(value, 'days')
            elif unit == 'INR':
                display_value = format_value(value, 'INR')
            elif unit == '%':
                display_value = format_value(value, '%')
            elif unit == 'count':
                display_value = format_value(value, 'count')
            elif unit == 'days':
                display_value = format_value(value, 'days')
            else:
                display_value = format_value(value)

            # Calculate trend vs previous month
            prev_scorecard = self.data.get('scorecard_previous', {})
            prev_value = prev_scorecard.get(kpi_key)
            trend = ""
            if value is not None and prev_value is not None and prev_value != 0:
                change = ((value - prev_value) / prev_value) * 100
                arrow = "↑" if change >= 0 else "↓"
                color = ACCENT_GREEN if (
                    (meta.get(kpi_key, {}).get('direction') == 'Higher is better' and change >= 0) or
                    (meta.get(kpi_key, {}).get('direction') == 'Lower is better' and change < 0)
                ) else ACCENT_RED
                trend = f"<font color='{color.hexval()}'>{arrow} {abs(change):.1f}% vs prev month</font>"

            kpi_name = meta.get(kpi_key, {}).get('name', kpi_key)
            card = create_kpi_card(kpi_name, display_value, unit, trend, target_status)
            cards.append(card)

        # Arrange in 2 rows of 4
        row1 = [cards[i] for i in range(4)]
        row2 = [cards[i] for i in range(4, 8)]

        card_table = Table([row1, row2], colWidths=[1.8*inch]*4)
        card_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(card_table)
        elements.append(Spacer(1, 12))

        # Target status note
        if all(t == 'Not Set' for t in target_dict.values()):
            elements.append(Paragraph(
                "<i>Note: Company KPI targets are currently not set. Target status shows 'Not Set' for all metrics.</i>",
                ParagraphStyle('note', fontSize=8, textColor=grey, alignment=TA_CENTER, spaceBefore=6)
            ))

        return elements

    def build_monthly_trends_table(self) -> List:
        """Build the monthly trends table."""
        elements = []
        elements.append(Paragraph("3. Monthly Trends (18 Months)", self.styles['SectionHeader']))

        trends_df = self.data.get('trends', pd.DataFrame())
        if trends_df.empty:
            elements.append(Paragraph("No trend data available.", self.styles['BodyText2']))
            return elements

        # Pivot trends for display
        kpi_order = [
            'Revenue', 'Net Profit', 'Operating Margin', 'DSO',
            'Total Headcount', 'Rolling 12M Attrition', 'Attendance Rate', 'Overtime Share'
        ]

        # Create pivot table
        pivot_data = []
        header = ['KPI'] + [self.report_month.replace(month=i).strftime('%b %Y') for i in range(4, 13)] + \
                 [self.report_month.replace(year=self.report_month.year+1, month=i).strftime('%b %Y') for i in range(1, 4)] if self.report_month.month >= 4 else \
                 [self.report_month.replace(month=i).strftime('%b %Y') for i in range(1, 13)]

        # Actually, let's just use all months from data
        months = sorted(trends_df['month'].unique())
        header = ['KPI'] + [m.strftime('%b %Y') for m in months]

        for kpi in kpi_order:
            row = [kpi]
            kpi_data = trends_df[trends_df['kpi_name'] == kpi].set_index('month')['value']
            for m in months:
                val = kpi_data.get(m)
                if val is not None:
                    meta = get_kpi_metadata()
                    # Map KPI name to key
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
                    key = name_to_key.get(kpi, '')
                    unit = meta.get(key, {}).get('unit', '')
                    if key == 'overtime_share_pct':
                        row.append(format_value(val * 100, '%'))
                    elif key == 'dso_days':
                        row.append(format_value(val, 'days'))
                    elif unit == 'INR':
                        row.append(format_value(val, 'INR'))
                    elif unit == '%':
                        row.append(format_value(val, '%'))
                    elif unit == 'count':
                        row.append(format_value(val, 'count'))
                    elif unit == 'days':
                        row.append(format_value(val, 'days'))
                    else:
                        row.append(format_value(val))
                else:
                    row.append("N/A")
            pivot_data.append(row)

        # Create table
        col_widths = [1.3*inch] + [0.7*inch] * len(months)
        # Adjust if too wide
        if sum(col_widths) > 7*inch:
            col_widths = [1.1*inch] + [0.6*inch] * len(months)

        table_data = [header] + pivot_data
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('TEXTCOLOR', (0, 1), (-1, -1), DARK_GREY),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, MEDIUM_GREY),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, TABLE_ALT_ROW]),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        # Add line charts for key financial KPIs
        financial_kpis = ['Revenue', 'Net Profit', 'Operating Margin']
        chart = self._create_line_chart(trends_df, financial_kpis, width=6.5*inch, height=2.8*inch)
        elements.append(chart)
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"Figure 1: Financial KPI Trends (April 2025 – {self.report_month.strftime('%B %Y')})", 
                                   ParagraphStyle('fig_caption', fontName='Helvetica-Oblique', fontSize=8, textColor=grey, alignment=TA_CENTER, spaceAfter=12)))

        # Add line charts for operational KPIs
        ops_kpis = ['Total Headcount', 'Rolling 12M Attrition', 'Attendance Rate', 'Overtime Share']
        chart2 = self._create_line_chart(trends_df, ops_kpis, width=6.5*inch, height=2.8*inch)
        elements.append(chart2)
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"Figure 2: Operational KPI Trends (April 2025 – {self.report_month.strftime('%B %Y')})", 
                                   ParagraphStyle('fig_caption', fontName='Helvetica-Oblique', fontSize=8, textColor=grey, alignment=TA_CENTER, spaceAfter=12)))

        return elements

    def _create_line_chart(self, trends_df: pd.DataFrame, kpi_names: List[str], width: float = 6.5*inch, height: float = 2.8*inch) -> Drawing:
        """Create a line chart for the given KPIs."""
        drawing = Drawing(width, height)
        chart = HorizontalLineChart()
        chart.x = 50
        chart.y = 40
        chart.width = width - 100
        chart.height = height - 80

        months = sorted(trends_df['month'].unique())
        month_labels = [m.strftime('%b %y') for m in months]

        chart.data = []

        colors_list = [DARK_BLUE, ACCENT_GREEN, ACCENT_RED, ACCENT_ORANGE, MEDIUM_BLUE, LIGHT_BLUE, HexColor("#8E44AD"), HexColor("#16A085")]

        for i, kpi in enumerate(kpi_names):
            kpi_data = trends_df[trends_df['kpi_name'] == kpi].set_index('month')['value']
            values = [kpi_data.get(m) for m in months]
            chart.data.append([v if v is not None else None for v in values])
            # Lines are auto-created by TypedPropertyCollection when accessed
            chart.lines[i].strokeColor = colors_list[i % len(colors_list)]
            chart.lines[i].strokeWidth = 2
            chart.lines[i].symbol = makeMarker('Circle')
            chart.lines[i].symbol.size = 4

        chart.categoryAxis.categoryNames = month_labels
        chart.categoryAxis.labels.fontName = 'Helvetica'
        chart.categoryAxis.labels.fontSize = 7
        chart.categoryAxis.labels.angle = 45
        chart.categoryAxis.labels.boxAnchor = 'n'
        chart.categoryAxis.labels.dx = -5
        chart.categoryAxis.labels.dy = -2

        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = None
        chart.valueAxis.valueStep = None
        chart.valueAxis.labels.fontName = 'Helvetica'
        chart.valueAxis.labels.fontSize = 7

        # Add legend
        legend = Legend()
        legend.x = width - 130
        legend.y = height - 50
        legend.dx = 8
        legend.dy = 8
        legend.fontName = 'Helvetica'
        legend.fontSize = 7
        legend.alignment = 'right'
        legend.colorNamePairs = [(colors_list[i % len(colors_list)], kpi) for i, kpi in enumerate(kpi_names)]

        drawing.add(chart, 'chart')
        drawing.add(legend, 'legend')
        return drawing

    def build_overdue_receivables(self) -> List:
        """Build the overdue receivables section."""
        elements = []
        elements.append(Paragraph("4. Overdue Receivables Detail", self.styles['SectionHeader']))

        overdue_df = self.data.get('overdue_receivables', pd.DataFrame())
        if overdue_df.empty:
            elements.append(Paragraph("No overdue receivables data available for this period.", self.styles['BodyText2']))
            return elements

        # Filter to only rows with overdue amounts > 0
        overdue_df = overdue_df[overdue_df['total_overdue_receivables'] > 0].copy()
        if overdue_df.empty:
            elements.append(Paragraph("No overdue receivables for this period.", self.styles['BodyText2']))
            return elements

        # Sort by total overdue descending
        overdue_df = overdue_df.sort_values('total_overdue_receivables', ascending=False)

        # Summary
        total_overdue = overdue_df['total_overdue_receivables'].sum()
        total_clients = len(overdue_df)
        elements.append(Paragraph(f"Total Overdue: {format_value(total_overdue, 'INR')} across {total_clients} client(s)", self.styles['BodyText2']))
        elements.append(Spacer(1, 6))

        # Table
        header = ['Client ID', 'Client Name', 'Overdue Invoices', 'Total Overdue (INR)', 'Carried Overdue', 'New Overdue']
        table_data = [header]
        for _, row in overdue_df.iterrows():
            table_data.append([
                row['client_id'],
                row['client_name'],
                str(row['overdue_invoice_count']),
                format_value(row['total_overdue_receivables'], 'INR'),
                format_value(row['carried_in_overdue'], 'INR'),
                format_value(row['new_invoice_overdue'], 'INR'),
            ])

        col_widths = [0.8*inch, 1.8*inch, 0.8*inch, 1.2*inch, 1.2*inch, 1.2*inch]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TEXTCOLOR', (0, 1), (-1, -1), DARK_GREY),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, MEDIUM_GREY),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, TABLE_ALT_ROW]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        return elements

    def build_dso_section(self) -> List:
        """Build DSO detail section."""
        elements = []
        elements.append(Paragraph("5. Days Sales Outstanding (DSO) Detail", self.styles['SectionHeader']))

        dso_df = self.data.get('dso', pd.DataFrame())
        if dso_df.empty:
            elements.append(Paragraph("DSO data not available for prior months. Only September 2026 DSO is available.", self.styles['BodyText2']))
            return elements

        # Filter to report month
        dso_current = dso_df[dso_df['report_date'] == self.report_month]
        if dso_current.empty:
            elements.append(Paragraph(f"No DSO data for {self.report_month.strftime('%B %Y')}.", self.styles['BodyText2']))
            return elements

        row = dso_current.iloc[0]
        elements.append(Paragraph(f"Report Date: {row['report_date'].strftime('%B %d, %Y')}", self.styles['BodyText2']))
        elements.append(Paragraph(f"Closing Receivables: {format_value(row['closing_receivables'], 'INR')}", self.styles['BodyText2']))
        elements.append(Paragraph(f"Revenue (incl. GST): {format_value(row['revenue_incl_gst'], 'INR')}", self.styles['BodyText2']))
        elements.append(Paragraph(f"DSO: {format_value(row['dso_days'], 'days')}", self.styles['BodyText2']))

        elements.append(Spacer(1, 12))
        return elements

    def build_revenue_profit_detail(self) -> List:
        """Build revenue and profit detail section."""
        elements = []
        elements.append(Paragraph("6. Revenue & Profit Detail", self.styles['SectionHeader']))

        rev_df = self.data.get('revenue_detail', pd.DataFrame())
        np_df = self.data.get('net_profit_detail', pd.DataFrame())
        om_df = self.data.get('operating_margin_detail', pd.DataFrame())

        # Current month detail
        elements.append(Paragraph("Current Month Breakdown", self.styles['SubSectionHeader']))

        # Revenue detail
        if not rev_df.empty:
            rev_current = rev_df[rev_df['month'] == self.report_month.strftime('%Y-%m')]
            if not rev_current.empty:
                elements.append(Paragraph(f"Revenue: {format_value(rev_current.iloc[0]['revenue'], 'INR')}", self.styles['BodyText2']))

        # Net profit detail
        if not np_df.empty:
            np_current = np_df[np_df['month'] == self.report_month.strftime('%Y-%m')]
            if not np_current.empty:
                row = np_current.iloc[0]
                elements.append(Paragraph(f"Total Income: {format_value(row['total_income'], 'INR')}", self.styles['BodyText2']))
                elements.append(Paragraph(f"Total Expense: {format_value(row['total_expense'], 'INR')}", self.styles['BodyText2']))
                elements.append(Paragraph(f"Net Profit: {format_value(row['net_profit'], 'INR')}", self.styles['BodyText2']))

        # Operating margin
        if not om_df.empty:
            om_current = om_df[om_df['month'] == self.report_month.strftime('%Y-%m')]
            if not om_current.empty:
                elements.append(Paragraph(f"Operating Margin: {format_value(om_current.iloc[0]['operating_margin_pct'], '%')}", self.styles['BodyText2']))

        elements.append(Spacer(1, 12))
        return elements

    def generate(self, output_path: str) -> str:
        """Generate the PDF report."""
        doc = BaseDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
        )

        # Define page templates
        first_page_frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='first_page'
        )
        later_page_frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='later_pages'
        )

        first_page_template = PageTemplate(
            id='FirstPage',
            frames=[first_page_frame],
            onPage=self._first_page_header_footer
        )
        later_page_template = PageTemplate(
            id='LaterPages',
            frames=[later_page_frame],
            onPage=self._header_footer
        )

        doc.addPageTemplates([first_page_template, later_page_template])

        # Build story
        story = []

        # Cover page
        story.extend(self.build_cover_page())
        story.append(NextPageTemplate('LaterPages'))
        story.append(PageBreak())

        # Table of Contents placeholder
        story.append(Paragraph("Table of Contents", self.styles['SectionHeader']))
        toc_items = [
            "1. Executive Summary",
            "2. KPI Dashboard",
            "3. Monthly Trends (18 Months)",
            "4. Overdue Receivables Detail",
            "5. Days Sales Outstanding (DSO) Detail",
            "6. Revenue & Profit Detail",
        ]
        for item in toc_items:
            story.append(Paragraph(item, ParagraphStyle('toc', fontSize=11, textColor=DARK_BLUE, spaceAfter=4, leftIndent=20)))
        story.append(PageBreak())

        # Report sections
        story.extend(self.build_executive_summary())
        story.extend(self.build_kpi_dashboard())
        story.append(PageBreak())
        story.extend(self.build_monthly_trends_table())
        story.append(PageBreak())
        story.extend(self.build_overdue_receivables())
        story.extend(self.build_dso_section())
        story.extend(self.build_revenue_profit_detail())

        # Build PDF
        doc.build(story)
        logger.info(f"PDF report generated: {output_path}")
        return output_path


def generate_pdf_report(report_month: date, data: Dict[str, Any], output_dir: str = "reports") -> str:
    """Convenience function to generate PDF report."""
    import os
    os.makedirs(output_dir, exist_ok=True)
    filename = f"pulseiq_executive_report_{report_month.strftime('%Y_%m')}.pdf"
    output_path = os.path.join(output_dir, filename)
    generator = PDFReportGenerator(report_month, data)
    return generator.generate(output_path)