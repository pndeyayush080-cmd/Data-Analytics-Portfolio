#!/usr/bin/env python
"""
Convenience entry point for the report builder.
Run from project root: python phase-4/run_report.py --month 2026-09
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from report_builder import main

if __name__ == '__main__':
    sys.exit(main())