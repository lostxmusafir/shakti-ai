"""Build the shareable eight-page product plan; no runtime app data is read."""
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    KeepTogether, HRFlowable,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "Zydrakon_AI_Product_Plan.pdf"
NAVY = colors.HexColor("#15243D")
INDIGO = colors.HexColor("#4856C8")
TEAL = colors.HexColor("#137F88")
INK = colors.HexColor("#25334B")
MUTED = colors.HexColor("#59677D")
PALE = colors.HexColor("#F2F5FB")
LINE = colors.HexColor("#DDE4EF")
AMBER = colors.HexColor("#FFF5E2")

FONT = "Helvetica"
BOLD = "Helvetica-Bold"
font_dir = Path("C:/Windows/Fonts")
if (font_dir / "segoeui.ttf").exists():
    pdfmetrics.registerFont(TTFont("Segoe", str(font_dir / "segoeui.ttf")))
    pdfmetrics.registerFont(TTFont("SegoeBold", str(font_dir / "segoeuib.ttf")))
    pdfmetrics.registerFontFamily("Segoe", normal="Segoe", bold="SegoeBold", italic="Segoe", boldItalic="SegoeBold")
    FONT, BOLD = "Segoe", "SegoeBold"

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="KickerZ", fontName=BOLD, fontSize=9, leading=12, textColor=TEAL, spaceAfter=9))
styles.add(ParagraphStyle(name="TitleZ", fontName=BOLD, fontSize=31, leading=36, textColor=NAVY, spaceAfter=17))
styles.add(ParagraphStyle(name="HeadingZ", fontName=BOLD, fontSize=22, leading=27, textColor=NAVY, spaceAfter=14))
styles.add(ParagraphStyle(name="SubZ", fontName=BOLD, fontSize=12, leading=17, textColor=INDIGO, spaceBefore=12, spaceAfter=6))
styles.add(ParagraphStyle(name="BodyZ", fontName=FONT, fontSize=10.6, leading=15.3, textColor=INK, spaceAfter=8))
styles.add(ParagraphStyle(name="SmallZ", fontName=FONT, fontSize=9, leading=12.6, textColor=MUTED, spaceAfter=6))
styles.add(ParagraphStyle(name="CellZ", fontName=FONT, fontSize=9.6, leading=13.2, textColor=INK))
styles.add(ParagraphStyle(name="CellHeadZ", fontName=BOLD, fontSize=9.6, leading=13.2, textColor=colors.white))
styles.add(ParagraphStyle(name="CallZ", fontName=BOLD, fontSize=11, leading=16, textColor=NAVY))
styles.add(ParagraphStyle(name="BulletZ", fontName=FONT, fontSize=10.4, leading=15, leftIndent=12, firstLineIndent=-12, textColor=INK, spaceAfter=7))

story = []

def p(text, style="BodyZ"):
    return Paragraph(text, styles[style])

def add(text, style="BodyZ"):
    story.append(p(text, style))

def bullet(text):
    add("<font color='#4856C8'>-</font> " + text, "BulletZ")

def title(section, heading, intro=None):
    add(section.upper(), "KickerZ")
    add(heading, "HeadingZ")
    if intro:
        add(intro)

def callout(text, background=PALE):
    t = Table([[p(text, "CallZ")]], colWidths=[174*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), background),
        ("BOX", (0,0), (-1,-1), .5, LINE),
        ("LEFTPADDING", (0,0), (-1,-1), 12),
        ("RIGHTPADDING", (0,0), (-1,-1), 12),
        ("TOPPADDING", (0,0), (-1,-1), 11),
        ("BOTTOMPADDING", (0,0), (-1,-1), 11),
    ]))
    story.extend([t, Spacer(1, 10)])

def table(headers, rows, widths):
    data = [[p(escape(str(x)), "CellHeadZ") for x in headers]]
    data.extend([[p(str(x), "CellZ") for x in row] for row in rows])
    t = Table(data, colWidths=[w*mm for w in widths], repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NAVY),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, PALE]),
        ("LINEBELOW", (0,0), (-1,0), .5, NAVY),
        ("LINEBELOW", (0,1), (-1,-1), .35, LINE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 9),
        ("RIGHTPADDING", (0,0), (-1,-1), 9),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.extend([t, Spacer(1, 9)])

def next_page():
    story.append(PageBreak())

def page_chrome(canvas, doc):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, height-6*mm, width, 6*mm, fill=1, stroke=0)
    canvas.setFont(BOLD, 9)
    canvas.setFillColor(NAVY)
    canvas.drawString(18*mm, height-17*mm, "ZYDRAKON AI")
    canvas.setFont(FONT, 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(width-18*mm, height-17*mm, "PRODUCT PLAN  /  06 NOV 2026")
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(.5)
    canvas.line(18*mm, 18*mm, width-18*mm, 18*mm)
    canvas.setFont(FONT, 8)
    canvas.drawString(18*mm, 12*mm, "INTERNAL PILOT  |  CLOUD MODEL + LOCAL CALCULATIONS")
    canvas.setFont(BOLD, 9)
    canvas.drawRightString(width-18*mm, 12*mm, f"{doc.page:02d} / 08")
    canvas.restoreState()

# 1: Executive decision
add("APPROVED PRODUCT DIRECTION", "KickerZ")
add("Company Data<br/>Assistant", "TitleZ")
add("A practical pilot for answering questions about company tables, with calculations that users can inspect.", "BodyZ")
story.append(Spacer(1, 12))
table(["02 USERS", "01 COMPUTER", "CLOUD MODEL"], [["Separate app accounts", "Private local workspace", "API-based intelligence"]], [58,58,58])
callout("Cloud AI API + React + Python FastAPI + SQLite.<br/>No local AI model. No model-hosting migration.")
add("What the first release delivers", "SubZ")
bullet("Upload CSV, XLSX or clear table images. Inspect the source and ask supported data questions.")
bullet("Compute with trusted Python functions across the full selected table. Show method, filters, row counts and source evidence.")
bullet("Test with synthetic data across sales, finance, HR and operations. Answers stay in the app.")
add("What is deliberately later", "SubZ")
add("Company policies, rule-based eligibility, Excel export, cross-file joins and automated business decisions. Departmental coverage means common analysis, not unlimited payroll, tax or policy expertise.")
callout("9/10 is a measured acceptance target, not a launch claim.", AMBER)
add("Product-owner assessment", "SubZ")
add("The hard part is trustworthy data interpretation. A wrong column, duplicate rows or stale formula values can produce an answer that looks precise and is still wrong. Do not sell an \"any file, any question\" promise.")

# 2: UX and supported work
next_page()
title("01 / Experience", "Keep the evidence visible", "A desktop-first workspace puts the question and the underlying table side by side.")
table(["LEFT", "CENTRE", "RIGHT"], [["Private files<br/>Selected sheet<br/>Conversation history", "Data preview<br/>Column types<br/>Warnings / OCR review", "Question and answer<br/>Calculation method<br/>Supporting rows"]], [47,74,53])
add("The normal journey", "SubZ")
add("Upload a file, select its table, inspect the preview, resolve warnings, confirm it, and ask a question. A successful answer remains traceable to the selected dataset version.")
add("Supported v1 analysis", "SubZ")
bullet("Lookup and filter rows; sort and show top or bottom results.")
bullet("Sum, count, average, minimum and maximum.")
bullet("Group totals by a column, or dates by day, month or year.")
bullet("Percentage, percentage change and same-table comparisons.")
bullet("Identify missing values and duplicate candidates without silently deleting them.")
callout("One selected table per question. A workbook may contain several sheets; the user chooses the table.")
add("Useful even when the API is unavailable", "SubZ")
add("The local calculation builder offers the same approved deterministic operations without a model. It works for Restricted data and when the cloud key is missing. Cloud questions show a real configuration or provider error, never a simulated success.")
add("Interface states", "SubZ")
add("Design explicit empty, uploading, processing, review-required, ready, clarification and failed states. Settings expose cloud readiness and usage. Two accounts keep application files and chats private from one another.")

# 3: architecture
next_page()
title("02 / Architecture", "A small, coherent stack", "The cloud model interprets. The backend validates. Python calculates. The interface shows the evidence.")
table(["Layer", "Decision and responsibility"], [
    ("Frontend", "React + TypeScript + Vite; production assets served locally by FastAPI."),
    ("API", "FastAPI + Pydantic for auth, access checks, request validation and orchestration."),
    ("Database", "SQLite + SQLAlchemy; accounts, versions, conversations, results and job state."),
    ("Calculation", "pandas + Python Decimal for controlled, full-table computations."),
    ("Reading", "openpyxl for Excel; Tesseract + OpenCV locally for simple table images."),
    ("Cloud", "OpenAI Responses API; configurable model, default gpt-6-luna. Account access verified at setup."),
    ("Processing", "One separate local Python worker with bounded tasks and visible failures."),
    ("Files", "Immutable originals and normalized versions in a private, non-synced local directory."),
], [35,139])
add("Deployment and storage", "SubZ")
add("Serve the app at 127.0.0.1. Use SQLite WAL, short transactions and a busy timeout on local disk. Separate browser profiles let both users test independently. A future multi-server deployment may require a different database; no Mongo-to-SQLite migration is needed now.")
callout("No Redis, vector database, microservice fleet or local model is needed for this bounded pilot.")
add("Data flow", "SubZ")
add("Upload > validate > preview / confirm > question > validated analysis plan > local calculation > answer with evidence. Restricted datasets skip the cloud step and use local controls.")

# 4: data correctness
next_page()
title("03 / Data quality", "Correct numbers need correct inputs")
table(["Input", "Initial safety default"], [
    ("CSV / XLSX", "Up to 10 MB; 50,000 rows x 50 columns per selected table."),
    ("PNG / JPEG", "Up to 5 MB; clear printed tables or screenshots."),
    ("Performance", "Benchmark actual-PC latency and memory. Limits are not performance claims."),
], [40,134])
add("Calculation contract", "SubZ")
bullet("Compute over the complete authorized selection. Never use the preview sample as the basis for totals.")
bullet("Show dataset version, table, filters, included/excluded row counts, method and source rows. Cap long evidence displays explicitly.")
bullet("Do not silently treat missing values as zero or remove duplicates and subtotal rows.")
bullet("Clarify ambiguous columns, dates, currencies or metrics. Decimal arithmetic and explicit rounding are required for amounts.")
add("Excel boundary", "SubZ")
add("openpyxl does not evaluate formulas. Formula-derived fields are flagged; cached values do not prove freshness. Affected calculations require verified values-only input. Arbitrary formula recalculation, macros and external workbook links are outside this release.")
add("Image boundary", "SubZ")
add("OCR runs locally and returns an editable table. The user reviews and confirms extracted cells before any analysis. Unsupported handwriting, invoices and complex merged layouts get an explicit limitation rather than an accuracy promise.")
callout("A validated JSON shape does not prove that the model chose the correct business metric. Validate semantics and test expected outcomes.", AMBER)

# 5: privacy
next_page()
title("04 / Privacy", "A clear cloud boundary", "Files stored locally and information never leaving the machine are not the same claim.")
table(["Classification", "Behavior"], [
    ("Restricted - default", "Questions, schema, contents and results cannot enter the cloud connector. Local deterministic analysis remains available."),
    ("Confirmed synthetic", "A tester explicitly attests the data is synthetic. Permitted question/schema context may be sent to the cloud model."),
], [50,124])
callout("Synthetic classification is a human control, not a reliable automatic confidentiality detector.", AMBER)
add("What can still leak", "SubZ")
add("A real name, salary, customer detail or confidential number typed into a cloud question is information sent externally. A synthetic dataset label does not make arbitrary free text safe. Testers must use synthetic questions as well as synthetic files.")
add("Required safeguards", "SubZ")
bullet("Keep API keys on the backend; never return them to the browser.")
bullet("Apply ownership checks before preview, analysis, retrieval, retry and deletion.")
bullet("Limit cloud payloads to necessary permitted question/schema context. Do not upload original workbooks or images to the model.")
bullet("Validate file type/size, bound worker execution and treat cells as data, not permission-changing instructions.")
bullet("Keep operational logs to necessary metadata. Store files and SQLite outside synced folders.")
add("Limits that must stay explicit", "SubZ")
add("Redaction reduces exposure but cannot guarantee zero leakage. Two app accounts do not prevent someone controlling the same Windows account from reading local files. Real-data conversational rollout waits until the company defines permitted cloud processing.")

# 6: public interfaces and resilience
next_page()
title("05 / Contracts", "Predictable interfaces and failures")
table(["Interface", "Responsibility"], [
    ("POST /uploads", "Validate upload and return a processing job."),
    ("GET /datasets/{id}/preview", "Return tables, types, rows and warnings."),
    ("POST /datasets/{id}/confirm", "Save a reviewed dataset version."),
    ("POST /questions", "Accept permitted dataset version and question; return job ID."),
    ("GET /jobs/{id}", "Return progress, answer, clarification or error."),
    ("DELETE /datasets/{id}", "Remove original and derived artifacts."),
], [76,98])
add("The app may group routes under /api. Authentication, classification, local analysis, conversation history, sample data and retry routes support the same workflow.", "SmallZ")
add("The model-to-engine contract", "SubZ")
add("An analysis plan names an approved action, existing columns, typed filters, grouping and result bounds. The backend rejects unknown fields, invalid permissions, stale versions and unsupported operations. Never execute arbitrary model-generated Python or SQL.")
add("Job lifecycle", "SubZ")
add("Queued and running work must have durable status. A restart leaves interrupted tasks visibly retryable. A cloud timeout, invalid response or missing OCR executable produces an actionable error. No failure path invents a numerical answer.")
add("Operational controls", "SubZ")
bullet("Record request count, tokens, failures and latency without logging secrets or raw sensitive payloads.")
bullet("Back up the complete data directory while app and worker are stopped; restore a matching complete copy and verify it.")
bullet("Deletion removes active source and derived data. Backup retention is a separate company operating responsibility.")

# 7: evaluation
next_page()
title("06 / Acceptance", "Earn the 9/10 target", "Target at least 90/100 plus every mandatory gate. These are release criteria, not results claimed today.")
table(["Area", "Weight", "Required evidence"], [
    ("Calculation", "30", "60+ independently verified cases; supported numerical results match."),
    ("Understanding", "20", "At least 95% correct interpretation on held-out supported questions using the live configured model."),
    ("Parsing / OCR", "15", "Messy inputs and 10+ clear table images; review gate enforced."),
    ("Privacy / access", "25", "Zero Restricted-data cloud calls; cross-user access checks pass."),
    ("Usability / recovery", "10", "Both users complete tasks; timeout, retry, restart, deletion and restore verified."),
], [41,23,110])
callout("Mandatory fail: wrong numerical result, unauthorized access, Restricted-data transmission or calculation before OCR review.", AMBER)
add("Representative edge cases", "SubZ")
add("Blanks, negatives, mixed currencies, ambiguous dates, duplicates, subtotal rows, formulas, division by zero, malicious cell instructions, unsupported questions, stale dataset versions, worker interruption and provider timeouts.")
add("Keep evidence categories separate", "SubZ")
bullet("Unit and API tests establish deterministic behavior and enforced boundaries.")
bullet("Provider mocks do not establish real cloud-model understanding or accuracy.")
bullet("Mock OCR does not establish extraction quality on company-style images.")
bullet("Two-user UAT, actual-PC capacity and backup/restore need their own recorded runs.")
add("Freeze a held-out set before evaluating. Record environment, dataset hashes, model ID, outcomes and limitations. Never describe an unexecuted test as passed.", "SmallZ")

# 8: delivery and sources
next_page()
title("07 / Delivery", "A bounded pilot, then expansion")
add("Planning estimate: <b>4-6 weeks</b> for one experienced full-time developer, assuming representative samples and timely feedback. This is not a production-rollout guarantee.")
table(["Stage", "Deliverable"], [
    ("Week 1", "Synthetic pack, expected answers, UX, privacy boundary and PC benchmark."),
    ("Week 2", "Login, upload, preview, versions and calculation engine."),
    ("Week 3", "Cloud interpretation, answers and source evidence."),
    ("Week 4", "OCR review, privacy/access checks and two-user testing."),
    ("Weeks 5-6", "Fixes, recovery, packaging, documentation and acceptance."),
], [30,144])
add("Commercial discipline", "SubZ")
add("Measure API consumption, latency and cost per successful answer. Separate build cost, provider usage and support. Avoid unlimited-usage promises. Quote against supported workflows and file limits.")
add("Later roadmap", "SubZ")
add("Approved policies, effective dates, clause citations and owner-approved deterministic rules. Treat policy explanation separately from eligibility decisions and automated approvals. Excel export and cross-file analysis remain separate additions.")
add("Technical references", "SubZ")
refs = [
    ("OpenAI model capabilities", "https://developers.openai.com/api/docs/models/gpt-6-luna"),
    ("OpenAI function calling", "https://developers.openai.com/api/docs/guides/function-calling"),
    ("SQLite deployment fit", "https://www.sqlite.org/whentouse.html"),
    ("openpyxl formula limitation", "https://openpyxl.readthedocs.io/en/stable/simple_formulae.html"),
    ("Tesseract output formats", "https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html"),
    ("OWASP prompt injection prevention", "https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html"),
]
for label, url in refs:
    add(f'<link href="{escape(url)}" color="#4856C8">{escape(label)}</link>', "SmallZ")
add("Delivery includes the local application, sample data, test suite, operating guide and this shareable plan. Intended PDF handoff: Downloads/Zydrakon_AI_Product_Plan.pdf.", "SmallZ")

def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
        topMargin=27*mm, bottomMargin=24*mm, title="Zydrakon AI - Company Data Assistant Product Plan",
        author="Zydrakon AI", subject="Cloud API data assistant - two-user pilot plan",
    )
    doc.build(story, onFirstPage=page_chrome, onLaterPages=page_chrome)
    print(f"Generated plan PDF: {OUTPUT}")

    # Copy to user Downloads folder
    downloads_target = Path.home() / "Downloads" / "Zydrakon_AI_Product_Plan.pdf"
    try:
        downloads_target.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copyfile(OUTPUT, downloads_target)
        print(f"Copied plan PDF to Downloads: {downloads_target}")
    except Exception as e:
        print(f"Note: Could not copy to Downloads: {e}")

if __name__ == "__main__":
    main()

