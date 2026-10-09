# Field journal

Consolidated daily log for the field campaign (5–12 October 2026). One entry per field day — add it the same day, even if brief. All times UTC.

## Entry template

```markdown
## Day X — Weekday, YYYY-MM-DD

### Plan
- Goal:
- Where:
- Who does what:

### Debrief
- Drone operations:
  - Location:
  - #flights:
  - Problems:
  - Data saved where:
  - Tomorrow:
- Notes:

### Other notes
```

---

## Day 1 — Monday, 2026-10-05

### Debrief

- Data backup! Check daily, or at least every other day.
- Start profiles in the middle of the valley up to 120 m, then go horizontally to the ridges to find the station positions.
- Comparison with Adventdalen:
  - similar measurements, positioned out of the valley outflow;
  - lidar and sodar observations from 2014–2017 should be included in the analysis;
  - radiosonde data also good for comparison;
  - calibration with the weather station;
  - "we all know that Adventdalen is best" → comparison target.
- Drone operations not necessarily needed tomorrow.
- Drone certificate.

---

## Day 2 — Tuesday, 2026-10-06 (D01 — site installations)

### Plan

Milestones:

1. Set up the weather stations.
2. Start with profile measurements (drones).
3. Start with the kite measurements.

### Debrief

#### Weather station setup

- Stations W1, W2, W3.
- W1 in the middle of the valley; W2, W3 on the slopes at the same altitude.
- Fly the drone at W1 up to 120 m, then horizontal transects to the slopes to find positions for W2, W3.
  - Alternative: use the elevation map, go out there, and communicate with the other side of the valley to check whether it works on both sides.
- Mount everything in the middle, then walk out.
- Tim has the drawings.

#### Flight plan — Endalen

- Profile every 50 m up to 120 m; record the exact position (compass app) and time for every flight.
- Idea: same position and same time every day, then flights in between.

#### Flight plan — Adventdalen

- Don't get too close to the entrance of the valley.
- Same as Endalen: profile at the fixed AWS, then work towards the mountain.

#### Kite

- Complementary measurements in the middle of the valley, right next to the AWS.
- Set up the kite when wind speed is high enough.

### Other notes

- Don't be too close to the bio measurement site (it is at the very beginning).
- Kartnorge as an app for navigation.
- We might only have 2 AWS, in which case we won't have one in the middle of the valley.
- Open questions:
  - Should we use the same upper height limit for the analysis?
  - How does the drone data handling work?
  - Anything to consider when mounting the AWS?
  - Do the stations have to be mounted at the same altitudes?

Photos: IMG_6155, IMG_6156 (linked in the old `plan_tuesday_20261006.md`, see git history).

---

## Day 3 — Wednesday, 2026-10-07

### Debrief

#### Drone operations (from the field)

- W1–W2 distance: 290 m.
- W1–W3 distance: 320 m.
- One profile up/down: ~5 min.
- Distance between measurement points: 50 m.
- At least 2 profiles per drone battery set.
- Open: can we charge batteries in the Aurora station?

#### Data processing discussion (group meeting)

Research questions:

- Is the katabatic wind feasible for wind energy to power a small town like Longyearbyen → how much can we generate / contribute?
- Is Endalen a suitable valley, or do we need more wind like in Adventdalen?
- How well is the wind captured by CARRA in the valley, and what information is needed to update the CARRA dataset?

Data sources:

- CARRA data
- Lidar and sodar data from Adventdalen
- iMET sensors
- AWS at the Aurora station

Work groups:

- AWS (ours + Aurora station): Irina, Ivan, Tim.
- Drone: Bruno, Alina.
- CARRA / ERA5 (larger scale): Emma, Fredi, Issac.
- Lidar / sodar (Adventdalen): Bruno.

Notes:

- Comparison study with CARRA for a weather situation similar to our campaign.
- How does the wind change across the transect?
- Where do we get the best output (enough wind and continuous power)?
- Use the Adventdalen lidar data for comparison.
- Discussed whether this is a feasible approach.

Ideas:

- Compare the 3 sites.
- Weibull distribution.
- CARRA & ERA5 as motivation for smaller-scale models:
  - CARRA doesn't have the same resolution;
  - a CARRA-based study needs at least one year → potential for wind energy?
  - we need more detail;
  - compare our small-scale installations with CARRA for the same period.
- What does the katabatic wind depend on?
- Compare our data with the Aurora station data and with CARRA.

What to show in the report (candidate figures/content):

- Map with the measurement locations.
- Data availability plot.
- Weibull distribution (extrapolated to the whole year?).
- Wind roses.
- Something with the drone data.
- Pictures from the installation and fieldwork.
- Description of the instruments and what they measure.
- Weather situation during the campaign, in perspective with climate change.
- Stability distribution.

---

## Day 4 — Thursday, 2026-10-08

### Debrief

- Endalen:
  - drone operations at every station;
  - drone operations between valley station and elevated station;
  - checked and fetched the AWS data;
  - saw 9 reindeers;
  - actually had some wind;
  - first river completely frozen;
  - no icing.
- Adventdalen:
  - simultaneous profiles next to the tower.

### Notebook transcription — station setup & drone flight log (source: notebook photos, 2026-10-08)

Values marked `[?]` were hard to read — verify against the original notebook photos before using them.

#### Station setup notes (Endalen)

- Station #3 Rosanne:
  - height of wind sensor (windmill): 165 + 54.5 = 209.5 cm
  - height of T/RH sensor: 186 cm
  - position: 78.18177°N, 15.75970°E
  - elevation E = 1.8 m; altitude = 142.2 m (E = 3 m `[?]`)
  - pressure: 975.8 hPa (octopus scale) at 15:31
- Additional (station unclear, possibly W3 / slope): height of wind sensor 154 + 60.5 = 214.5 cm; height of T/RH sensor 169 cm.

#### Drone flight log (times as in notebook, matching UTC data-file names)

| Flight | Site / path | Start (UTC) | Profile top / end (UTC) | Notes | Data file |
|---|---|---|---|---|---|
| #1 (attempt 1) | Endalen | 10:45 | — | Sensor was not on! Came back. | — |
| #1 (attempt 2) | Endalen | 10:50 | 120 m, 10:54 | Camera looking down | `DJI_MavicPro2_wind_20261008_1050.csv` |
| #2 | Middle between Rosanne and Bobby McGee | 11:10 | 120 m at 11:13, end 11:14 | | `DJI_MavicPro2_wind_20261008_1109.csv` |
| #3 | Bobby McGee | 11:23 | 120 m at 11:25, end 11:27 | | `DJI_MavicPro2_wind_20261008_1123.csv` |
| #4 | Between Bobby McGee and Mrs Robinson | 11:51 | 120 m at 11:54, end 11:55 | | `DJI_MavicPro2_wind_20261008_1151.csv` |
| #5 | Mrs Robinson | 12:04 | 120 m at 12:06, end 12:08 | | `DJI_MavicPro2_wind_20261008_1204.csv` |
| #6 | Mrs Robinson → Rosanne | 12:12 | end 12:18 | | `DJI_MavicPro2_wind_20261008_1212.csv` |
| #7 | Adventdalen, old Aurora station | 13:41 | 20 m at 13:43, end 13:45 | Position 78.20133°N, 15.82968°E | `DJI_MavicPro2_wind_20261008_1341.csv` |
| #8 | (Adventdalen?) | | | Position 78.18550°N, 15.74992°E; no further details in the notebook | — |

Icing-related drone files from the same day (from the data folder, not the notebook): `DJI_MavicPro2_icing_20261008_0302.csv`, `DJI_MavicPro2_icing_20261008_1234.csv`, `DJI_MavicPro2_icing_20261008_1247.csv`, `imet_SN611_202610080916.csv`, `imet_SN611_202610081548.csv`, `imet_SN657_202610081333.csv`.

---

## Day 5 — Friday, 2026-10-09

*(to be filled in)*

## Day 6 — Saturday, 2026-10-10

*(to be filled in)*

## Day 7 — Sunday, 2026-10-11

*(to be filled in)*

## Day 8 — Monday, 2026-10-12 (site removal & clean-up)

*(to be filled in)*
