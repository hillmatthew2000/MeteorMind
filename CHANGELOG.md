# Changelog

## 2.0.0 (unreleased)

A rewrite of most of the application. Existing data and API keys carry
over automatically.

### Upgrading from 1.0

- Install with `pip install -e .` and run `meteormind` or `meteormind-gui`.
  `python main.py` still works from a checkout, and so do the old `--cli`
  and `--gui` flags.
- Data moves from `./data` to a per-user folder (see the README). It is
  copied on first run; the old files are left in place.
- An API key in `config.json` or `.env` in the working directory is still
  found, but `meteormind config set-key` stores it in the per-user folder.
- Saved CSV reports no longer start with a `# title` line, and JSON
  reports have `generated_at` instead of `footer`.

### Added

- Command-line subcommands for scripts (`current`, `forecast`,
  `favorites`, `history`, `report`, `config`, `gui`), with JSON output,
  `--units` and meaningful exit codes. The interactive menu remains the
  default.
- `--demo` mode with deterministic offline sample data.
- A redesigned desktop app: favorites sidebar, Weather/History/Reports/
  Settings tabs, light and dark themes that can follow the system,
  keyboard shortcuts, and background lookups that never freeze the
  window.
- A choice between places with the same name in every interface;
  `--pick N` on the command line.
- Response caching that persists between runs, retries for transient
  failures, and errors that say what went wrong and what to do.
- Data tools: back up, clear the cache, delete everything. The desktop
  app logs unexpected errors to `meteormind.log`.
- Reproducible sample reports in `examples/reports`.

### Fixed

- Temperature changes in trend reports were converted as absolute
  temperatures (+1 °C showed as +33.8 °F).
- Report tables lined up badly with multi-line cells and non-Latin
  place names, and cut long values off; CSV export did not escape
  commas or quotes.
- Searching "London" could show a nearby station's name instead.
- Forecast days followed the computer's date rather than the place's.
- An invalid key or a network outage was reported as "location not
  found".
- Choosing inches of mercury, or the wind speed and distance units in the
  menu, crashed.
- Names in other scripts (東京, Αθήνα) were rejected, and capitalisation
  such as "McAllen" was changed.
- The desktop app swallowed errors from failed requests.

### Development

- Installable `src/` package, ruff for linting and formatting, strict
  mypy, over 300 tests that never touch the network, and CI on Ubuntu
  and Windows.
