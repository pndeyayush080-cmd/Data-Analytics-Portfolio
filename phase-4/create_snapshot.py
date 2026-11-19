#!/usr/bin/env python
"""
Create a data snapshot (CSV export) for clean-machine testing.
Exports all data needed for report generation so the tool can run
without the Phase 3 DuckDB database.
"""
import os
import sys
import pandas as pd
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from data_fetcher import DataFetcher

def create_snapshot(db_path: str = None, output_dir: str = "snapshot"):
    """Export all report data to CSV files."""
    os.makedirs(output_dir, exist_ok=True)
    
    with DataFetcher(db_path) as fetcher:
        # Get all available months
        months = fetcher.get_available_months()
        print(f"Available months: {len(months)} ({months[0]} to {months[-1]})")
        
        # Export company scorecard (all months)
        print("Exporting company scorecard...")
        scorecard = fetcher.get_company_scorecard()
        scorecard.to_csv(os.path.join(output_dir, "pq15_company_scorecard.csv"), index=False)
        print(f"  Rows: {len(scorecard)}")
        
        # Export KPI trends
        print("Exporting KPI trends...")
        trends = fetcher.get_kpi_trends()
        trends.to_csv(os.path.join(output_dir, "pq15_kpi_trends.csv"), index=False)
        print(f"  Rows: {len(trends)}")
        
        # Export KPI targets
        print("Exporting KPI targets...")
        targets = fetcher.get_kpi_targets()
        targets.to_csv(os.path.join(output_dir, "pq15_kpi_targets_company.csv"), index=False)
        print(f"  Rows: {len(targets)}")
        
        # Export revenue detail
        print("Exporting revenue detail...")
        rev = fetcher.get_revenue_detail()
        rev.to_csv(os.path.join(output_dir, "m16_revenue.csv"), index=False)
        print(f"  Rows: {len(rev)}")
        
        # Export net profit detail
        print("Exporting net profit detail...")
        np = fetcher.get_net_profit_detail()
        np.to_csv(os.path.join(output_dir, "m17_net_profit.csv"), index=False)
        print(f"  Rows: {len(np)}")
        
        # Export operating margin detail
        print("Exporting operating margin detail...")
        om = fetcher.get_operating_margin_detail()
        om.to_csv(os.path.join(output_dir, "m18_operating_margin.csv"), index=False)
        print(f"  Rows: {len(om)}")
        
        # Export DSO data
        print("Exporting DSO data...")
        dso = fetcher.get_dso_data()
        dso.to_csv(os.path.join(output_dir, "m20_dso.csv"), index=False)
        print(f"  Rows: {len(dso)}")
        
        # Export overdue receivables for each month that has data
        print("Exporting overdue receivables...")
        all_overdue = []
        for m in months:
            od = fetcher.get_overdue_receivables(m)
            if not od.empty:
                all_overdue.append(od)
        if all_overdue:
            pd.concat(all_overdue).to_csv(os.path.join(output_dir, "m21_overdue_receivables.csv"), index=False)
            print(f"  Rows: {len(pd.concat(all_overdue))}")
        else:
            # Create empty file with correct columns
            pd.DataFrame(columns=['client_id', 'client_name', 'report_date', 'overdue_invoice_count',
                                   'total_overdue_receivables', 'carried_in_overdue', 'new_invoice_overdue']).to_csv(
                os.path.join(output_dir, "m21_overdue_receivables.csv"), index=False)
            print("  No overdue data, created empty file")
        
        # Create a manifest with metadata
        manifest = {
            'created_at': pd.Timestamp.now().isoformat(),
            'source_db': db_path or 'phase-3/data/warehouse/pulseiq_clean.duckdb',
            'months': [m.isoformat() for m in months],
            'data_cutoff': '2026-09-30',
            'tables': {
                'pq15_company_scorecard': len(scorecard),
                'pq15_kpi_trends': len(trends),
                'pq15_kpi_targets_company': len(targets),
                'm16_revenue': len(rev),
                'm17_net_profit': len(np),
                'm18_operating_margin': len(om),
                'm20_dso': len(dso),
                'm21_overdue_receivables': len(pd.concat(all_overdue)) if all_overdue else 0,
            }
        }
        import json
        with open(os.path.join(output_dir, "manifest.json"), 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"\nSnapshot created in {output_dir}/")
        print("Files:")
        for f in sorted(os.listdir(output_dir)):
            size = os.path.getsize(os.path.join(output_dir, f))
            print(f"  {f} ({size:,} bytes)")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Create data snapshot for clean-machine testing')
    parser.add_argument('--db-path', default=None, help='Path to DuckDB database')
    parser.add_argument('--output-dir', default='snapshot', help='Output directory')
    args = parser.parse_args()
    
    create_snapshot(args.db_path, args.output_dir)