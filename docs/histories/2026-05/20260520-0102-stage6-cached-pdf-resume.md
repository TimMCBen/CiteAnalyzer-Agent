## [2026-05-20 01:02] | Task: Stage 6 cached-PDF resume path

**Scope:** live smoke resume script / Stage 7 country batching

### Summary

- Added `scripts/test_agent/e2e_resume_stage6_cached_pdfs.py` to rerun Stage 6/7 from existing `downloaded-papers/stage5/**/source.pdf` artifacts without re-downloading PDFs.
- Added `--skip-author-intel` for fast Stage 6-only reruns when the report can temporarily omit author profile, scholar, and country-map completeness.
- Changed Stage 7 country resolution to batch unresolved institutions through the LLM after deterministic rules, avoiding one model call per institution.

### Verification

- `python -m py_compile scripts/test_agent/e2e_resume_stage6_cached_pdfs.py packages/reporting/country_resolution.py packages/reporting/service.py`
- `python scripts/test_agent/stage7.py`
- `python scripts/test_agent/e2e_resume_stage6_cached_pdfs.py --target https://arxiv.org/pdf/2507.19457 --max-citations 10000 --log detail --skip-author-intel`

### Result

The cached-PDF resume run processed 157 Semantic Scholar citing papers, loaded 149 local PDFs, completed Stage 6 with `positive=24`, `neutral=21`, `critical=22`, `unknown=90`, and generated HTML/JSON/PDF reports under `generated-reports/2507-19457/`.

### Remaining Risk

The fast resume mode intentionally skips Stage 4, so author profile, important scholar, and country/region visualizations are incomplete. A complete full-report resume still needs persistent Stage 4 author-profile caching or batched OpenAlex author lookups.
