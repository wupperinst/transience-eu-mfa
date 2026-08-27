# MIC3 — the supply module for the core model, EU MFA

EU MFA takes its data from **OPEN-GEM**, **OPEN-PROM** and the **P&S database**.
MIC3 is where all of that arrives and becomes model input.

```
OPEN-GEM  ┐
P&S       ┼─►  src/mic3  ─►  buildings parameters  ─►  buildings MFA
OPEN-PROM ┘                  vehicle_inflow        ─►  vehicles / combined MFA
                             vehicle steel intensity
```

| | |
|---|---|
| **Code** | `src/mic3/` (this folder) |
| **Command** | `eumfa_mic3.py` (repo root) |
| **Config** | `config/mic3.yml` |
| **Raw inputs** | `data/MIC3_models/input/datasets/` |
| **Provenance copies** | `data/MIC3_models/output/` |

## Run order

```bash
python eumfa_mic3.py          # refresh the inputs
python eumfa_buildings.py     # buildings sub-module
python eumfa_vehicles.py      # vehicles sub-module
```

## Files

| file | role |
|---|---|
| `mic3_model.py` | `Mic3Model`: reads config, builds every input, writes and archives it. |
| `mic3_parameters.py` | The buildings extractions, and the vehicle material intensities. |
| `mic3_vehicle_inflow.py` | The OPEN-PROM translation (`build_inflow`, `summary`). Moved here from the former `src/openprom`; the method is unchanged. |

## What it supplies

**Buildings** — `building_population`, `building_floor_space_per_capita`,
`building_residential_share`, `building_old_stock`,
`building_commercial_base_year`, `building_service_output`.

Population is the calibrated history to 2024, then OPEN-GEM, reported at
five-year intervals and linearly interpolated. Regions OPEN-GEM does not cover
(GBR) hold their 2024 level and see no service-driven growth.

**Vehicles** — `vehicle_inflow`, plus `vehicle_steel_intensity_B`.

## No model logic here

The required stock, new construction, the age-cohort split and the construction
and demolition flows are all computed inside the EU MFA itself, in
`BuildingsMFASystem`. Keeping the supply separate from the accounting means a
new OPEN-GEM scenario or P&S release changes only what MIC3 reads.

## Switches (`config/mic3.yml`)

- `translate_intensities: False` — the **buildings** material intensities ship
  with the model. Turning this on rebuilds them from the P&S inventory sheets;
  verified to reproduce the shipped files to 4e-7.
- `translate_vehicle_intensities: ['steel']` — only the **baseline** steel
  scenario is written; `HSS_*` and `Redesign_*` are never touched. Steel
  reproduces the shipped file exactly (6e-14). Adding `'plastics'` or `'glass'`
  **changes results** — plastics is 15–18% lower for Fuel Cells – Hydrogen, and
  the shipped glass file predates the current `vehicle_types` dimension.

## Known limitation: the OPEN-PROM inflow starts in 2023

The translation covers **2023–2050**, so the vehicles model has no inflow for
2020–2022 and its stock cold-starts in 2023. To close that gap, either extend
the translation back before 2023, or merge 2023–2050 on top of the historical
rows kept from the original file.

## Method (vehicle inflow)

Documented in full in the `mic3_vehicle_inflow.py` docstring. In brief: the
Eurostat new-registration base is split across motor types by OPEN-PROM 2024
capacity-addition shares; 2023 is that base ×0.9877353; 2025–2050 follow the
OPEN-PROM trajectory rescaled to the Eurostat level; hydrogen is Eurostat-flat
to 2026, then OPEN-PROM.
