# AGENTS.md

This file provides context for AI agents (and humans) working in this repository.

## Standing rules

- **All files and documents in this repository must be written in English.** This includes commit messages, READMEs, journals, tables, comments, and new notes.
- Use snake_case for new file names.
- Record all times in UTC.
- Every field day gets an entry in `01_days/field_journal.md` — write it the same day, even if brief.
- `FieldReportInstructions.pdf` is the authoritative source for report deadlines; `Report_instructions.pdf` is from 2025 and is superseded.

## Project context

- **Course:** AE-342 Arctic Energy Meteorology (UNIS, Svalbard), autumn 2026.
- **Field campaign:** around Longyearbyen / Adventdalen / Endalen, 5–12 October 2026. Site installations on 6 October, site removal and clean-up on 12 October.
- **Group:** Group B — "Wind Power" (members: Alina, Bruno, Emma, Fredi, Irina, Ivan, Issac, Tim).
- **Goal:** assess whether the wind regime (e.g. katabatic winds) in the valleys around Longyearbyen is feasible for wind energy production, and how well it is captured by reanalysis (CARRA/ERA5), compared with observations and other sites such as Adventdalen.

### Instruments / equipment

- 3 automatic weather stations (AWS: temperature, humidity, anemometer) — named Bobby McGee, Mrs Robinson, Rosanne.
- 2 DJI Mavic Pro 2 drones with sensor payloads (iMET sondes SN611, SN657) for wind/temperature profiles.
- 1 kite for complementary profiles next to the valley AWS.
- AWS data also available from the Aurora station.

### Data conventions

- Raw data lives in `03_data_analysis/data/` together with `instruments.csv`, `locations.csv`, `flights.csv`; plus `analyze_aws_data.py`.
- File naming: `YYYYMMDD_instrument_location_flight.ext` (UTC time, decimal degrees, pressure-based altitude).
- Plots and their index live in `04_plots/`.
- See `03_data_analysis/README.md` for the data workflow and end-of-day checklist.

## Repository map

```
01_days/          field_journal.md — consolidated daily log (one entry per field day)
02_logistics/     packing_list.md
03_data_analysis/ data (raw .dat/.csv, instrument/location/flight logs), src/ (analysis scripts), README.md (data conventions)
04_plots/         generated plots + plots.md (index)
research_questions.md
REPORT_PLAN.md    group organization, task split, report outline, deadlines
AGENTS.md         this file
README.md         repository index
```
