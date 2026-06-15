# Coverage Audit Methodology

The coverage audit summarizes which source layers are strong enough for public
analysis and which should be framed as future work.

The goal is not to make the OCR perfect. The goal is to be transparent:
publish useful lifecycle analysis now, while showing readers where source
coverage is complete, partial, or pending.

Run:

```powershell
python -m src.analysis.build_coverage_audit
```

Outputs:

- `outputs/public/coverage_by_year.csv`
- `outputs/public/source_coverage_audit.csv`
- `docs/data_coverage_and_future_work.md`
