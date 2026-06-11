# Legacy copied files — do not use for new runs

These files were copied from the earlier System Current internal tooling version.

For the standalone tool, use the root-level package instead:

```bash
python -m leadgen.run_pipeline \
  --queries-file data/queries/calgary_home_services.csv \
  --batch-name calgary_home_services_001 \
  --mode no-website-first
```

The supported standalone package is:

```text
leadgen/
```

The old `src/lead_pipeline/` path may contain outdated System Current wording, misleading internal paths, and older offer names. Keep it only as legacy reference until it is deleted.
