"""
Validation module for the automated report builder.
Provides comprehensive validation of generated reports and data integrity.
"""

import os
import logging
from datetime import date
from typing import Dict, Any, List, Tuple
import pandas as pd
import openpyxl
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)


class ReportValidator:
    """Validates generated reports for correctness and completeness."""

    def __init__(self, db_path: str = None, snapshot_dir: str = None):
        if db_path is None:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base_dir, "phase-3", "data", "warehouse", "pulseiq_clean.duckdb")
        self.db_path = db_path
        self.snapshot_dir = snapshot_dir

    def validate_pdf_exists(self, pdf_path: str) -> Tuple[bool, str]:
        """Validate PDF file exists and has reasonable size."""
        if not os.path.exists(pdf_path):
            return False, f"PDF file not found: {pdf_path}"

        size = os.path.getsize(pdf_path)
        if size < 5000:  # Less than 5KB is suspicious
            return False, f"PDF file too small ({size} bytes): {pdf_path}"

        return True, f"PDF valid: {pdf_path} ({size:,} bytes)"

    def validate_excel_exists(self, excel_path: str) -> Tuple[bool, str]:
        """Validate Excel file exists and has required sheets."""
        if not os.path.exists(excel_path):
            return False, f"Excel file not found: {excel_path}"

        size = os.path.getsize(excel_path)
        if size < 5000:  # Less than 5KB is suspicious
            return False, f"Excel file too small ({size} bytes): {excel_path}"

        try:
            wb = openpyxl.load_workbook(excel_path, read_only=True)
            sheets = wb.sheetnames
            wb.close()

            required_sheets = ['KPI Summary', 'Monthly Trends', 'Overdue Receivables', 'DSO Detail', 'Revenue & Profit']
            missing = [s for s in required_sheets if s not in sheets]
            if missing:
                return False, f"Missing required sheets: {missing}. Found: {sheets}"

            return True, f"Excel valid: {excel_path} ({size:,} bytes), sheets: {sheets}"
        except Exception as e:
            return False, f"Excel file corrupted or invalid: {e}"

    def validate_excel_content(self, excel_path: str, report_month: date) -> Tuple[bool, List[str]]:
        """Validate Excel content matches expected data."""
        errors = []
        warnings = []

        try:
            wb = openpyxl.load_workbook(excel_path, data_only=True)

            # Validate KPI Summary sheet
            if 'KPI Summary' in wb.sheetnames:
                ws = wb['KPI Summary']
                # Check for key KPIs in column A
                kpi_names = []
                for row in ws.iter_rows(min_row=1, max_col=1, values_only=False):
                    cell = row[0]
                    if cell.value and isinstance(cell.value, str):
                        kpi_names.append(cell.value.strip())

                expected_kpis = ['Revenue', 'Net Profit', 'Operating Margin', 'DSO',
                                 'Total Headcount', 'Rolling 12M Attrition',
                                 'Attendance Rate', 'Overtime Share']
                for ekpi in expected_kpis:
                    found = any(ekpi.lower() in k.lower() for k in kpi_names)
                    if not found:
                        warnings.append(f"KPI Summary: Expected KPI '{ekpi}' not found in sheet")

            # Validate Monthly Trends sheet
            if 'Monthly Trends' in wb.sheetnames:
                ws = wb['Monthly Trends']
                # Check header row has month labels
                header_row = None
                for row in ws.iter_rows(min_row=1, max_row=10, values_only=True):
                    if row and any(isinstance(v, str) and ('2025' in v or '2026' in v) for v in row):
                        header_row = row
                        break
                if not header_row:
                    warnings.append("Monthly Trends: Could not find month header row")

            # Validate Overdue Receivables sheet
            if 'Overdue Receivables' in wb.sheetnames:
                ws = wb['Overdue Receivables']
                # Check for summary data
                has_summary = False
                for row in ws.iter_rows(min_row=1, max_col=2, values_only=True):
                    if row and row[0] and 'Total Overdue' in str(row[0]):
                        has_summary = True
                        break
                if not has_summary:
                    warnings.append("Overdue Receivables: Summary section not found")

            wb.close()

        except Exception as e:
            errors.append(f"Excel content validation failed: {e}")

        return len(errors) == 0, errors + warnings

    def validate_data_consistency(self, report_month: date, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate data consistency across sources."""
        errors = []
        warnings = []

        scorecard = data.get('scorecard_current', {})
        trends = data.get('trends', pd.DataFrame())

        if scorecard and not trends.empty:
            # Cross-check a few KPIs between scorecard and trends
            name_to_key = {
                'Revenue': 'revenue',
                'Net Profit': 'net_profit',
                'Operating Margin': 'operating_margin_pct',
                'Total Headcount': 'total_headcount',
                'Attendance Rate': 'attendance_rate_pct',
            }

            for kpi_name, key in name_to_key.items():
                scorecard_val = scorecard.get(key)
                trend_row = trends[(trends['kpi_name'] == kpi_name) & (trends['month'] == report_month)]
                if not trend_row.empty:
                    trend_val = trend_row.iloc[0]['value']
                    if scorecard_val is not None and trend_val is not None:
                        # Allow small floating point differences
                        if abs(scorecard_val - trend_val) > 0.01:
                            warnings.append(
                                f"Data inconsistency: {kpi_name} scorecard={scorecard_val} "
                                f"vs trends={trend_val} (diff={abs(scorecard_val - trend_val):.4f})"
                            )

        # Validate DSO is only present for Sept 2026
        dso_df = data.get('dso', pd.DataFrame())
        if not dso_df.empty:
            for _, row in dso_df.iterrows():
                if row['report_date'] != date(2026, 9, 30) and row['report_date'] != date(2026, 9, 1):
                    warnings.append(f"Unexpected DSO data for {row['report_date']} (expected only Sept 2026)")

        # Validate overdue receivables only for Sept 2026
        overdue_df = data.get('overdue_receivables', pd.DataFrame())
        if not overdue_df.empty:
            for _, row in overdue_df.iterrows():
                if row['report_date'] != date(2026, 9, 30):
                    warnings.append(f"Unexpected overdue receivables for {row['report_date']} (expected only Sept 2026)")

        return len(errors) == 0, errors + warnings

    def validate_september_2026_output(self, excel_path: str, pdf_path: str) -> Tuple[bool, List[str]]:
        """Specific validation for September 2026 report against verified values."""
        errors = []
        warnings = []

        verified = {
            'revenue': 80268200.0,
            'net_profit': 14985979.13,
            'operating_margin_pct': 18.67,
            'dso_days': 47.61,
            'total_headcount': 441,
            'attrition_rolling_12m_pct': 13.877054,
            'attendance_rate_pct': 95.187136,
            'overtime_share_pct': 0.347618
        }

        def _clean_val(val):
            """Clean formatted string to extract numeric value."""
            if val is None:
                return None
            if isinstance(val, str):
                clean = val.replace('₹', '').replace(',', '').replace('%', '').strip()
                try:
                    return float(clean)
                except ValueError:
                    return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        # Validate Excel
        try:
            wb = openpyxl.load_workbook(excel_path, data_only=True)
            ws = wb['KPI Summary']

            # Extract KPI values from KPI Summary sheet
            for row in ws.iter_rows(min_row=1, max_col=6, values_only=True):
                if row and row[0]:
                    kpi_label = str(row[0]).strip().lower()
                    current_val = row[1]
                    num_val = _clean_val(current_val)

                    if 'revenue' in kpi_label and 'net' not in kpi_label:
                        if num_val is not None and abs(num_val - verified['revenue']) > 1:
                            errors.append(f"Revenue mismatch: Excel={current_val}, Expected={verified['revenue']}")
                    elif 'net profit' in kpi_label:
                        if num_val is not None and abs(num_val - verified['net_profit']) > 1:
                            errors.append(f"Net Profit mismatch: Excel={current_val}, Expected={verified['net_profit']}")
                    elif 'operating margin' in kpi_label:
                        if num_val is not None and abs(num_val - verified['operating_margin_pct']) > 0.02:
                            errors.append(f"Operating Margin mismatch: Excel={current_val}, Expected={verified['operating_margin_pct']}")
                    elif 'headcount' in kpi_label:
                        if num_val is not None and int(num_val) != verified['total_headcount']:
                            errors.append(f"Headcount mismatch: Excel={current_val}, Expected={verified['total_headcount']}")
                    elif 'attrition' in kpi_label:
                        if num_val is not None and abs(num_val - verified['attrition_rolling_12m_pct']) > 0.02:
                            errors.append(f"Attrition mismatch: Excel={current_val}, Expected={verified['attrition_rolling_12m_pct']}")
                    elif 'attendance' in kpi_label:
                        if num_val is not None and abs(num_val - verified['attendance_rate_pct']) > 0.02:
                            errors.append(f"Attendance mismatch: Excel={current_val}, Expected={verified['attendance_rate_pct']}")
                    elif 'overtime' in kpi_label:
                        if num_val is not None and abs(num_val - verified['overtime_share_pct']*100) > 0.02:
                            errors.append(f"Overtime Share mismatch: Excel={current_val}, Expected={verified['overtime_share_pct']*100}")

            wb.close()
        except Exception as e:
            errors.append(f"September 2026 Excel validation failed: {e}")

        return len(errors) == 0, errors + warnings


def run_full_validation(report_month: date, pdf_path: str, excel_path: str,
                        data: Dict[str, Any], snapshot_dir: str = None) -> Dict[str, Any]:
    """Run all validations and return comprehensive results."""
    validator = ReportValidator(snapshot_dir=snapshot_dir)

    results = {
        'report_month': report_month.isoformat(),
        'timestamp': pd.Timestamp.now().isoformat(),
        'validations': {}
    }

    # File existence
    pdf_ok, pdf_msg = validator.validate_pdf_exists(pdf_path)
    results['validations']['pdf_exists'] = {'passed': pdf_ok, 'message': pdf_msg}

    excel_ok, excel_msg = validator.validate_excel_exists(excel_path)
    results['validations']['excel_exists'] = {'passed': excel_ok, 'message': excel_msg}

    # Content validation
    if excel_ok:
        content_ok, content_msgs = validator.validate_excel_content(excel_path, report_month)
        results['validations']['excel_content'] = {'passed': content_ok, 'messages': content_msgs}

    # Data consistency
    consistency_ok, consistency_msgs = validator.validate_data_consistency(report_month, data)
    results['validations']['data_consistency'] = {'passed': consistency_ok, 'messages': consistency_msgs}

    # September 2026 specific
    if report_month == date(2026, 9, 1):
        sept_ok, sept_msgs = validator.validate_september_2026_output(excel_path, pdf_path)
        results['validations']['september_2026_verified'] = {'passed': sept_ok, 'messages': sept_msgs}

    # Overall
    all_passed = all(v.get('passed', False) for v in results['validations'].values())
    results['all_passed'] = all_passed

    return results