# Pilot acceptance and verification

This is an evidence checklist, not a certificate of production readiness. A 90/100 target requires every mandatory gate. Root implementation verification updates the actual run results below; unexecuted checks must stay explicitly unverified.

## Scorecard

| Area | Weight | Evidence required |
|---|---:|---|
| Numerical correctness | 30 | At least 60 independent expected-result cases; all supported computations correct |
| Cloud interpretation | 20 | At least 95% correct plans on held-out supported questions, with the configured live model |
| Parsing/OCR | 15 | Messy CSV/XLSX fixtures and at least 10 clear-table images; review gate tested |
| Privacy/access | 25 | No Restricted-data outbound call; cross-user requests denied; cloud key stays backend-only |
| Usability/recovery | 10 | Both users complete tasks; timeout/retry/restart/delete/restore verified |

Mandatory failures: wrong numerical result, unauthorized access, Restricted-data cloud transmission, or analysis of an unconfirmed OCR extraction. A high weighted total cannot override a mandatory failure.

## Automated checks

- Calculation suite: independently specified values, nulls, negatives, grouping, percentage denominator handling, comparisons, filters and rounding.
- Parsing suite: valid/malformed CSV and XLSX, empty data, repeated headers, formula flags, row/column limits and image-review gating.
- API suite: setup/login, two-account limit, ownership, CSRF, version checks, classification, cloud call prevention, deletion, retries and failure handling.
- Frontend: TypeScript check and production build.

Execution status and counts are recorded by the implementing agent after test runs. Until then, none of the above should be described as passed.

## External and human checks (not implied by unit tests)

1. **Live cloud model:** configure a real API key and confirm model access. Freeze a held-out question set before evaluating. Record correct/incorrect/clarification outcomes, token usage and latency. Provider mocks do not establish model quality.
2. **Actual OCR executable:** install Tesseract; process at least 10 representative clear table images. Review extraction accuracy and confirm calculations are blocked until review. Mock OCR tests establish control flow only.
3. **Two-user UAT:** each person independently uploads, inspects, corrects, asks/analyses and verifies five representative tasks; check account separation.
4. **Actual-PC capacity:** import the maximum supported files, measure cold/warm times and peak memory, and exercise both users concurrently. Configured limits are not measured performance claims.
5. **Network evidence:** instrument provider calls and test Restricted datasets, errors, retries and mixed conversations. No restricted prompt/schema/result should reach an outbound request.
6. **Backup/restore:** stop services, back up all local storage, restore in a disposable data directory and verify source/evidence continuity.

## Safe evaluation rules

Use synthetic files and synthetic questions for cloud tests. Classification is a human attestation; malicious or mistaken attestations are not automatically detectable. Do not send real company data merely to improve this scorecard.

Retain test timestamps, environment/dependency versions, model ID, dataset hashes and summarized outcomes. Do not log API keys or sensitive raw prompts in ordinary operational logs.
