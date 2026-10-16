\# Financial Performance Analysis — Final Analytical Report



\## 1. Executive Summary



The \*\*Financial Performance Analysis\*\* project is an end-to-end data analytics project designed to evaluate financial performance across transactions, budgets, business units, regions, customers, vendors, and workforce costs.



The analysis integrates data validation, SQL database design and analysis, Python-based data cleaning and exploratory analysis, statistical testing, budget variance analysis, Power BI dashboarding, and strategic recommendations.



The final financial transaction dataset contains \*\*10,400 transactions\*\* covering the period from \*\*2022-01-01 to 2023-12-30\*\*.



Overall observed financial performance was:



\- \*\*Total Revenue:\*\* approximately ₹864.61M

\- \*\*Total Expense:\*\* approximately -₹167.74M

\- \*\*Net Performance:\*\* approximately ₹696.87M



Revenue increased from approximately \*\*₹377.43M in 2022\*\* to \*\*₹487.18M in 2023\*\*, while total expense remained broadly stable at approximately ₹83.86M and ₹83.88M in magnitude respectively.



Statistical analysis found that the 2022-to-2023 difference was statistically significant, but the effect size was small. Business-unit and regional differences were not statistically significant based on the corresponding ANOVA tests.



Budget analysis identified substantial actual-versus-budget differences, indicating that budget-setting assumptions and variance-monitoring practices require management review.



The project concludes with a four-page interactive Power BI dashboard, strategic insights, recommendations, a management action plan, and supporting analytical documentation.



\---



\## 2. Business Problem \& Objectives



\### 2.1 Business Problem



The organization requires a reliable analytical framework to understand financial performance and identify areas requiring management attention.



The project addresses the following business questions:



\- Are revenues and costs aligned with available targets?

\- Which business units and time periods underperform or overachieve?

\- Where are budget overruns or underspends?

\- Which expense categories and business units contribute most to financial variance?

\- Which customers and vendors are financially significant?

\- How do workforce costs compare across business units and regions?

\- Are data-quality issues or anomalies affecting reporting reliability?

\- What statistical evidence supports observed financial differences?

\- What actions can management take based on the findings?



\### 2.2 Project Objectives



The main objectives were to:



1\. Understand the business requirements and define a KPI framework.

2\. Validate the quality and integrity of financial data.

3\. Design and analyze a relational database structure using SQL.

4\. Integrate financial, customer, vendor, budget, and workforce datasets.

5\. Perform exploratory data analysis using Python.

6\. Apply statistical analysis and hypothesis testing.

7\. Analyze budget versus actual performance.

8\. Develop an interactive Power BI dashboard.

9\. Identify strategic insights.

10\. Provide actionable recommendations and a management action plan.

11\. Produce a complete analytical report and final presentation.



\---



\## 3. Data Sources \& Data Validation



\### 3.1 Data Sources



The project uses the following datasets:



\- Financial Transactions

\- Budget

\- Headcount

\- Customers

\- Vendors



\### 3.2 Financial Transactions



The financial transaction dataset contains fields including:



\- Transaction ID

\- Transaction Date

\- Amount

\- Account Type

\- Category

\- Business Unit

\- Region

\- Customer ID

\- Vendor ID

\- Description



The final financial transaction dataset contains:



\*\*10,400 transactions\*\*



Date range:



\*\*2022-01-01 to 2023-12-30\*\*



\### 3.3 Data Validation



Data validation was performed before downstream analytical modeling.



Validation checks included:



\- Row-count validation

\- Duplicate transaction checks

\- Transaction ID uniqueness

\- Missing-value checks

\- Data-type validation

\- Financial sign validation

\- Customer linkage validation

\- Vendor linkage validation

\- Required-column validation

\- Financial calculation validation

\- Outlier investigation



\### 3.4 Validation Results



\- Total transactions: \*\*10,400\*\*

\- Unique transaction IDs: \*\*10,400\*\*

\- Duplicate transaction IDs: \*\*0\*\*

\- Duplicate rows: \*\*0\*\*

\- Zero-value transactions: \*\*0\*\*

\- Required columns missing: \*\*0\*\*

\- Financial calculation validation: \*\*Passed\*\*

\- Transaction amount potential outliers requiring investigation: \*\*0\*\*



Customer and vendor merges preserved all \*\*10,400 transaction rows\*\*.



Missing customer and vendor attributes were retained where no underlying transaction linkage existed rather than being artificially filled.



\### 3.5 Financial Sign Convention



The transaction dataset stores:



\- Revenue as positive amounts

\- Expenses as negative amounts



Budget expense values are stored as positive values. Therefore, expense budget variance calculations were aligned with the appropriate sign convention before comparison.



\---



\## 4. SQL \& Data Integration



\### 4.1 SQL Database Design



A relational SQL structure was designed to support repeatable financial analysis.



The analytical model included:



\- Financial Transactions

\- Customers

\- Vendors

\- Budget

\- Headcount



The SQL phase included:



\- Database schema design

\- Table structures

\- Relationships

\- Data ingestion and querying

\- Financial aggregation

\- KPI calculations

\- Business-unit analysis

\- Regional analysis

\- Customer analysis

\- Vendor analysis

\- Budget analysis



\### 4.2 ER Diagram



An ER Diagram was created to document the relationships between the major analytical tables.



The relational structure provides the foundation for integrating financial activity with customer, vendor, budget, and workforce information.



\### 4.3 Data Integration



Customer and vendor information was integrated with the financial transaction dataset while preserving the original transaction grain.



The final integrated dataset maintained:



\*\*10,400 transaction rows\*\*



The SQL workflow supported downstream Python analysis and Power BI reporting.



\---



\## 5. Python EDA \& Key Findings



\### 5.1 Python Data Preparation



Python was used for:



\- SQL database connection

\- Data loading

\- Data cleaning

\- Data transformation

\- Data integration

\- Exploratory Data Analysis

\- Descriptive statistics

\- Outlier analysis

\- Analytical validation



The statistical analysis dataset contained:



\*\*10,400 rows × 32 columns\*\*



Dates were restored to datetime format and year-month values were derived for time-series analysis.



Analytical measures were created for:



\- Revenue

\- Expense

\- Net Performance

\- Absolute transaction amount



\### 5.2 Overall Financial Performance



The analysis identified:



| KPI | Result |

|---|---:|

| Total Revenue | ₹864.61M |

| Total Expense | -₹167.74M |

| Net Performance | ₹696.87M |

| Transactions | 10,400 |



The analysis uses \*\*Net Performance\*\* rather than treating the calculated result as a conventional accounting profit measure.



\### 5.3 Year-over-Year Performance



\#### 2022



\- Transactions: \*\*4,894\*\*

\- Mean transaction amount: approximately \*\*₹61.59K\*\*

\- Revenue: approximately \*\*₹377.43M\*\*

\- Expense: approximately \*\*-₹83.86M\*\*

\- Net Performance: approximately \*\*₹293.56M\*\*



\#### 2023



\- Transactions: \*\*5,506\*\*

\- Mean transaction amount: approximately \*\*₹74.56K\*\*

\- Revenue: approximately \*\*₹487.18M\*\*

\- Expense: approximately \*\*-₹83.88M\*\*

\- Net Performance: approximately \*\*₹403.30M\*\*



Revenue increased by approximately \*\*29%\*\* from 2022 to 2023.



\### 5.4 Business Unit Performance



| Business Unit | Revenue | Expense | Net Performance |

|---|---:|---:|---:|

| Enterprise | ₹281.40M | -₹57.02M | ₹224.37M |

| Online | ₹297.53M | -₹55.30M | ₹242.23M |

| Retail | ₹285.68M | -₹55.42M | ₹230.26M |



Online recorded the highest observed net performance.



However, statistical testing did not establish a statistically significant difference between business units.



\### 5.5 Regional Performance



| Region | Revenue | Expense | Net Performance |

|---|---:|---:|---:|

| East | ₹222.19M | -₹42.97M | ₹179.22M |

| North | ₹213.84M | -₹42.42M | ₹171.42M |

| South | ₹214.39M | -₹42.97M | ₹171.41M |

| West | ₹214.20M | -₹39.38M | ₹174.82M |



Regional performance was relatively close across the four regions.



Statistical testing did not identify a statistically significant difference in financial performance across regions.



\### 5.6 Distribution and Outlier Analysis



Skewness results:



| Metric | Skewness |

|---|---:|

| Amount | 0.174603 |

| Absolute Amount | 0.544107 |

| Revenue Amount | 0.421621 |

| Expense Amount | -1.152281 |

| Net Performance | 0.199441 |



IQR-based outlier results:



| Metric | IQR Outliers |

|---|---:|

| Amount | 0 |

| Absolute Amount | 2 |

| Revenue Amount | 0 |

| Expense Amount | 63 |

| Net Performance | 0 |



No potential IQR outliers were identified in the raw transaction amount measure.



\---



\## 6. Statistical Analysis



Statistical hypothesis testing was performed to determine whether observed differences were statistically supported.



\### 6.1 Business Unit ANOVA



\- F-statistic: \*\*2.256404\*\*

\- p-value: \*\*0.104778\*\*



At the conventional 5% significance level, the null hypothesis was not rejected.



Therefore, there was insufficient evidence to conclude that business-unit financial performance differed significantly.



\### 6.2 Regional ANOVA



\- F-statistic: \*\*0.582537\*\*

\- p-value: \*\*0.626415\*\*



The null hypothesis was not rejected.



There was insufficient evidence to conclude that regional financial performance differed significantly.



\### 6.3 Welch t-test — 2022 vs 2023



\- t-statistic: \*\*-6.420743\*\*

\- p-value: approximately \*\*1.42 × 10⁻¹⁰\*\*

\- Cohen's d: \*\*0.126052\*\*



The year-to-year difference was statistically significant.



However, Cohen's d indicates a \*\*negligible practical effect\*\*.



This demonstrates that statistical significance should be interpreted alongside effect size and business relevance.



\### 6.4 Pearson Correlation



The correlation between absolute transaction amount and expense amount was:



\- \*\*r = 0.491287\*\*

\- p-value: approximately \*\*0\*\*



This indicates a statistically significant moderate positive association.



\### 6.5 Kruskal-Wallis Test



A Kruskal-Wallis test was performed across financial-flow groups.



\- H-statistic: \*\*8188.876922\*\*

\- p-value: approximately \*\*0\*\*



The result indicates statistically significant differences between financial-flow groups.



Pairwise Mann-Whitney testing also identified statistically significant differences between the tested financial-flow groups.



\### 6.6 Statistical Interpretation



The statistical analysis provides an important distinction between:



\- Descriptive differences

\- Statistical significance

\- Practical significance



Observed rankings between business units or regions should not automatically be interpreted as statistically significant differences.



\---



\## 7. Budget Variance \& Cost Analysis



\### 7.1 Budget Performance



Actual financial performance was compared with available budget values.



\#### Revenue



\- Actual Revenue: approximately \*\*₹864.61M\*\*

\- Budget Revenue: approximately \*\*₹135.82M\*\*

\- Revenue Budget Variance: approximately \*\*+₹728.79M\*\*

\- Revenue Budget Variance %: approximately \*\*+536.61%\*\*



\#### Expense



\- Actual Expense: approximately \*\*-₹167.74M\*\*

\- Budget Expense: approximately \*\*₹104.26M\*\*

\- Expense Budget Variance: approximately \*\*-₹63.48M\*\*

\- Expense Budget Variance %: approximately \*\*-60.88%\*\*



Expense variance was calculated using the project's financial sign convention because transaction expenses are negative while budget expense values are positive.



\### 7.2 Budget Interpretation



The large actual-versus-budget differences indicate that the available budget baseline and planning assumptions require management review.



The analysis does \*\*not\*\* establish a specific causal reason for the variance.



Potential management focus areas include:



\- Budget-setting methodology

\- Planning assumptions

\- Monthly budget monitoring

\- Business-unit budget alignment

\- Variance review processes



\### 7.3 Workforce Cost Analysis



Workforce analysis evaluated:



\- Headcount

\- Employee cost

\- Cost per employee

\- Business-unit workforce distribution

\- Regional workforce distribution

\- Employee status



Observed cost per employee:



| Business Unit | Cost per Employee |

|---|---:|

| Enterprise | ₹1.15M |

| Retail | ₹1.11M |

| Online | ₹1.09M |



Enterprise had the highest observed cost per employee.



This should be investigated through:



\- Role mix

\- Compensation structure

\- Workforce allocation

\- Productivity indicators

\- Business-unit resource requirements



The result is an investigation opportunity and should not be interpreted as direct proof of inefficiency.



\---



\## 8. Power BI Dashboard



An interactive Power BI dashboard was developed as the decision-support layer of the project.



The dashboard contains \*\*four pages\*\*.



\### 8.1 Page 1 — Executive Financial Overview



Key elements include:



\- Total Transactions

\- Average Transaction Amount

\- Total Revenue

\- Total Expense

\- Total Net Performance

\- Yearly performance

\- Revenue versus expense

\- Business-unit performance

\- Monthly trends

\- Interactive filters



\### 8.2 Page 2 — Financial Performance Analysis



Key elements include:



\- Monthly Revenue versus Expense

\- Revenue by Category

\- Expense by Category

\- Business-unit analysis

\- Regional analysis

\- Actual versus Budget Revenue

\- Actual versus Budget Expense

\- Budget variance analysis



\### 8.3 Page 3 — Customer \& Vendor Analysis



Key elements include:



\- Revenue by Customer Segment

\- Net Performance by Customer Segment

\- Revenue by Vendor Category

\- Expense by Vendor Category

\- Top 10 Vendors by Expense

\- Customer Segment filter

\- Vendor Category filter



\### 8.4 Page 4 — Workforce \& Cost Analysis



Key elements include:



\- Total Headcount

\- Total Employee Cost

\- Cost per Employee

\- Headcount by Business Unit

\- Employee Cost by Business Unit

\- Cost per Employee by Business Unit

\- Headcount by Region

\- Employee Cost by Region

\- Cost per Employee by Region

\- Employee Status

\- Headcount by Region \& Business Unit

\- Employee Cost by Region \& Business Unit



\### 8.5 Dashboard Purpose



The Power BI dashboard provides an interactive view of:



\- Financial performance

\- Revenue and expense trends

\- Budget variance

\- Business-unit performance

\- Regional performance

\- Customer segmentation

\- Vendor expenditure

\- Workforce cost

\- Cost efficiency



The dashboard is designed to support management-oriented financial monitoring and investigation.



\---



\## 9. Strategic Insights



\### Insight 1 — Strong 2023 Revenue Growth



Revenue increased from approximately \*\*₹377.43M in 2022\*\* to \*\*₹487.18M in 2023\*\*, representing approximately \*\*29% growth\*\*.



Net Performance also increased from approximately \*\*₹293.56M\*\* to \*\*₹403.30M\*\*.



This indicates stronger observed financial performance in 2023.



\### Insight 2 — Statistical Significance vs Practical Significance



The Welch t-test showed a statistically significant difference between 2022 and 2023.



However, Cohen's d was only \*\*0.126052\*\*, indicating a negligible practical effect.



Therefore, statistical significance should not be interpreted as evidence of a large business impact at the transaction level.



\### Insight 3 — Business Unit Performance Is Relatively Balanced



Online recorded the highest observed net performance at approximately \*\*₹242.23M\*\*.



However, the business-unit ANOVA was not statistically significant with:



\*\*p = 0.104778\*\*



Therefore, descriptive rankings should not alone drive major resource-allocation decisions.



\### Insight 4 — Budget Variance Requires Management Attention



Actual revenue and expense differed substantially from the available budget baseline.



The magnitude of these variances indicates that budget assumptions, planning methodology, and variance-monitoring practices should be reviewed.



\### Insight 5 — Workforce Cost Structure Varies



Enterprise recorded the highest observed cost per employee at approximately \*\*₹1.15M\*\*.



This provides an opportunity to investigate workforce composition, compensation structure, resource allocation, and productivity.



\---



\## 10. Recommendations



\### Recommendation 1 — Review Budget Methodology



Management should review the assumptions and methodology used to establish revenue and expense budgets.



Actual-versus-budget performance should be monitored regularly by:



\- Month

\- Business Unit

\- Region

\- Category



\### Recommendation 2 — Investigate Workforce Cost Efficiency



Enterprise's higher observed cost per employee should be investigated alongside:



\- Employee role mix

\- Compensation structure

\- Workforce allocation

\- Productivity

\- Business-unit requirements



\### Recommendation 3 — Keep Business-Unit Resource Allocation Evidence-Based



Online has the highest observed net performance, but the ANOVA result does not establish a statistically significant business-unit difference.



Resource allocation should therefore be based on deeper investigation of performance drivers rather than descriptive rankings alone.



\### Recommendation 4 — Institutionalize Monthly Variance Reviews



Management should establish a recurring financial review process:



\*\*Actual → Budget → Variance → Root Cause → Corrective Action → Monitor\*\*



This can support earlier identification of financial issues and improve accountability.



\### Recommendation 5 — Investigate Drivers of 2023 Growth



The increase in 2023 performance should be investigated across:



\- Customer segments

\- Product/service categories

\- Business units

\- Vendors

\- Regions

\- Workforce factors



This can help identify the drivers supporting sustainable growth.



\---



\## 11. Management Action Plan



| Priority | Action | Expected Business Impact |

|---|---|---|

| HIGH | Review revenue and expense budget assumptions | Better planning and financial control |

| HIGH | Establish monthly variance reviews | Earlier identification of financial issues |

| MEDIUM | Analyze workforce cost differences | Improved resource allocation |

| MEDIUM | Investigate 2023 revenue-growth drivers | Support sustainable growth |

| MEDIUM | Monitor business-unit performance continuously | Evidence-based resource decisions |



\### Recommended Management Cycle



\*\*Actual → Budget → Variance → Root Cause → Corrective Action → Monitor\*\*



\### Immediate Priorities



\#### Priority 1 — Budget Review



Review revenue and expense budget assumptions and understand why actual results differ materially from the available budget baseline.



\#### Priority 2 — Variance Monitoring



Establish a monthly process for identifying, investigating, and documenting material financial variances.



\#### Priority 3 — Workforce Cost Review



Investigate differences in cost per employee, particularly within Enterprise, using workforce composition and role-level information.



\#### Priority 4 — Growth Driver Analysis



Investigate the customer, category, vendor, region, and business-unit factors associated with the observed 2023 growth.



\#### Priority 5 — Continuous Monitoring



Use the Power BI dashboard as a recurring management monitoring tool for financial and workforce performance.



\---



\## 12. Conclusion



The Financial Performance Analysis project provides an end-to-end analytical workflow covering business understanding, data validation, SQL database design and analysis, Python data preparation and EDA, statistical testing, budget variance analysis, Power BI dashboarding, and strategic recommendations.



The project successfully validated \*\*10,400 financial transactions\*\* and established a reliable analytical foundation with zero duplicate transaction IDs, zero duplicate rows, and passed financial calculation validation.



The financial analysis identified:



\- Approximately \*\*₹864.61M\*\* in total revenue

\- Approximately \*\*₹167.74M\*\* in total expense magnitude

\- Approximately \*\*₹696.87M\*\* in net performance

\- Approximately \*\*29% year-over-year revenue growth\*\*

\- Significant statistical difference between 2022 and 2023

\- Negligible practical effect size for the year comparison

\- No statistically significant business-unit differences

\- No statistically significant regional differences

\- Significant financial-flow distribution differences

\- Substantial actual-versus-budget variances

\- Observable differences in workforce cost per employee



The project also demonstrates the importance of combining descriptive analytics with statistical evidence. Descriptive rankings provide useful business context, but statistical testing helps determine whether observed differences are sufficiently supported by the data.



The final four-page Power BI dashboard provides an interactive decision-support layer covering executive financial performance, financial and budget analysis, customer and vendor analysis, and workforce and cost analysis.



The strategic recommendations focus on budget methodology, variance monitoring, workforce cost investigation, evidence-based resource allocation, and identifying the drivers of 2023 growth.



Overall, the project transforms validated financial and operational data into a structured analytical framework that can support recurring financial performance monitoring and evidence-based management decisions.



\*\*Validated Data → Analysis → Statistical Evidence → Insight → Action\*\*

