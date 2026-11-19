"""
Main report builder module for the automated report builder.
Orchestrates data fetching, validation, and report generation (PDF + Excel).
"""

import logging
import sys
from datetime import date, datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

# Handle both module and direct execution
try:
    from .data_fetcher import DataFetcher, format_value
    from .pdf_generator import generate_pdf_report
    from .excel_generator import generate_excel_report
except ImportError:
    from data_fetcher import DataFetcher, format_value
    from pdf_generator import generate_pdf_report
    from excel_generator import generate_excel_report

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ReportBuilder:
    """Main orchestrator for building automated monthly reports."""

    def __init__(self, db_path: str = None, snapshot_dir: str = None,
                 output_dir: str = "reports", log_dir: str = "logs"):
        # Only set default db_path if neither db_path nor snapshot_dir is provided
        if db_path is None and snapshot_dir is None:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base_dir, "phase-3", "data", "warehouse", "pulseiq_clean.duckdb")
        self.db_path = db_path
        self.snapshot_dir = snapshot_dir
        self.output_dir = Path(output_dir)
        self.log_dir = Path(log_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Setup file logging
        self._setup_file_logging()

    def _setup_file_logging(self):
        """Setup file logging in addition to console logging."""
        log_file = self.log_dir / f"report_builder_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)

    def get_available_months(self) -> List[date]:
        """Get list of available reporting months."""
        with DataFetcher(self.db_path, self.snapshot_dir) as fetcher:
            return fetcher.get_available_months()

    def validate_report_month(self, report_month: date) -> bool:
        """Validate that the report month is available."""
        available = self.get_available_months()
        return report_month in available

    def fetch_report_data(self, report_month: date) -> Dict[str, Any]:
        """Fetch all data needed for the report."""
        logger.info(f"Fetching data for report month: {report_month}")

        with DataFetcher(self.db_path, self.snapshot_dir) as fetcher:
            # Get scorecard for current and previous month
            scorecard_current = fetcher.get_scorecard_for_month(report_month)

            # Find previous month
            available_months = fetcher.get_available_months()
            prev_month = None
            for m in reversed(available_months):
                if m < report_month:
                    prev_month = m
                    break

            scorecard_previous = None
            if prev_month:
                scorecard_previous = fetcher.get_scorecard_for_month(prev_month)

            # Get trends up to report month
            trends = fetcher.get_kpi_trends(report_month)

            # Get targets
            targets = fetcher.get_kpi_targets()

            # Get overdue receivables for report month
            overdue_receivables = fetcher.get_overdue_receivables(report_month)

            # Get DSO data
            dso = fetcher.get_dso_data(report_month)

            # Get detail views
            revenue_detail = fetcher.get_revenue_detail(report_month)
            net_profit_detail = fetcher.get_net_profit_detail(report_month)
            operating_margin_detail = fetcher.get_operating_margin_detail(report_month)

        data = {
            'scorecard_current': scorecard_current or {},
            'scorecard_previous': scorecard_previous or {},
            'trends': trends,
            'targets': targets,
            'overdue_receivables': overdue_receivables,
            'dso': dso,
            'revenue_detail': revenue_detail,
            'net_profit_detail': net_profit_detail,
            'operating_margin_detail': operating_margin_detail,
        }

        logger.info(f"Data fetched successfully for {report_month}")
        return data

    def validate_data(self, report_month: date, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the fetched data against known values."""
        logger.info(f"Validating data for {report_month}")

        validation_results = {
            'report_month': report_month.isoformat(),
            'timestamp': datetime.now().isoformat(),
            'checks': {}
        }

        # Validate September 2026 specifically
        if report_month == date(2026, 9, 1):
            with DataFetcher(self.db_path, self.snapshot_dir) as fetcher:
                sept_validation = fetcher.validate_september_2026_data()
            validation_results['checks']['september_2026_verified'] = sept_validation
            all_passed = all(sept_validation.values())
            validation_results['checks']['september_2026_all_passed'] = all_passed
            if not all_passed:
                logger.warning(f"September 2026 validation failed: {sept_validation}")
            else:
                logger.info("September 2026 validation passed")

        # Check for required data
        scorecard = data.get('scorecard_current', {})
        required_kpis = ['revenue', 'net_profit', 'operating_margin_pct', 'total_headcount',
                         'attrition_rolling_12m_pct', 'attendance_rate_pct', 'overtime_share_pct']

        for kpi in required_kpis:
            val = scorecard.get(kpi)
            validation_results['checks'][f'{kpi}_present'] = val is not None
            if val is None:
                logger.warning(f"Missing required KPI: {kpi}")

        # Check DSO availability
        dso_df = data.get('dso')
        has_dso = dso_df is not None and not dso_df.empty
        validation_results['checks']['dso_available'] = has_dso
        if not has_dso:
            logger.info(f"DSO not available for {report_month} (expected for months before Sept 2026)")

        # Check overdue receivables
        overdue_df = data.get('overdue_receivables')
        has_overdue = overdue_df is not None and not overdue_df.empty
        validation_results['checks']['overdue_receivables_available'] = has_overdue

        # Overall status
        critical_checks = [k for k in validation_results['checks'] if k.endswith('_present')]
        validation_results['all_critical_passed'] = all(validation_results['checks'].get(k, False) for k in critical_checks)

        logger.info(f"Validation complete. All critical checks passed: {validation_results['all_critical_passed']}")
        return validation_results

    def generate_reports(self, report_month: date, data: Dict[str, Any],
                         formats: List[str] = None) -> Dict[str, str]:
        """Generate reports in specified formats."""
        if formats is None:
            formats = ['pdf', 'excel']

        output_files = {}

        if 'pdf' in formats:
            logger.info("Generating PDF report...")
            pdf_path = generate_pdf_report(report_month, data, str(self.output_dir))
            output_files['pdf'] = pdf_path

        if 'excel' in formats:
            logger.info("Generating Excel report...")
            excel_path = generate_excel_report(report_month, data, str(self.output_dir))
            output_files['excel'] = excel_path

        logger.info(f"Reports generated: {output_files}")
        return output_files

    def build_report(self, report_month: date, formats: List[str] = None,
                     skip_validation: bool = False) -> Dict[str, Any]:
        """Build complete report for a given month."""
        logger.info(f"Starting report build for {report_month}")

        # Validate month
        if not self.validate_report_month(report_month):
            available = self.get_available_months()
            raise ValueError(
                f"Report month {report_month} not available. "
                f"Available months: {', '.join(m.strftime('%Y-%m') for m in available)}"
            )

        # Fetch data
        data = self.fetch_report_data(report_month)

        # Validate data
        validation = {}
        if not skip_validation:
            validation = self.validate_data(report_month, data)
            if not validation.get('all_critical_passed', False):
                logger.warning("Some critical validation checks failed")

        # Generate reports
        output_files = self.generate_reports(report_month, data, formats)

        result = {
            'report_month': report_month.isoformat(),
            'generated_at': datetime.now().isoformat(),
            'output_files': output_files,
            'validation': validation,
            'success': True
        }

        logger.info(f"Report build completed successfully for {report_month}")
        return result


def parse_month_string(month_str: str) -> date:
    """Parse month string in various formats to date (first day of month)."""
    formats = ['%Y-%m', '%Y-%m-%d', '%B %Y', '%b %Y', '%Y%m']
    for fmt in formats:
        try:
            return datetime.strptime(month_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse month string: {month_str}. Use formats like '2026-09', '2026-09-01', 'September 2026', 'Sep 2026', '202609'")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="PulseIQ Automated Monthly Report Builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.report_builder --month 2026-09
  python -m src.report_builder --month "September 2026" --format pdf excel
  python -m src.report_builder --list-months
  python -m src.report_builder --month 2026-09 --skip-validation
        """
    )

    parser.add_argument('--month', '-m', type=str, help='Report month (e.g., 2026-09, "September 2026")')
    parser.add_argument('--format', '-f', nargs='+', choices=['pdf', 'excel'], default=['pdf', 'excel'],
                        help='Output formats (default: pdf excel)')
    parser.add_argument('--list-months', '-l', action='store_true', help='List available reporting months')
    parser.add_argument('--skip-validation', action='store_true', help='Skip data validation')
    parser.add_argument('--db-path', default=None,
                        help='Path to DuckDB database (default: auto-detect from Phase 3)')
    parser.add_argument('--snapshot-dir', default=None,
                        help='Path to CSV snapshot directory (for clean-machine testing)')
    parser.add_argument('--output-dir', default='reports', help='Output directory for reports')
    parser.add_argument('--log-dir', default='logs', help='Log directory')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    builder = ReportBuilder(db_path=args.db_path, snapshot_dir=args.snapshot_dir,
                            output_dir=args.output_dir, log_dir=args.log_dir)

    if args.list_months:
        months = builder.get_available_months()
        print("Available reporting months:")
        for m in months:
            print(f"  {m.strftime('%Y-%m')} ({m.strftime('%B %Y')})")
        return 0

    if not args.month:
        parser.error("--month is required unless --list-months is used")

    try:
        report_month = parse_month_string(args.month)
        # Ensure it's the first day of the month
        report_month = date(report_month.year, report_month.month, 1)
    except ValueError as e:
        parser.error(str(e))

    try:
        result = builder.build_report(
            report_month=report_month,
            formats=args.format,
            skip_validation=args.skip_validation
        )

        print(f"\n✅ Report generated successfully for {report_month.strftime('%B %Y')}")
        print(f"📁 Output files:")
        for fmt, path in result['output_files'].items():
            print(f"  {fmt.upper()}: {path}")

        if result['validation']:
            val = result['validation']
            print(f"\n🔍 Validation: {'PASSED' if val.get('all_critical_passed') else 'WARNINGS'}")
            if 'september_2026_all_passed' in val.get('checks', {}):
                print(f"   September 2026 verified: {'YES' if val['checks']['september_2026_all_passed'] else 'NO'}")

        return 0

    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())