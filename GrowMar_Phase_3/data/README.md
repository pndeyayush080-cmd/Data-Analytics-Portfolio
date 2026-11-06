# Data Directory

This directory contains all data assets for GrowMar Phase 3 workforce analytics.

## Data Sources

### Phase 2 Database
- **Location:** `warehouse/pulseiq_clean.duckdb`
- **Description:** Cleaned star-schema database from Phase 2 (25 main tables + 9 quarantine tables)
- **Purpose:** Foundation for all Phase 3 analytics and predictions
- **Access:** Read-only for analytics pipeline

### Phase 3 Data Assets

**ML Training Data:**
- `warehouse/pulseiq_clean.duckdb` - Primary source for training ML models
- `warehouse/pulseiq.duckdb` - Raw source (for comparison/validation)

**Generated Data:**
- `warehouse/pulseiq_forecast.duckdb` - Production forecast database
- `warehouse/pulseiq_predictions.duckdb` - Model predictions and scores
- `warehouse/pulseiq_enhanced.duckdb` - Enhanced dataset with derived features

**Model Artifacts:**
- `models/` - Trained ML model files (serialized)
- `models/predictions/` - Real-time prediction outputs
- `models/experiments/` - A/B test results and experiments

**Performance Data:**
- `performance/` - Model performance metrics and evaluation results
- `performance/historical/` - Historical performance benchmarks
- `performance/real-time/` - Real-time monitoring data

## Data Access Patterns

### Read Operations
- All DuckDB databases are opened in read-only mode for analytics
- Connection pooling for high-performance queries
- Scheduled data refreshes for up-to-date insights

### Write Operations
- ML models are saved to `models/` directory
- Predictions are stored in `warehouse/pulseiq_predictions.duckdb`
- Logs and metrics are written to `logs/` directory

### Data Processing Pipeline
```
1. Import clean data from Phase 2
2. Feature engineering and enrichment
3. ML model training and validation
4. Real-time prediction serving
5. Performance monitoring and evaluation
```

## Data Governance

### Data Security
- All sensitive data is encrypted at rest
- Access controls implemented for different data categories
- Audit logs for all data access and modifications

### Data Quality
- Automated validation checks for all input data
- Consistency checks between source and derived datasets
- Performance monitoring for data processing pipelines

### Data Retention
- Raw data: 7 years (regulatory requirement)
- Processed data: 5 years
- Model artifacts: 3 years
- Temporary data: 30 days

## Data Dictionary

### DuckDB Databases
| Database | Description | Size | Last Updated |
|----------|-------------|------|--------------|
| pulseiq_clean.duckdb | Clean Phase 2 database | ~1.2GB | 2026-10-31 |
| pulseiq.duckdb | Raw Phase 2 database | ~1.5GB | 2026-10-31 |
| pulseiq_forecast.duckdb | Enhanced forecast database | ~800MB | 2026-11-06 |
| pulseiq_predictions.duckdb | Model predictions | ~200MB | 2026-11-06 |

### Files
| File Type | Description | Location | Retention |
|-----------|-------------|----------|----------|
| .duckdb | DuckDB databases | data/warehouse/ | 5 years |
| .pkl | Python pickle files | data/models/ | 3 years |
| .json | JSON data files | data/warehouse/ | 1 year |
| .parquet | Parquet files | data/warehouse/ | 5 years |

## Data Access

### Local Access
```bash
# Connect to DuckDB databases
python -c "import duckdb; conn = duckdb.connect('data/warehouse/pulseiq_clean.duckdb');"

# Query data
python -c "
import duckdb
conn = duckdb.connect('data/warehouse/pulseiq_clean.duckdb')
result = conn.execute('SELECT COUNT(*) FROM fact_headcount_monthly').fetchone()
print(f'Total rows: {result[0]}')
conn.close()
"
```

### API Access
```python
import duckdb
import requests

# Connect to databases
conn = duckdb.connect('data/warehouse/pulseiq_clean.duckdb')

# API endpoints (if available)
API_BASE = 'http://localhost:8000'

# Get analytics data
response = requests.get(f'{API_BASE}/api/analytics/headcount')
headcount_data = response.json()
```

## Backup Strategy

### Regular Backups
- **Daily:** Incremental backups of modified tables
- **Weekly:** Full database backups
- **Monthly:** Archive database backups
- **Annually:** Long-term storage backups

### Backup Locations
- Primary: `data/backup/current/`
- Secondary: Cloud storage (AWS S3, Azure Blob)
- Tertiary: Off-site physical storage

## Maintenance

### Automated Maintenance
- **Vacuum:** Run vacuum on DuckDB databases monthly
- **Index optimization:** Monthly index optimization
- **Log rotation:** Daily log rotation
- **Backup verification:** Weekly backup integrity checks

### Manual Maintenance
- **Data quality checks:** Monthly data quality validation
- **Performance monitoring:** Continuous performance monitoring
- **Access review:** Quarterly access rights review

## Compliance

### Regulatory Compliance
- **GDPR:** Data protection and privacy compliance
- **CCPA:** California privacy compliance
- **SOX:** Financial data compliance
- **HIPAA:** Health data protection (if applicable)

### Industry Standards
- **ISO 27001:** Information security management
- **SOC 2:** Security, availability, and processing integrity
- **PCI DSS:** Payment card industry compliance (if applicable)

## Contact

For data access questions, technical support,,v or data governance inquiries:
- Email: data-analytics@growmar.com
- Slack: #data-analytics
- Phone: +1-555-DATA-123

---

**GrowMar Phase 3 Data Governance** | Co-authored by Claude Code <noreply@anthropic.com>