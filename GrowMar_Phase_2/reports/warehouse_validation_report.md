# Warehouse Validation Report

**Validation Timestamp:** 2026-10-31T11:54:36
**Database:** `data\warehouse\pulseiq.duckdb`
**Source Workbook:** `data\raw\03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx`
**Project Root:** `C:\Users\Ayush Pandey\OneDrive\Documents\GrowMar_Phase_2`

## Executive Summary

- **Tables Validated:** 25
- **PASS:** 20
- **FAIL:** 0
- **WARNING:** 5

## Global Checks

- **PASS** | table_presence | All 25 expected tables present, no unexpected tables

## Table-by-Table Validation

### ⚠️ budget_payroll_dept_month

- **Expected Rows:** 198
- **Actual Rows:** 198
- **Row Count Status:** PASS
- **Overall Status:** WARNING

#### Schema Checks

- **PASS** | row_count | DB=198, Expected=198, Source=198
- **PASS** | key_column_present | Key column 'department_id' found in schema

#### Integrity Checks

- **WARNING** | duplicate_keys | Key column 'department_id' has 187 duplicate values

#### Data Quality Checks

- **PASS** | null_keys | Key column 'department_id' has no NULLs

### ✅ dim_account

- **Expected Rows:** 47
- **Actual Rows:** 47
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=47, Expected=47, Source=47
- **PASS** | key_column_present | Key column 'account_code' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'account_code' has no duplicates

#### Data Quality Checks

- **PASS** | null_keys | Key column 'account_code' has no NULLs

### ✅ dim_client

- **Expected Rows:** 28
- **Actual Rows:** 28
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=28, Expected=28, Source=28
- **PASS** | key_column_present | Key column 'client_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'client_id' has no duplicates

#### Data Quality Checks

- **PASS** | null_keys | Key column 'client_id' has no NULLs

### ✅ dim_date

- **Expected Rows:** 2,557
- **Actual Rows:** 2,557
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=2,557, Expected=2,557, Source=2,557
- **PASS** | key_column_present | Key column 'date_key' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'date_key' has no duplicates

#### Data Quality Checks

- **PASS** | null_keys | Key column 'date_key' has no NULLs

### ✅ dim_department

- **Expected Rows:** 11
- **Actual Rows:** 11
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=11, Expected=11, Source=11
- **PASS** | key_column_present | Key column 'department_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'department_id' has no duplicates

#### Data Quality Checks

- **PASS** | null_keys | Key column 'department_id' has no NULLs

### ✅ dim_employee

- **Expected Rows:** 1,606
- **Actual Rows:** 1,606
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=1,606, Expected=1,606, Source=1,606
- **PASS** | key_column_present | Key column 'employee_key' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'employee_key' has no duplicates

#### Data Quality Checks

- **PASS** | null_keys | Key column 'employee_key' has no NULLs

### ✅ dim_leave_type

- **Expected Rows:** 6
- **Actual Rows:** 6
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=6, Expected=6, Source=6
- **PASS** | key_column_present | Key column 'leave_type_code' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'leave_type_code' has no duplicates

#### Data Quality Checks

- **PASS** | null_keys | Key column 'leave_type_code' has no NULLs

### ✅ dim_location

- **Expected Rows:** 9
- **Actual Rows:** 9
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=9, Expected=9, Source=9
- **PASS** | key_column_present | Key column 'work_location' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'work_location' has no duplicates

#### Data Quality Checks

- **PASS** | null_keys | Key column 'work_location' has no NULLs

### ✅ dim_role

- **Expected Rows:** 58
- **Actual Rows:** 58
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=58, Expected=58, Source=58
- **PASS** | key_column_present | Key column 'role_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'role_id' has no duplicates

#### Data Quality Checks

- **PASS** | null_keys | Key column 'role_id' has no NULLs

### ✅ dim_sprint

- **Expected Rows:** 38
- **Actual Rows:** 38
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=38, Expected=38, Source=38
- **PASS** | key_column_present | Key column 'sprint_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'sprint_id' has no duplicates

#### Data Quality Checks

- **PASS** | null_keys | Key column 'sprint_id' has no NULLs

### ✅ dim_team

- **Expected Rows:** 16
- **Actual Rows:** 16
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=16, Expected=16, Source=16
- **PASS** | key_column_present | Key column 'team_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'team_id' has no duplicates

#### Data Quality Checks

- **PASS** | null_keys | Key column 'team_id' has no NULLs

### ✅ dim_vendor

- **Expected Rows:** 30
- **Actual Rows:** 30
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=30, Expected=30, Source=30
- **PASS** | key_column_present | Key column 'vendor_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'vendor_id' has no duplicates

#### Data Quality Checks

- **PASS** | null_keys | Key column 'vendor_id' has no NULLs

### ✅ fact_anomaly

- **Expected Rows:** 405
- **Actual Rows:** 405
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=405, Expected=405, Source=405
- **PASS** | key_column_present | Key column 'result_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'result_id' has no duplicates
- **PASS** | orphan_fk | FK 'employee_id' -> 'dim_employee.employee_id' has no orphans
- **PASS** | orphan_fk | FK 'period_key' -> 'dim_date.date_key' has no orphans

#### Data Quality Checks

- **PASS** | null_keys | Key column 'result_id' has no NULLs

### ✅ fact_attendance_monthly

- **Expected Rows:** 7,343
- **Actual Rows:** 7,343
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=7,343, Expected=7,343, Source=7,343
- **PASS** | key_column_present | Key column 'attendance_fact_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'attendance_fact_id' has no duplicates
- **PASS** | orphan_fk | FK 'employee_key' -> 'dim_employee.employee_key' has no orphans
- **PASS** | orphan_fk | FK 'date_key' -> 'dim_date.date_key' has no orphans
- **PASS** | orphan_fk | FK 'department_id' -> 'dim_department.department_id' has no orphans

#### Data Quality Checks

- **PASS** | null_keys | Key column 'attendance_fact_id' has no NULLs

### ✅ fact_attrition_risk

- **Expected Rows:** 430
- **Actual Rows:** 430
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=430, Expected=430, Source=430
- **PASS** | key_column_present | Key column 'prediction_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'prediction_id' has no duplicates
- **PASS** | orphan_fk | FK 'employee_id' -> 'dim_employee.employee_id' has no orphans
- **PASS** | orphan_fk | FK 'as_of_date_key' -> 'dim_date.date_key' has no orphans
- **PASS** | orphan_fk | FK 'department_id' -> 'dim_department.department_id' has no orphans
- **PASS** | orphan_fk | FK 'employee_key' -> 'dim_employee.employee_key' has no orphans

#### Data Quality Checks

- **PASS** | null_keys | Key column 'prediction_id' has no NULLs

### ✅ fact_expense

- **Expected Rows:** 501
- **Actual Rows:** 501
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=501, Expected=501, Source=501
- **PASS** | key_column_present | Key column 'expense_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'expense_id' has no duplicates
- **PASS** | orphan_fk | FK 'expense_date_key' -> 'dim_date.date_key' has no orphans
- **PASS** | orphan_fk | FK 'category_account' -> 'dim_account.account_code' has no orphans
- **PASS** | orphan_fk | FK 'vendor_id' -> 'dim_vendor.vendor_id' has no orphans
- **PASS** | orphan_fk | FK 'department_id' -> 'dim_department.department_id' has no orphans

#### Data Quality Checks

- **PASS** | null_keys | Key column 'expense_id' has no NULLs

### ⚠️ fact_forecast

- **Expected Rows:** 72
- **Actual Rows:** 72
- **Row Count Status:** PASS
- **Overall Status:** WARNING

#### Schema Checks

- **PASS** | row_count | DB=72, Expected=72, Source=72
- **PASS** | key_column_present | Key column 'forecast_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'forecast_id' has no duplicates
- **WARNING** | orphan_fk | FK 'department_id' -> 'dim_department.department_id' has 12 orphan values
- **WARNING** | orphan_fk | FK 'forecast_month_key' -> 'dim_date.date_key' has 36 orphan values

#### Data Quality Checks

- **PASS** | null_keys | Key column 'forecast_id' has no NULLs

### ⚠️ fact_headcount_monthly

- **Expected Rows:** 891
- **Actual Rows:** 891
- **Row Count Status:** PASS
- **Overall Status:** WARNING

#### Schema Checks

- **PASS** | row_count | DB=891, Expected=891, Source=891
- **PASS** | key_column_present | Key column 'date_key' found in schema

#### Integrity Checks

- **WARNING** | duplicate_keys | Key column 'date_key' has 810 duplicate values
- **PASS** | orphan_fk | FK 'department_id' -> 'dim_department.department_id' has no orphans

#### Data Quality Checks

- **PASS** | null_keys | Key column 'date_key' has no NULLs

### ✅ fact_invoice

- **Expected Rows:** 743
- **Actual Rows:** 743
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=743, Expected=743, Source=743
- **PASS** | key_column_present | Key column 'invoice_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'invoice_id' has no duplicates
- **PASS** | orphan_fk | FK 'invoice_date_key' -> 'dim_date.date_key' has no orphans
- **PASS** | orphan_fk | FK 'client_id' -> 'dim_client.client_id' has no orphans
- **PASS** | orphan_fk | FK 'service_line_account' -> 'dim_account.account_code' has no orphans

#### Data Quality Checks

- **PASS** | null_keys | Key column 'invoice_id' has no NULLs

### ✅ fact_invoice_payment

- **Expected Rows:** 709
- **Actual Rows:** 709
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=709, Expected=709, Source=709
- **PASS** | key_column_present | Key column 'payment_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'payment_id' has no duplicates
- **PASS** | orphan_fk | FK 'invoice_id' -> 'fact_invoice.invoice_id' has no orphans
- **PASS** | orphan_fk | FK 'payment_date_key' -> 'dim_date.date_key' has no orphans

#### Data Quality Checks

- **PASS** | null_keys | Key column 'payment_id' has no NULLs

### ✅ fact_leave

- **Expected Rows:** 3,441
- **Actual Rows:** 3,441
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=3,441, Expected=3,441, Source=3,441
- **PASS** | key_column_present | Key column 'leave_request_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'leave_request_id' has no duplicates
- **PASS** | orphan_fk | FK 'employee_key' -> 'dim_employee.employee_key' has no orphans
- **PASS** | orphan_fk | FK 'leave_type_code' -> 'dim_leave_type.leave_type_code' has no orphans
- **PASS** | orphan_fk | FK 'start_date_key' -> 'dim_date.date_key' has no orphans
- **PASS** | orphan_fk | FK 'end_date_key' -> 'dim_date.date_key' has no orphans

#### Data Quality Checks

- **PASS** | null_keys | Key column 'leave_request_id' has no NULLs

### ✅ fact_ledger

- **Expected Rows:** 6,784
- **Actual Rows:** 6,784
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=6,784, Expected=6,784, Source=6,784
- **PASS** | key_column_present | Key column 'line_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'line_id' has no duplicates
- **PASS** | orphan_fk | FK 'date_key' -> 'dim_date.date_key' has no orphans
- **PASS** | orphan_fk | FK 'account_code' -> 'dim_account.account_code' has no orphans
- **PASS** | orphan_fk | FK 'cost_center_department_id' -> 'dim_department.department_id' has no orphans

#### Data Quality Checks

- **PASS** | null_keys | Key column 'line_id' has no NULLs

### ⚠️ fact_payroll

- **Expected Rows:** 7,344
- **Actual Rows:** 7,344
- **Row Count Status:** PASS
- **Overall Status:** WARNING

#### Schema Checks

- **PASS** | row_count | DB=7,344, Expected=7,344, Source=7,344
- **PASS** | key_column_present | Key column 'payroll_item_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'payroll_item_id' has no duplicates
- **WARNING** | orphan_fk | FK 'employee_key' -> 'dim_employee.employee_key' has 2 orphan values
- **PASS** | orphan_fk | FK 'date_key' -> 'dim_date.date_key' has no orphans
- **PASS** | orphan_fk | FK 'department_id' -> 'dim_department.department_id' has no orphans
- **PASS** | orphan_fk | FK 'role_id' -> 'dim_role.role_id' has no orphans

#### Data Quality Checks

- **PASS** | null_keys | Key column 'payroll_item_id' has no NULLs

### ✅ fact_task

- **Expected Rows:** 28,868
- **Actual Rows:** 28,868
- **Row Count Status:** PASS
- **Overall Status:** PASS

#### Schema Checks

- **PASS** | row_count | DB=28,868, Expected=28,868, Source=28,868
- **PASS** | key_column_present | Key column 'task_id' found in schema

#### Integrity Checks

- **PASS** | duplicate_keys | Key column 'task_id' has no duplicates
- **PASS** | orphan_fk | FK 'team_id' -> 'dim_team.team_id' has no orphans
- **PASS** | orphan_fk | FK 'sprint_id' -> 'dim_sprint.sprint_id' has no orphans
- **PASS** | orphan_fk | FK 'assignee_employee_id' -> 'dim_employee.employee_id' has no orphans

#### Data Quality Checks

- **PASS** | null_keys | Key column 'task_id' has no NULLs

### ⚠️ kpi_targets

- **Expected Rows:** 180
- **Actual Rows:** 180
- **Row Count Status:** PASS
- **Overall Status:** WARNING

#### Schema Checks

- **PASS** | row_count | DB=180, Expected=180, Source=180
- **PASS** | key_column_present | Key column 'month' found in schema

#### Integrity Checks

- **WARNING** | duplicate_keys | Key column 'month' has 162 duplicate values
- **PASS** | orphan_fk | FK 'department_id' -> 'dim_department.department_id' has no orphans

#### Data Quality Checks

- **PASS** | null_keys | Key column 'month' has no NULLs

## Summary of Findings

- **Total Checks:** 136
- **FAIL:** 0
- **WARNING:** 6
- **PASS:** 130

**Overall Result: ⚠️ PASSED WITH WARNINGS**

---
*Report generated: 2026-10-31T11:54:36*