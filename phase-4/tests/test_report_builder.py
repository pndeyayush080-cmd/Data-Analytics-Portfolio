"""
Tests for the automated report builder.
Run with: python -m pytest phase-4/tests/test_report_builder.py -v
"""

import pytest
import os
import sys
import openpyxl
from datetime import date
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_fetcher import DataFetcher, format_value, get_kpi_metadata
from report_builder import ReportBuilder, parse_month_string
from validation import ReportValidator, run_full_validation
from pdf_generator import generate_pdf_report, PDFReportGenerator
from excel_generator import generate_excel_report, ExcelReportGenerator


class TestDataFetcher:
    """Tests for data fetching."""

    @pytest.fixture
    def fetcher(self):
        return DataFetcher()  # Use default path

    def test_connection(self, fetcher):
        """Test database connection works."""
        with fetcher:
            months = fetcher.get_available_months()
            assert len(months) == 18
            assert months[0] == date(2025, 4, 1)
            assert months[-1] == date(2026, 9, 1)

    def test_scorecard_data(self, fetcher):
        """Test scorecard data fetching."""
        with fetcher:
            df = fetcher.get_company_scorecard()
            assert len(df) == 18
            assert list(df.columns) == ['month', 'revenue', 'net_profit', 'operating_margin_pct',
                                         'dso_days', 'total_headcount', 'attrition_rolling_12m_pct',
                                         'attendance_rate_pct', 'overtime_share_pct']

    def test_september_2026_verified_values(self, fetcher):
        """Test September 2026 data matches verified values."""
        with fetcher:
            validation = fetcher.validate_september_2026_data()

        expected = {
            'revenue': 80268200.0,
            'net_profit': 14985979.13,
            'operating_margin_pct': 18.67,
            'dso_days': 47.61,
            'total_headcount': 441,
            'attrition_rolling_12m_pct': 13.877054,
            'attendance_rate_pct': 95.187136,
            'overtime_share_pct': 0.347618
        }

        for key, expected_val in expected.items():
            assert validation[key], f"{key} validation failed. Expected ~{expected_val}"

    def test_kpi_trends(self, fetcher):
        """Test KPI trends data."""
        with fetcher:
            df = fetcher.get_kpi_trends()
            assert not df.empty
            assert 'kpi_name' in df.columns
            assert 'month' in df.columns
            assert 'value' in df.columns

            # Check we have 8 KPIs * 18 months = 144 rows (minus DSO which only has 1)
            kpi_counts = df.groupby('kpi_name').size()
            assert kpi_counts['Revenue'] == 18
            assert kpi_counts['Net Profit'] == 18
            assert kpi_counts['Operating Margin'] == 18
            assert kpi_counts['Total Headcount'] == 18
            assert kpi_counts['Attendance Rate'] == 18
            assert kpi_counts['Overtime Share'] == 18
            assert kpi_counts['Rolling 12M Attrition'] == 18
            assert kpi_counts['DSO'] == 1  # Only Sept 2026

    def test_kpi_targets(self, fetcher):
        """Test KPI targets are 'Not Set'."""
        with fetcher:
            df = fetcher.get_kpi_targets()
            assert len(df) == 8
            assert all(df['target_status'] == 'Not Set')

    def test_overdue_receivables(self, fetcher):
        """Test overdue receivables only for Sept 2026."""
        with fetcher:
            # Test Sept 2026
            sept_30 = date(2026, 9, 30)
            df = fetcher.get_overdue_receivables(sept_30)
            assert not df.empty
            assert len(df) == 28  # 28 clients
            # Check some have overdue amounts
            overdue_clients = df[df['total_overdue_receivables'] > 0]
            assert len(overdue_clients) == 9

            # Test earlier month (should be empty or not exist)
            apr_30 = date(2025, 4, 30)
            df_early = fetcher.get_overdue_receivables(apr_30)
            # May be empty or not exist - either is fine

    def test_dso_data(self, fetcher):
        """Test DSO data only available for Sept 2026."""
        with fetcher:
            df = fetcher.get_dso_data()
            assert len(df) == 1
            # report_date may be Timestamp or date
            rd = df.iloc[0]['report_date']
            if hasattr(rd, 'date'):
                rd = rd.date()
            assert rd == date(2026, 9, 30)
            assert df.iloc[0]['dso_days'] == 47.61

    def test_format_value(self):
        """Test value formatting."""
        assert format_value(None) == "N/A"
        assert format_value(1000000, "INR") == "₹1,000,000.00"
        assert format_value(18.67, "%") == "18.67%"
        assert format_value(47.61, "days") == "47.61 days"
        assert format_value(441, "count") == "441"
        assert format_value(0.347618, "%") == "0.35%"


class TestMonthParsing:
    """Tests for month string parsing."""

    def test_parse_various_formats(self):
        assert parse_month_string("2026-09") == date(2026, 9, 1)
        assert parse_month_string("2026-09-01") == date(2026, 9, 1)
        assert parse_month_string("September 2026") == date(2026, 9, 1)
        assert parse_month_string("Sep 2026") == date(2026, 9, 1)
        assert parse_month_string("202609") == date(2026, 9, 1)

    def test_parse_invalid(self):
        with pytest.raises(ValueError):
            parse_month_string("invalid")


class TestReportBuilder:
    """Tests for report builder."""

    @pytest.fixture
    def builder(self):
        return ReportBuilder(
            output_dir="reports",
            log_dir="logs"
        )

    def test_available_months(self, builder):
        months = builder.get_available_months()
        assert len(months) == 18
        assert date(2025, 4, 1) in months
        assert date(2026, 9, 1) in months

    def test_validate_report_month(self, builder):
        assert builder.validate_report_month(date(2026, 9, 1))
        assert not builder.validate_report_month(date(2026, 10, 1))
        assert not builder.validate_report_month(date(2024, 12, 1))

    def test_fetch_report_data_sept_2026(self, builder):
        data = builder.fetch_report_data(date(2026, 9, 1))

        assert 'scorecard_current' in data
        assert 'scorecard_previous' in data
        assert 'trends' in data
        assert 'targets' in data
        assert 'overdue_receivables' in data
        assert 'dso' in data
        assert 'revenue_detail' in data
        assert 'net_profit_detail' in data
        assert 'operating_margin_detail' in data

        # Verify current scorecard
        sc = data['scorecard_current']
        assert sc['revenue'] == 80268200.0
        assert sc['total_headcount'] == 441

        # Verify previous month (August 2026)
        prev = data['scorecard_previous']
        assert prev['revenue'] == 81459400.0
        assert prev['total_headcount'] == 427

        # Verify overdue receivables
        overdue = data['overdue_receivables']
        assert not overdue.empty
        assert len(overdue) == 28

        # Verify DSO
        dso = data['dso']
        assert not dso.empty
        assert dso.iloc[0]['dso_days'] == 47.61

    def test_fetch_report_data_apr_2025(self, builder):
        """Test fetching data for earliest month (no previous month)."""
        data = builder.fetch_report_data(date(2025, 4, 1))

        assert data['scorecard_current']['revenue'] == 71075300.0
        assert data['scorecard_previous'] == {}  # No previous month
        assert data['dso'].empty  # No DSO for Apr 2025
        assert data['overdue_receivables'].empty  # No overdue for Apr 2025


class TestPDFGeneration:
    """Tests for PDF generation."""

    def test_pdf_generation_sept_2026(self, tmp_path):
        """Test PDF generation for September 2026."""
        builder = ReportBuilder(output_dir=str(tmp_path))
        data = builder.fetch_report_data(date(2026, 9, 1))

        pdf_path = generate_pdf_report(date(2026, 9, 1), data, str(tmp_path))

        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 5000  # Should be substantial


class TestExcelGeneration:
    """Tests for Excel generation."""

    def test_excel_generation_sept_2026(self, tmp_path):
        """Test Excel generation for September 2026."""
        builder = ReportBuilder(output_dir=str(tmp_path))
        data = builder.fetch_report_data(date(2026, 9, 1))

        excel_path = generate_excel_report(date(2026, 9, 1), data, str(tmp_path))

        assert os.path.exists(excel_path)
        assert os.path.getsize(excel_path) > 5000

        # Validate structure
        wb = openpyxl.load_workbook(excel_path)
        expected_sheets = ['KPI Summary', 'Monthly Trends', 'Overdue Receivables', 'DSO Detail', 'Revenue & Profit']
        for sheet in expected_sheets:
            assert sheet in wb.sheetnames, f"Missing sheet: {sheet}"
        wb.close()

    def test_excel_content_sept_2026(self, tmp_path):
        """Test Excel content for September 2026 matches verified values."""
        builder = ReportBuilder(output_dir=str(tmp_path))
        data = builder.fetch_report_data(date(2026, 9, 1))

        excel_path = generate_excel_report(date(2026, 9, 1), data, str(tmp_path))

        wb = openpyxl.load_workbook(excel_path, data_only=True)
        ws = wb['KPI Summary']

        # Find KPI rows and verify values
        for row in ws.iter_rows(min_row=1, max_col=6, values_only=True):
            if row and row[0]:
                kpi_label = str(row[0]).strip().lower()
                current_val = row[1]

                # Handle formatted strings (may contain ₹ or commas)
                if current_val is not None:
                    if isinstance(current_val, str):
                        # Remove currency symbols and commas
                        clean_val = current_val.replace('₹', '').replace(',', '').replace('%', '')
                        try:
                            num_val = float(clean_val)
                        except ValueError:
                            num_val = None
                    else:
                        num_val = float(current_val)
                else:
                    num_val = None

                if 'revenue' in kpi_label and 'net' not in kpi_label:
                    assert num_val is not None
                    assert abs(num_val - 80268200.0) < 1
                elif 'net profit' in kpi_label:
                    assert num_val is not None
                    assert abs(num_val - 14985979.13) < 1
                elif 'operating margin' in kpi_label:
                    assert num_val is not None
                    assert abs(num_val - 18.67) < 0.02
                elif 'headcount' in kpi_label:
                    assert num_val is not None
                    assert int(num_val) == 441
                elif 'attrition' in kpi_label:
                    assert num_val is not None
                    assert abs(num_val - 13.877054) < 0.02
                elif 'attendance' in kpi_label:
                    assert num_val is not None
                    assert abs(num_val - 95.187136) < 0.02
                elif 'overtime' in kpi_label:
                    assert num_val is not None
                    assert abs(num_val - 34.7618) < 0.02  # Stored as percentage

        wb.close()


class TestValidation:
    """Tests for validation module."""

    def test_validation_sept_2026(self, tmp_path):
        """Test full validation for September 2026 report."""
        builder = ReportBuilder(output_dir=str(tmp_path))
        data = builder.fetch_report_data(date(2026, 9, 1))

        pdf_path = generate_pdf_report(date(2026, 9, 1), data, str(tmp_path))
        excel_path = generate_excel_report(date(2026, 9, 1), data, str(tmp_path))

        results = run_full_validation(date(2026, 9, 1), pdf_path, excel_path, data)

        assert results['all_passed'], f"Validation failed: {results}"
        assert results['validations']['pdf_exists']['passed']
        assert results['validations']['excel_exists']['passed']
        assert results['validations']['september_2026_verified']['passed']


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_report_build_sept_2026(self, tmp_path):
        """Test complete report building for September 2026."""
        builder = ReportBuilder(
            output_dir=str(tmp_path),
            log_dir=str(tmp_path / "logs")
        )

        result = builder.build_report(date(2026, 9, 1), formats=['pdf', 'excel'])

        assert result['success']
        assert 'pdf' in result['output_files']
        assert 'excel' in result['output_files']
        assert os.path.exists(result['output_files']['pdf'])
        assert os.path.exists(result['output_files']['excel'])
        assert result['validation']['all_critical_passed']

    def test_full_report_build_apr_2025(self, tmp_path):
        """Test complete report building for April 2025 (earliest month)."""
        builder = ReportBuilder(
            output_dir=str(tmp_path),
            log_dir=str(tmp_path / "logs")
        )

        result = builder.build_report(date(2025, 4, 1), formats=['pdf', 'excel'])

        assert result['success']
        assert 'pdf' in result['output_files']
        assert 'excel' in result['output_files']
        assert os.path.exists(result['output_files']['pdf'])
        assert os.path.exists(result['output_files']['excel'])


if __name__ == '__main__':
    pytest.main([__file__, '-v'])