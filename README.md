# Zydrakon AI

A local, two-user company data workspace with cloud-AI question interpretation and deterministic Python calculations. Upload CSV, XLSX or clear table images, inspect the data, and see answers with source evidence.

**The model is a cloud API. No local AI model is installed or required.** Company-policy features and Excel export are intentionally deferred.

## Run on Windows

From PowerShell in this directory:

```powershell
.\setup.ps1
.\start.ps1
```

Open http://127.0.0.1:8000. The first-run screen creates the first account. A signed-in user can create the second account; the pilot allows two accounts. Use separate browser profiles to test both users at once.

The setup script installs the Python and frontend dependencies and builds the frontend. The start script runs the local FastAPI service and processing worker. If PowerShell execution policy blocks a script, run it explicitly with `powershell -ExecutionPolicy Bypass -File .\setup.ps1` (and then `start.ps1`).

## Cloud API configuration

Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. The configurable default model is `OPENAI_MODEL=gpt-6-luna`; your API account must have access. Restart the app after changing configuration. Keep `.env` private and out of version control.

Without an API key, file inspection and the **local calculation builder** still work. Natural-language cloud questions show an actionable configuration error, not a simulated AI response. The frontend never receives the key.

## First test

1. Create an account and load the built-in sample or upload `sample-data/synthetic_company_metrics.csv`.
2. Select the table and inspect the headers, inferred types and warnings.
3. Confirm the table. For images, correct all required extracted cells before confirmation.
4. Use the local calculation builder to sum `Amount`, group it by `Department`, or count records.
5. If using cloud questions, explicitly classify the known synthetic dataset as synthetic first. Try “What is the total Amount by Department?”
6. Inspect the result, applied filters, row counts and source rows.

Expected results for the sample are in `sample-data/expected_results.json`. All names, IDs and amounts are fictional. Use the exact file for those reference answers; the built-in sample may have different records.

## Privacy boundary

- Every upload starts **Restricted**. Restricted datasets cannot call the cloud model.
- Explicitly marking a dataset synthetic enables cloud interpretation for that dataset. This is a human attestation, not an automatic confidentiality detector.
- Cloud users must use synthetic questions too. A real name or confidential number typed into a cloud question can leave the machine even if the uploaded file is synthetic.
- The cloud request is limited to permitted question/schema context; original images and workbooks are not uploaded to the model.
- Original files, normalized data, conversations and results stay in the local data directory. Operational logs avoid raw prompts/data. Same-Windows-account users can still inspect local files outside the app: application login is not OS-level isolation.
- Real-data cloud processing requires a separately agreed company policy. The app cannot truthfully guarantee zero disclosure for arbitrary content that a tester wrongly marks synthetic.

The default data directory is `%LOCALAPPDATA%\ZydrakonAI`. Set `ZYDRAKON_DATA_DIR` to another **local, non-synced** directory if necessary. Do not use a network share or OneDrive folder for the SQLite database. Tests must use a disposable directory so they do not affect user data.

## OCR dependency

Install the Tesseract OCR executable and make it available on `PATH` (or configure `TESSERACT_CMD` if supported by the installed app). Python OCR/image libraries alone do not provide the executable. OCR runs locally. If Tesseract is absent, image imports fail with a clear dependency message; CSV/XLSX analysis remains available.

Only clear printed table images/screenshots are in scope. Every extracted table requires review. Handwriting, receipts, invoices and complex merged layouts have no accuracy commitment.

## Supported analysis

Filtering, row selection, sorting, sum/count/average/min/max, grouped totals, missing values, duplicate candidates, percentages, percentage changes and same-table comparisons. One selected table per analysis. The engine computes over the full selected table, not just the preview.

Missing values are not silently zeroed; duplicate rows are not silently removed. Formula-dependent Excel inputs are flagged because openpyxl does not recalculate formulas. Supply verified values-only data for affected operations. Input limits are 10 MB for CSV/XLSX, 50,000 rows by 50 columns per table, and 5 MB for PNG/JPEG.

## Tests and acceptance

Run backend tests from the repository root using the configured Python environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Build the frontend:

```powershell
Set-Location frontend
npm.cmd run build
```

See `docs/ACCEPTANCE.md` for the distinction between automated checks and remaining cloud/OCR/human acceptance. Passing tests is not a universal “95% accurate” or “9/10 production-ready” claim.

## Backup, restore and deletion

Stop the app and worker before a filesystem backup. Copy the complete data directory, including the SQLite database and its sidecar files if present, originals and normalized data. Restore the complete matching directory while the app is stopped, then restart and verify both users' sample workflows. Never copy only a live SQLite main file and assume the backup is consistent.

Dataset deletion removes its source and derived artifacts from active application storage; existing external backups may still contain copies. Maintain and delete backups according to the company's retention requirements. Interrupted jobs are visible and retryable rather than silently reported as successful.

## Documentation

- `docs/PRODUCT_PLAN.md` - accepted product scope and design.
- `docs/ACCEPTANCE.md` - release gates and verification record.
- `output/pdf/Zydrakon_AI_Product_Plan.pdf` - shareable product plan.
- `scripts/create_plan_pdf.py` - reproducible PDF source.

No source data is modified in place. Excel export, company policies, autonomous approvals and cross-file joins are outside this pilot.
