"""
MIC3 -- the supply module for the core model, EU MFA.

EU MFA takes its data from OPEN-GEM, OPEN-PROM and the P&S database. This is
where all of that arrives and becomes model input:

    buildings : OPEN-GEM + P&S   ->  the buildings parameters
    vehicles  : OPEN-PROM        ->  vehicle_inflow

No model logic lives here. Stocks, flows and cohorts are computed inside the
EU MFA sub-modules themselves.

    python eumfa_mic3.py         # refresh the inputs
    python eumfa_buildings.py    # run the buildings sub-module
    python eumfa_vehicles.py     # run the vehicles sub-module
"""

import csv
import logging
import shutil
from pathlib import Path

from src.mic3 import mic3_parameters as prm
from src.mic3.mic3_vehicle_inflow import build_inflow


class Mic3Model:
    """Turn the upstream MIC3 sources into EU MFA inputs."""

    def __init__(self, cfg: dict, root: Path = None):
        self.cfg = cfg
        self.root = Path(root) if root else Path.cwd()

        inputs = cfg.get("inputs", {})
        self.opengem_path = self._resolve(inputs.get("opengem"))
        self.ps_path = self._resolve(inputs.get("ps_database"))
        self.history_path = self._resolve(inputs.get("population_history"))
        self.openprom_path = self._resolve(inputs.get("openprom"))
        self.eurostat_path = self._resolve(inputs.get("eurostat"))

        output = cfg.get("output", {})
        self.datasets_path = self._resolve(output.get("datasets"))
        self.vehicle_inflow_path = self._resolve(output.get("vehicle_inflow"))
        self.archive_path = self._resolve(output.get("archive")) if output.get("archive") else None
        self.backup = cfg.get("backup_existing", True)
        # The material intensities already ship with the model. Translating them
        # from the P&S database is off by default so a change there cannot move
        # the model's numbers without someone asking for it.
        self.translate_intensities = cfg.get("translate_intensities", False)
        # Which vehicle materials to translate from P&S. Only steel is on by
        # default: it reproduces the shipped baseline exactly, so switching the
        # source cannot move the model. Plastics and glass do differ -- see the
        # note in config/mic3.yml.
        self.translate_vehicle_intensities = cfg.get("translate_vehicle_intensities", ["steel"])
        # The shipped baseline steel file spans 2012-2050, wider than the model's
        # own time dimension; keep that range so the file stays a drop-in match.
        span = cfg.get("vehicle_intensity_years")
        self.vehicle_intensity_years = list(range(span[0], span[1] + 1)) if span else None

    def _resolve(self, rel):
        if rel is None:
            return None
        path = Path(rel)
        return path if path.is_absolute() else (self.root / path)

    def _dimension_items(self, filename, datasets_path=None):
        """
        Read one of a sub-module's own dimension files.

        Parsed as CSV, since items containing a comma are quoted in the file.
        """
        base = datasets_path or self.datasets_path
        path = base.parent / "dimensions" / filename
        with open(path, encoding="utf-8-sig", newline="") as handle:
            return [row[0].strip() for row in csv.reader(handle) if row and row[0].strip()]

    def _regions(self):
        """Region list, taken from the buildings sub-module's dimension file."""
        return self._dimension_items("regions.csv")

    def _archive(self, table, name):
        if self.archive_path:
            self.archive_path.mkdir(parents=True, exist_ok=True)
            table.to_csv(self.archive_path / f"{name}.csv", index=False, encoding="utf-8-sig")

    # ----------------------------------------------------------------- #
    # buildings: OPEN-GEM + P&S
    # ----------------------------------------------------------------- #
    def build_buildings(self):
        """Return {parameter name: long DataFrame} for the buildings sub-module."""
        regions = self._regions()

        pop, frozen_pop = prm.population(self.opengem_path, self.history_path)
        output, flat_service = prm.service_output(self.opengem_path, regions)

        if frozen_pop:
            logging.info("[MIC3] %s not in OPEN-GEM population; held at the %d level",
                         ", ".join(frozen_pop), prm.HISTORY_YEARS[-1])
        if flat_service:
            logging.info("[MIC3] %s not in OPEN-GEM service output; commercial floor "
                         "area held flat", ", ".join(flat_service))

        tables = {
            "building_population": pop,
            "building_floor_space_per_capita": prm.floor_space_per_capita(self.ps_path),
            "building_residential_share": prm.residential_share(self.ps_path),
            "building_old_stock": prm.old_stock(self.ps_path),
            "building_commercial_base_year": prm.commercial_base_year(self.ps_path),
            "building_service_output": output,
        }

        # Material intensities, translated from the P&S inventory sheets.
        # Opt-in: see translate_intensities in config/mic3.yml.
        if self.translate_intensities:
            for material in prm.MATERIALS:
                items = self._dimension_items(f"{material}_products.csv")
                tables[f"building_{material}_intensity"] = prm.material_intensity(
                    self.ps_path, material, items
                )
        else:
            logging.info("[MIC3]   material intensities: using the files that ship "
                         "with the model (translate_intensities: False)")
        return tables

    def run_buildings(self):
        logging.info("[MIC3] buildings <- OPEN-GEM  %s", self.opengem_path.name)
        logging.info("[MIC3] buildings <- P&S       %s", self.ps_path.name)

        tables = self.build_buildings()
        self.datasets_path.mkdir(parents=True, exist_ok=True)
        for name, table in tables.items():
            target = self.datasets_path / f"{name}.csv"
            table.to_csv(target, index=False, encoding="utf-8-sig")
            logging.info("[MIC3]   wrote %-34s %6d rows", name, len(table))
            self._archive(table, name)
        return tables

    # ----------------------------------------------------------------- #
    # vehicles: OPEN-PROM
    # ----------------------------------------------------------------- #
    def run_vehicles(self):
        """Build vehicle_inflow from OPEN-PROM and Eurostat."""
        if not (self.openprom_path and self.eurostat_path and self.vehicle_inflow_path):
            logging.info("[MIC3] vehicles: no OPEN-PROM paths configured, skipping")
            return None

        logging.info("[MIC3] vehicles  <- OPEN-PROM %s", self.openprom_path.name)
        logging.info("[MIC3] vehicles  <- Eurostat  %s", self.eurostat_path.name)
        table = build_inflow(self.eurostat_path, self.openprom_path)

        # keep one backup of whatever stood there before MIC3 first overwrote it
        if self.backup and self.vehicle_inflow_path.exists():
            backup = self.vehicle_inflow_path.with_suffix(".pre_mic3.bak.csv")
            if not backup.exists():
                shutil.copy2(self.vehicle_inflow_path, backup)
                logging.info("[MIC3]   backed up existing inflow -> %s", backup.name)

        self.vehicle_inflow_path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(self.vehicle_inflow_path, index=False, encoding="utf-8-sig")
        logging.info("[MIC3]   wrote %-34s %6d rows", "vehicle_inflow", len(table))
        self._archive(table, "vehicle_inflow")

        self.run_vehicle_intensities()
        return table

    def run_vehicle_intensities(self):
        """
        Vehicle material intensities, translated from the P&S inventory sheets.

        Only the baseline steel scenario is written. The other scenario files
        (HSS_*, Redesign_*) are left alone -- the P&S database carries the
        baseline only, and the scenarios are selected in config/vehicles.yml.
        """
        wanted = self.translate_vehicle_intensities or []
        if not wanted:
            return
        datasets = self.vehicle_inflow_path.parent
        types = self._dimension_items("vehicle_types.csv", datasets)
        years = [int(y) for y in self._dimension_items("time_in_years.csv", datasets)]

        for material, (_, has_time) in prm.VEHICLE_MATERIALS.items():
            if material not in wanted:
                continue
            products = self._dimension_items(f"{material}_products.csv", datasets)
            table, dropped = prm.vehicle_intensity(
                self.ps_path, material, products, types,
                years=self.vehicle_intensity_years or years if has_time else None,
            )
            if dropped:
                logging.info("[MIC3]   %s: %s not in the model's vehicle types, dropped",
                             material, ", ".join(dropped))
            # steel is scenario-driven; MIC3 supplies the baseline only
            stem = f"vehicle_{material}_intensity" + ("_B" if material == "steel" else "")
            table.to_csv(datasets / f"{stem}.csv", index=False, encoding="utf-8-sig")
            logging.info("[MIC3]   wrote %-34s %6d rows", stem, len(table))
            self._archive(table, stem)

    # ----------------------------------------------------------------- #
    def run(self):
        logging.info("[MIC3] Supplying EU MFA inputs")
        tables = self.run_buildings()
        vehicles = self.run_vehicles()
        if vehicles is not None:
            tables["vehicle_inflow"] = vehicles
        return tables
