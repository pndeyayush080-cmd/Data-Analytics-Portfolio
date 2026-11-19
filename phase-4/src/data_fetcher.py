"""
Data fetcher module for the automated report builder.
Connects to the DuckDB database in read-only mode or loads from CSV snapshot
and provides methods to fetch all required data for report generation.
"""
import duckdb
import pandas as pd
from datetime import date
from typing import Optional, List, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetches data from the pulseiq_clean.duckdb database or CSV snapshot for report generation."""

    def __init__(self, db_path: str = None, snapshot_dir: str = None):
        """
        Initialize DataFetcher.
        
        Args:
            db_path: Path to DuckDB database. If None, uses default Phase 3 location.
            snapshot_dir: Path to CSV snapshot directory. If provided, loads from CSV instead of DB.
        """
        self.snapshot_dir = snapshot_dir
        self._snapshot_data = {}
        
        if snapshot_dir and os.path.exists(snapshot_dir):
            # Load from snapshot
            self._load_snapshot(snapshot_dir)
            self.db_path = None
            self._conn = None
            logger.info(f"DataFetcher initialized with snapshot from {snapshot_dir}")
        else:
            # Use database
            if db_path is None:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                db_path = os.path.join(base_dir, "phase-3", "data", "warehouse", "pulseiq_clean.duckdb")
            self.db_path = db_path
            self._conn = None
            logger.info(f"DataFetcher initialized with database: {db_path}")

    def _load_snapshot(self, snapshot_dir: str):
        """Load all CSV files from snapshot directory into memory."""
        csv_files = {
            'pq15_company_scorecard': 'pq15_company_scorecard.csv',
            'pq15_kpi_trends': 'pq15_kpi_trends.csv',
            'pq15_kpi_targets_company': 'pq15_kpi_targets_company.csv',
            'm16_revenue': 'm16_revenue.csv',
            'm17_net_profit': 'm17_net_profit.csv',
            'm18_operating_margin': 'm18_operating_margin.csv',
            'm20_dso': 'm20_dso.csv',
            'm21_overdue_receivables': 'm21_overdue_receivables.csv',
        }
        
        for key, filename in csv_files.items():
            path = os.path.join(snapshot_dir, filename)
            if os.path.exists(path):
                df = pd.read_csv(path)
                # Convert date columns
                if 'month' in df.columns:
                    df['month'] = pd.to_datetime(df['month']).dt.date
                if 'report_date' in df.columns:
                    df['report_date'] = pd.to_datetime(df['report_date']).dt.date
                self._snapshot_data[key] = df
                logger.debug(f"Loaded snapshot: {key} ({len(df)} rows)")
            else:
                logger.warning(f"Snapshot file not found: {path}")
                self._snapshot_data[key] = pd.DataFrame()

    def __enter__(self):
        if self.db_path:
            self._conn = duckdb.connect(self.db_path, read_only=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            self._conn.close()

    @property
    def conn(self):
        if self._conn is None and self.db_path:
            self._conn = duckdb.connect(self.db_path, read_only=True)
        return self._conn

    def _filter_by_month(self, df: pd.DataFrame, report_month: Optional[date], month_col: str = 'month') -> pd.DataFrame:
        """Filter dataframe by month <= report_month."""
        if report_month is None or df.empty:
            return df
        if month_col in df.columns:
            return df[df[month_col] <= report_month].copy()
        return df

    def get_company_scorecard(self, report_month: Optional[date] = None) -> pd.DataFrame:
        """Fetch company scorecard data."""
        if self.snapshot_dir:
            df = self._snapshot_data.get('pq15_company_scorecard', pd.DataFrame())
            return self._filter_by_month(df, report_month).sort_values('month')
        
        query = "SELECT * FROM star_schema.pq15_company_scorecard"
        params = []
        if report_month:
            query += " WHERE month <= ?"
            params.append(report_month)
        query += " ORDER BY month"
        return self.conn.execute(query, params).fetchdf()

    def get_kpi_trends(self, report_month: Optional[date] = None) -> pd.DataFrame:
        """Fetch KPI trends data."""
        if self.snapshot_dir:
            df = self._snapshot_data.get('pq15_kpi_trends', pd.DataFrame())
            return self._filter_by_month(df, report_month).sort_values(['kpi_name', 'month'])
        
        query = "SELECT * FROM star_schema.pq15_kpi_trends"
        params = []
        if report_month:
            query += " WHERE month <= ?"
            params.append(report_month)
        query += " ORDER BY kpi_name, month"
        return self.conn.execute(query, params).fetchdf()

    def get_kpi_targets(self) -> pd.DataFrame:
        """Fetch company KPI targets."""
        if self.snapshot_dir:
            return self._snapshot_data.get('pq15_kpi_targets_company', pd.DataFrame())
        return self.conn.execute("SELECT * FROM star_schema.pq15_kpi_targets_company").fetchdf()

    def get_overdue_receivables(self, report_month: date) -> pd.DataFrame:
        """Fetch overdue receivables for the given report month."""
        if self.snapshot_dir:
            df = self._snapshot_data.get('m21_overdue_receivables', pd.DataFrame())
            if df.empty:
                return df
            from calendar import monthrange
            last_day = monthrange(report_month.year, report_month.month)[1]
            report_date = date(report_month.year, report_month.month, last_day)
            return df[df['report_date'] == report_date].copy()
        
        from calendar import monthrange
        last_day = monthrange(report_month.year, report_month.month)[1]
        report_date = date(report_month.year, report_month.month, last_day)
        query = "SELECT * FROM star_schema.m21_overdue_receivables WHERE report_date = ?"
        return self.conn.execute(query, [report_date]).fetchdf()

    def get_dso_data(self, report_month: Optional[date] = None) -> pd.DataFrame:
        """Fetch DSO data."""
        if self.snapshot_dir:
            df = self._snapshot_data.get('m20_dso', pd.DataFrame())
            if df.empty:
                return df
            if report_month:
                from calendar import monthrange
                last_day = monthrange(report_month.year, report_month.month)[1]
                report_date = date(report_month.year, report_month.month, last_day)
                df = df[df['report_date'] <= report_date]
            return df.sort_values('report_date')
        
        query = "SELECT * FROM star_schema.m20_dso"
        params = []
        if report_month:
            from calendar import monthrange
            last_day = monthrange(report_month.year, report_month.month)[1]
            report_date = date(report_month.year, report_month.month, last_day)
            query += " WHERE report_date <= ?"
            params.append(report_date)
        query += " ORDER BY report_date"
        return self.conn.execute(query, params).fetchdf()

    def get_revenue_detail(self, report_month: Optional[date] = None) -> pd.DataFrame:
        """Fetch revenue detail from m16_revenue."""
        if self.snapshot_dir:
            df = self._snapshot_data.get('m16_revenue', pd.DataFrame())
            return self._filter_by_month(df, report_month).sort_values('month')
        
        query = "SELECT * FROM star_schema.m16_revenue"
        params = []
        if report_month:
            query += " WHERE month <= ?"
            params.append(report_month.strftime('%Y-%m'))
        query += " ORDER BY month"
        return self.conn.execute(query, params).fetchdf()

    def get_net_profit_detail(self, report_month: Optional[date] = None) -> pd.DataFrame:
        """Fetch net profit detail from m17_net_profit."""
        if self.snapshot_dir:
            df = self._snapshot_data.get('m17_net_profit', pd.DataFrame())
            return self._filter_by_month(df, report_month).sort_values('month')
        
        query = "SELECT * FROM star_schema.m17_net_profit"
        params = []
        if report_month:
            query += " WHERE month <= ?"
            params.append(report_month.strftime('%Y-%m'))
        query += " ORDER BY month"
        return self.conn.execute(query, params).fetchdf()

    def get_operating_margin_detail(self, report_month: Optional[date] = None) -> pd.DataFrame:
        """Fetch operating margin detail from m18_operating_margin."""
        if self.snapshot_dir:
            df = self._snapshot_data.get('m18_operating_margin', pd.DataFrame())
            return self._filter_by_month(df, report_month).sort_values('month')
        
        query = "SELECT * FROM star_schema.m18_operating_margin"
        params = []
        if report_month:
            query += " WHERE month <= ?"
            params.append(report_month.strftime('%Y-%m'))
        query += " ORDER BY month"
        return self.conn.execute(query, params).fetchdf()

    def get_available_months(self) -> List[date]:
        """Get list of available months in the scorecard."""
        if self.snapshot_dir:
            df = self._snapshot_data.get('pq15_company_scorecard', pd.DataFrame())
            if df.empty:
                return []
            return sorted(df['month'].unique().tolist())
        
        query = "SELECT month FROM star_schema.pq15_company_scorecard ORDER BY month"
        result = self.conn.execute(query).fetchall()
        return [r[0] for r in result]

    def get_scorecard_for_month(self, report_month: date) -> Dict[str, Any]:
        """Get the scorecard row for a specific month."""
        if self.snapshot_dir:
            df = self._snapshot_data.get('pq15_company_scorecard', pd.DataFrame())
            row = df[df['month'] == report_month]
            if row.empty:
                return None
            columns = ['month', 'revenue', 'net_profit', 'operating_margin_pct', 'dso_days',
                       'total_headcount', 'attrition_rolling_12m_pct', 'attendance_rate_pct', 'overtime_share_pct']
            return dict(zip(columns, row.iloc[0].values))
        
        query = "SELECT * FROM star_schema.pq15_company_scorecard WHERE month = ?"
        result = self.conn.execute(query, [report_month]).fetchone()
        if result is None:
            return None
        columns = ['month', 'revenue', 'net_profit', 'operating_margin_pct', 'dso_days',
                   'total_headcount', 'attrition_rolling_12m_pct', 'attendance_rate_pct', 'overtime_share_pct']
        return dict(zip(columns, result))

    def validate_september_2026_data(self) -> Dict[str, bool]:
        """Validate that September 2026 data matches verified values."""
        from datetime import date
        sept_2026 = date(2026, 9, 1)
        scorecard = self.get_scorecard_for_month(sept_2026)
        if scorecard is None:
            return {"error": "September 2026 data not found"}

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

        results = {}
        for key, expected_val in expected.items():
            actual_val = scorecard.get(key)
            if actual_val is None:
                results[key] = False
            elif isinstance(expected_val, float):
                results[key] = abs(actual_val - expected_val) < 0.01
            else:
                results[key] = actual_val == expected_val

        return results


def format_value(value, unit: str = "", precision: int = 2) -> str:
    """Format a value for display in reports."""
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        if unit == "INR" or unit == "₹":
            return f"₹{value:,.{precision}f}"
        elif unit == "%":
            return f"{value:.{precision}f}%"
        elif unit == "days":
            return f"{value:.{precision}f} days"
        elif unit == "count":
            return f"{int(value):,}"
        else:
            return f"{value:,.{precision}f}"
    return str(value)


def get_kpi_metadata() -> Dict[str, Dict[str, str]]:
    """Return metadata for each KPI."""
    return {
        'revenue': {'name': 'Revenue', 'unit': 'INR', 'direction': 'Higher is better'},
        'net_profit': {'name': 'Net Profit', 'unit': 'INR', 'direction': 'Higher is better'},
        'operating_margin_pct': {'name': 'Operating Margin', 'unit': '%', 'direction': 'Higher is better'},
        'dso_days': {'name': 'DSO', 'unit': 'days', 'direction': 'Lower is better'},
        'total_headcount': {'name': 'Total Headcount', 'unit': 'count', 'direction': 'Context dependent'},
        'attrition_rolling_12m_pct': {'name': 'Rolling 12M Attrition', 'unit': '%', 'direction': 'Lower is better'},
        'attendance_rate_pct': {'name': 'Attendance Rate', 'unit': '%', 'direction': 'Higher is better'},
        'overtime_share_pct': {'name': 'Overtime Share', 'unit': '%', 'direction': 'Lower is better'},
    }