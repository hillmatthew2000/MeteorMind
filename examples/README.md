# Examples

`reports/` holds one sample of every report MeteorMind can build, made from
the offline demo data:

| File | Command that builds the same kind of report |
| --- | --- |
| `compare.txt`, `.csv`, `.json` | `meteormind report compare London Paris Tokyo "New York" Sydney` |
| `forecast.txt` (imperial units) | `meteormind --units imperial report forecast London --days 5` |
| `forecast-compare.txt`, `.csv` | `meteormind report forecast-compare London Paris Tokyo --days 3` |
| `trends.txt` | `meteormind report trends London` |
| `locations.txt` | `meteormind report locations` |
| `history.txt` | `meteormind report history` |

Add `--demo` to any of these to try them without an API key, and
`-o FILE` (`.txt`, `.csv` or `.json`) to save instead of print.

The samples use a fixed date and clock, so regenerating them gives
identical files:

```bash
python examples/sample_reports.py           # rewrite examples/reports
python examples/sample_reports.py OUT_DIR   # or write them elsewhere
```

The test suite fails if the committed samples and the script's output
drift apart, so rerun it after changing how reports look.
