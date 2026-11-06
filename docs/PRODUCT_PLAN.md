# Zydrakon AI - Company Data Assistant

Product plan | 6 November 2026 | Internal two-user pilot

## Product decision

Cloud AI model API + React frontend + Python FastAPI + SQLite. No local AI model.

Two users on the same computer can upload CSV, Excel and clear table images, ask data questions, and inspect calculations together with source evidence. Initial testing uses dummy data. Sales, finance, HR and operations are covered through common data-analysis operations, not unlimited departmental expertise.

Answers appear inside the application. Excel export, company-policy interpretation, policy-rule application, cross-file joins and automated business decisions are later scope. The cloud model remains API-based; there is no local-model migration commitment.

## Product-owner reality check

The valuable product is trustworthy analysis, not merely an upload box and chat interface. A wrong column, duplicate rows, subtotal double counting, mixed currencies or stale formula values can produce a mathematically correct but commercially wrong answer. Do not promise "any file, any question" or universal accuracy. Payroll, tax and policy expertise are not implied by accepting HR or finance files.

The 9/10 target is an acceptance objective: at least 90/100 on the defined scorecard plus every mandatory safety/correctness gate. It is not a claim about the present implementation. External AI processing and zero information leaving the machine are different requirements. Redaction cannot guarantee that every question or value is non-confidential.

## User experience

The desktop-first workspace has three visible areas:

- Left: private uploaded files, selected sheet and previous conversations.
- Centre: source-table preview, types, warnings and editable image-extraction corrections.
- Right: questions, answers, calculation method and supporting source rows.

Settings show account, dataset classification, configured cloud model and usage. Two separate application accounts have private files and chats. The interface must have clear empty, loading, processing, clarification and error states. A local calculation builder remains useful without an API key and for Restricted datasets.

## Architecture

| Layer | Decision | Responsibility |
|---|---|---|
| Frontend | React + TypeScript + Vite | Local desktop-friendly web interface |
| Backend | Python FastAPI + Pydantic | Auth, permissions, validation and orchestration |
| Database | SQLite + SQLAlchemy | Users, metadata, versions, results and jobs |
| Calculation | pandas + Python Decimal | Deterministic full-table computation |
| Excel | openpyxl | Values, sheets and formula detection |
| Images | Local Tesseract + OpenCV | Simple-table OCR plus mandatory review |
| Cloud AI | OpenAI Responses API, configurable model | Question to validated analysis instructions |
| Initial model | gpt-6-luna | Default configuration; verify account access |
| Jobs | One separate local Python worker | Bounded parsing, OCR and analysis |
| Files | Private non-synced local directory | Immutable originals and normalized versions |

FastAPI serves the built frontend at 127.0.0.1. SQLite uses WAL, short transactions and a busy timeout on local disk. No MongoDB migration, Redis, vector database, microservice fleet or model hosting is required for this pilot. Revisit database deployment only if workload or multi-server needs change.

## End-to-end data flow

Upload -> validate -> parse -> preview/confirm -> ask -> cloud analysis plan -> backend validation -> local calculation -> answer with evidence.

The cloud model interprets a permitted question. It does not run arbitrary Python or SQL. A Pydantic-validated plan selects only approved operations; backend validation checks table versions, column names, permissions, filters and bounds. Calculations use the complete selected table. Numeric answers are populated from the actual backend result, not invented prose.

Restricted datasets never enter the cloud stage. Their deterministic local calculation builder does not need a model.

## Supported operations and capacity

- Row lookup, filtering, sorting and top/bottom results.
- Sum, count, average, minimum and maximum.
- Group totals, including explicit date grouping by day/month/year.
- Percentage, percentage change and same-table comparisons.
- Missing-value and duplicate-candidate identification.

One question uses one selected table. Workbooks may contain several sheets; the user selects the table. Cross-file joins, arbitrary spreadsheet formula evaluation, macros and external workbook links are not supported.

Initial safety defaults are 10 MB for CSV/XLSX, 50,000 rows by 50 columns per selected table, and 5 MB for PNG/JPEG. These are input limits, not measured performance claims. Benchmark the actual PC and record processing latency and peak memory before pilot acceptance.

## Correctness rules

- Every answer identifies dataset version, sheet/table, applied filters, included and excluded row counts, calculation method and supporting source rows.
- Preview sampling must never determine full-table totals. Long evidence lists may be capped in the UI while full counts remain explicit.
- Missing values are not silently converted to zero. Duplicate and subtotal rows are not silently removed.
- Ambiguous columns, dates, currencies and metrics require clarification or an actionable error.
- Currency computations use decimal arithmetic and explicit display rounding.
- Formula-dependent inputs are flagged. openpyxl does not recalculate formulas; cached results are not proof of freshness. Affected calculations require verified values-only input.
- Images mean clear printed/screenshot tables. Show editable extracted cells and require explicit review before analysis. Handwriting, invoices and complex merged layouts are outside the committed v1 scope.

## Privacy and security boundary

Every new upload starts Restricted. A tester may explicitly confirm a known synthetic dataset for cloud demo use. Restricted dataset contents, questions, schema and results must not reach the cloud connector.

Synthetic classification is a human/process control. The application cannot reliably prove that arbitrary uploaded data or free-text questions contain no confidential information. Cloud demo users must use synthetic files and synthetic questions. A file marked synthetic in error can disclose information.

Cloud payloads are limited to the necessary permitted question and schema, not the original workbook/image. Real-data conversational rollout waits until the company defines which information may be processed externally. "Files stay local" must never be presented as "nothing leaves the machine."

API keys remain server-side. Enforce per-user access checks, file type/size validation, local non-synced storage, metadata-only operational logs and bounded workers. Treat cells and file text as data, never permission-changing instructions. User accounts inside the app do not provide OS-level confidentiality against someone controlling the same Windows account.

## Public interfaces

| Interface | Responsibility |
|---|---|
| POST /uploads | Validate a file and create a processing job |
| GET /datasets/{id}/preview | Return tables, types and warnings |
| POST /datasets/{id}/confirm | Save the reviewed version |
| POST /questions | Submit permitted dataset version and question |
| GET /jobs/{id} | Return progress, result, clarification or error |
| DELETE /datasets/{id} | Delete original and derived artifacts |

The delivered app may group these under an /api prefix. Authentication, classification, local analyses, conversations, sample data and retry endpoints support the same workflow. Interrupted jobs are visibly retryable. Model failure, timeout or invalid output must not produce a fabricated answer.

## Acceptance scorecard

| Area | Weight | Required evidence |
|---|---:|---|
| Calculation correctness | 30 | At least 60 verified calculation cases; numerical results match |
| Question understanding | 20 | At least 95% correct interpretations on a held-out supported set |
| Parsing and OCR | 15 | Messy inputs and at least 10 clear-table images; review gate enforced |
| Privacy and access | 25 | Zero Restricted-data cloud calls; cross-user access tests pass |
| Usability and recovery | 10 | Both users finish workflows; retry, restart, delete and restore verified |

Target: at least 90/100 and all mandatory gates. A wrong numerical result, unauthorized access, Restricted-data transmission or unconfirmed OCR calculation fails the pilot regardless of total score. Backend arithmetic tests, cloud interpretation evaluations and human UAT are distinct evidence; one cannot substitute for another.

Cover blanks, negatives, mixed currencies, ambiguous dates, duplicates, subtotal rows, formulas, division by zero, malicious cell instructions, unsupported questions, malformed model responses, provider timeout, worker restart and cross-user requests. Record any unexecuted tests explicitly.

## Delivery and commercial assumptions

Planning estimate: 4-6 weeks for one experienced full-time developer, with representative samples and prompt company feedback. This is a planning estimate, not a claim that a complete production rollout is finished.

| Stage | Deliverable |
|---|---|
| Week 1 | Sample pack, approved expected answers, UI flow, privacy boundary and PC benchmark |
| Week 2 | Login, upload, preview, versions and calculation engine |
| Week 3 | Cloud interpretation, evidence and chat |
| Week 4 | OCR review, privacy/access checks and two-user testing |
| Weeks 5-6 | Parsing/OCR fixes, recovery, packaging, documentation and acceptance |

Measure API request volume, failures, latency, tokens and cost per successful answer. Separate development cost, API consumption and support. Do not sell unlimited usage before measuring workload.

Later phases can introduce approved company policies, effective dates, clause citations and separately approved deterministic rules. Policy explanation and eligibility/approval decisions must remain separately governed capabilities.

## Deliverables and references

Working local application, synthetic sample data, test suite, operating instructions, this plan and its PDF. Intended PDF handoff: Downloads/Zydrakon_AI_Product_Plan.pdf.

- OpenAI model: https://developers.openai.com/api/docs/models/gpt-6-luna
- Function calling: https://developers.openai.com/api/docs/guides/function-calling
- SQLite usage: https://www.sqlite.org/whentouse.html
- SQLite WAL: https://www.sqlite.org/wal.html
- openpyxl formula limits: https://openpyxl.readthedocs.io/en/stable/simple_formulae.html
- Tesseract outputs: https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html
- OWASP prompt injection guidance: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html
