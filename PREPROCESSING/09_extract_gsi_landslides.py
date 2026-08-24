"""Extract and label the GSI Sikkim historical-landslide inventory.

This reproducible pipeline:

1. extracts the validated Sikkim table block from the source PDF;
2. preserves source values while adding conservative temporal-quality fields;
3. assigns valid coordinates to the existing 1 km Sikkim grid;
4. creates affected-cell and static-feature label tables; and
5. writes a machine-readable validation report and label documentation.

The source PDF and all files under DATA/RAW are read-only inputs. A value of 0
in ``historically_affected`` means only "not present in the available GSI
inventory"; it does not mean "confirmed landslide-free". Likewise,
``inventory_record_count`` is an inventory count, not true landslide frequency.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pdfplumber
from shapely.geometry import Point


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED = PROJECT_ROOT / "DATA" / "PROCESSED"
SOURCE_PDF = (
    PROJECT_ROOT
    / "DATA"
    / "RAW"
    / "DYNAMIC"
    / "Landslides"
    / "GSI"
    / "landslide_report.pdf"
)
GRID_PATH = PROCESSED / "GRID" / "sikkim_grid_1km.gpkg"
STATIC_FEATURES_PATH = (
    PROCESSED / "FEATURES" / "sikkim_static_features_1km.csv"
)

LANDSLIDE_OUTPUT_DIR = PROCESSED / "LANDSLIDES"
INVENTORY_CSV = LANDSLIDE_OUTPUT_DIR / "gsi_sikkim_inventory.csv"
INVENTORY_GPKG = LANDSLIDE_OUTPUT_DIR / "gsi_sikkim_inventory.gpkg"
DATED_EVENTS_CSV = LANDSLIDE_OUTPUT_DIR / "gsi_sikkim_dated_events.csv"
AFFECTED_CELLS_CSV = (
    LANDSLIDE_OUTPUT_DIR / "sikkim_historical_affected_cells.csv"
)
AFFECTED_CELLS_GPKG = (
    LANDSLIDE_OUTPUT_DIR / "sikkim_historical_affected_cells.gpkg"
)
VALIDATION_REPORT = LANDSLIDE_OUTPUT_DIR / "gsi_sikkim_validation.json"
DOCUMENTATION_PATH = LANDSLIDE_OUTPUT_DIR / "README.md"
LABELLED_FEATURES_CSV = (
    PROCESSED / "FEATURES" / "sikkim_static_features_with_history.csv"
)

SIKKIM_PDF_PAGES = range(659, 677)
EXPECTED_REFERENCE_ROWS = 777
EXPECTED_REFERENCE_AFFECTED_CELLS = 456
INVENTORY_LAYER = "gsi_sikkim_inventory"
AFFECTED_CELLS_LAYER = "sikkim_historical_affected_cells"

SOURCE_HEADERS = [
    "Sl.No.",
    "Slide_No",
    "State",
    "District",
    "Slide_Name",
    "NH_SH_Location",
    "Latitude",
    "Longitude",
    "Material Involved",
    "Movement Type",
    "History",
]
NORMALIZED_HEADERS = [
    "sl_no",
    "slide_no",
    "state",
    "district",
    "slide_name",
    "nh_sh_location",
    "latitude",
    "longitude",
    "material_involved",
    "movement_type",
    "history",
]
TEMPORAL_TYPES = {
    "exact_date",
    "year_only",
    "range_or_multiple",
    "other_interpretable",
    "missing",
}
MISSING_HISTORY_VALUES = {"", "na", "n/a", "null"}
MONTH_PATTERN = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)"
)
DAY_DATE_RE = re.compile(
    rf"\b(?P<day>[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+"
    rf"(?P<month>{MONTH_PATTERN})\s+(?P<year>(?:19|20)\d{{2}})\b",
    re.IGNORECASE,
)
DAY_RANGE_RE = re.compile(
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s*(?:-|&|to)\s*"
    rf"\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH_PATTERN}\s+"
    rf"(?:19|20)\d{{2}}\b",
    re.IGNORECASE,
)
MONTH_RANGE_RE = re.compile(
    rf"\b{MONTH_PATTERN}\s*(?:/|-)\s*{MONTH_PATTERN}\s+"
    rf"(?:19|20)\d{{2}}\b",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
YEAR_ONLY_RE = re.compile(
    r"^(?:19|20)\d{2}(?:\s*,\s*(?:19|20)\d{2})*$"
)
MONTH_NUMBER = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def require(condition: bool, message: str) -> None:
    """Raise a clear validation error when a data contract is violated."""
    if not condition:
        raise RuntimeError(message)


def clean_cell(value: str | None) -> str:
    """Remove extraction-only line wrapping without normalizing source terms."""
    return re.sub(r"\s+", " ", value or "").strip()


def sha256(path: Path) -> str:
    """Return a streaming SHA-256 digest without loading the large PDF in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def classify_temporal(history: str) -> str:
    """Classify History conservatively without using the Slide_No identifier."""
    value = history.strip()
    if value.casefold() in MISSING_HISTORY_VALUES:
        return "missing"
    if YEAR_ONLY_RE.fullmatch(value):
        return "year_only"

    exact_dates = list(DAY_DATE_RE.finditer(value))
    years = YEAR_RE.findall(value)
    explicit_range = bool(
        DAY_RANGE_RE.search(value)
        or MONTH_RANGE_RE.search(value)
        or re.search(r"\bbetween\b.+\band\b", value, re.IGNORECASE)
    )
    multiple_temporal_references = len(exact_dates) > 1 or len(years) > 1
    if explicit_range or multiple_temporal_references:
        return "range_or_multiple"
    if len(exact_dates) == 1:
        return "exact_date"
    return "other_interpretable"


def parse_exact_event_date(history: str, temporal_type: str) -> str:
    """Return ISO date only for a single defensible day-level History value."""
    if temporal_type != "exact_date":
        return ""
    match = DAY_DATE_RE.search(history)
    require(match is not None, f"Exact-date classification could not be parsed: {history}")
    day = int(match.group("day"))
    month_text = match.group("month").casefold()
    year = int(match.group("year"))
    try:
        return date(year, MONTH_NUMBER[month_text], day).isoformat()
    except ValueError as error:
        raise RuntimeError(f"Invalid calendar date in History: {history}") from error


def extract_inventory() -> pd.DataFrame:
    """Extract actual Sikkim records from the validated 18-page table block."""
    records: list[dict] = []
    with pdfplumber.open(SOURCE_PDF) as pdf:
        for pdf_page in SIKKIM_PDF_PAGES:
            table = pdf.pages[pdf_page - 1].extract_table()
            require(table is not None and len(table) > 1, f"No table on page {pdf_page}")
            header = [clean_cell(value) for value in table[0]]
            require(
                header == SOURCE_HEADERS,
                f"Unexpected table schema on page {pdf_page}: {header}",
            )
            for raw_row in table[1:]:
                values = [clean_cell(value) for value in raw_row]
                require(
                    len(values) == len(SOURCE_HEADERS),
                    f"Unexpected row width on page {pdf_page}: {len(values)}",
                )
                source_record = dict(zip(NORMALIZED_HEADERS, values, strict=True))
                if source_record["state"].casefold() != "sikkim":
                    continue
                source_record["source_pdf_page"] = pdf_page
                records.append(source_record)

    inventory = pd.DataFrame.from_records(records)
    require(not inventory.empty, "No Sikkim inventory rows were extracted")
    inventory["sl_no"] = pd.to_numeric(inventory["sl_no"], errors="raise").astype(
        "int64"
    )
    inventory["latitude"] = pd.to_numeric(
        inventory["latitude"], errors="coerce"
    ).astype("float64")
    inventory["longitude"] = pd.to_numeric(
        inventory["longitude"], errors="coerce"
    ).astype("float64")
    require(inventory["sl_no"].is_unique, "Extracted Sl.No. values are not unique")
    require(
        inventory["sl_no"].is_monotonic_increasing,
        "Extracted Sl.No. values are not ordered",
    )

    inventory["temporal_type"] = inventory["history"].map(classify_temporal)
    require(
        set(inventory["temporal_type"]).issubset(TEMPORAL_TYPES),
        "Unexpected temporal type was produced",
    )
    inventory["event_date"] = [
        parse_exact_event_date(history, temporal_type)
        for history, temporal_type in zip(
            inventory["history"], inventory["temporal_type"], strict=True
        )
    ]
    return inventory


def valid_coordinate_mask(inventory: pd.DataFrame) -> pd.Series:
    """Identify finite, globally valid WGS84 coordinate pairs."""
    latitude = inventory["latitude"]
    longitude = inventory["longitude"]
    return (
        latitude.notna()
        & longitude.notna()
        & np.isfinite(latitude)
        & np.isfinite(longitude)
        & latitude.between(-90, 90)
        & longitude.between(-180, 180)
    )


def assign_grid_cells(
    inventory: pd.DataFrame, grid: gpd.GeoDataFrame
) -> tuple[pd.DataFrame, list[int], list[dict]]:
    """Assign valid points deterministically to the existing square grid."""
    result = inventory.copy()
    result["cell_id"] = ""
    result["historically_affected"] = 1
    valid = valid_coordinate_mask(result)
    point_geometry = [
        Point(longitude, latitude)
        for longitude, latitude in zip(
            result.loc[valid, "longitude"],
            result.loc[valid, "latitude"],
            strict=True,
        )
    ]
    points = gpd.GeoDataFrame(
        {"inventory_index": result.index[valid]},
        geometry=point_geometry,
        crs="EPSG:4326",
    ).to_crs(grid.crs)
    joined = gpd.sjoin(
        points,
        grid[["cell_id", "geometry"]],
        how="left",
        predicate="intersects",
    ).sort_values(["inventory_index", "cell_id"], na_position="last")

    match_counts = joined.groupby("inventory_index")["cell_id"].count()
    multiple_matches = []
    for index in match_counts[match_counts > 1].index:
        cell_ids = joined.loc[joined["inventory_index"] == index, "cell_id"].tolist()
        multiple_matches.append(
            {"sl_no": int(result.loc[index, "sl_no"]), "candidate_cell_ids": cell_ids}
        )
    selected = joined.drop_duplicates("inventory_index", keep="first")
    assignments = selected.set_index("inventory_index")["cell_id"]
    mapped = assignments.dropna()
    result.loc[mapped.index, "cell_id"] = mapped.astype(str)
    outside_indices = assignments[assignments.isna()].index
    outside_sl_nos = result.loc[outside_indices, "sl_no"].astype(int).tolist()
    return result, outside_sl_nos, multiple_matches


def duplicate_summary(inventory: pd.DataFrame) -> dict:
    """Summarize duplicate identifiers and exact coordinate pairs."""
    slide_key = inventory["slide_no"].str.strip().str.casefold()
    slide_key = slide_key[slide_key != ""]
    slide_counts = slide_key.value_counts()
    duplicate_slide_counts = slide_counts[slide_counts > 1]

    valid = valid_coordinate_mask(inventory)
    coordinate_counts = (
        inventory.loc[valid]
        .groupby(["latitude", "longitude"], dropna=False)
        .size()
        .sort_values(ascending=False)
    )
    duplicate_coordinate_counts = coordinate_counts[coordinate_counts > 1]
    return {
        "slide_no": {
            "missing_count": int((inventory["slide_no"].str.strip() == "").sum()),
            "unique_nonmissing_count": int(slide_key.nunique()),
            "duplicate_value_count": int(len(duplicate_slide_counts)),
            "duplicate_excess_record_count": int(
                (duplicate_slide_counts - 1).sum()
            ),
            "affected_record_count": int(duplicate_slide_counts.sum()),
            "values": {
                value: int(count)
                for value, count in duplicate_slide_counts.items()
            },
        },
        "coordinates": {
            "duplicate_pair_count": int(len(duplicate_coordinate_counts)),
            "duplicate_excess_record_count": int(
                (duplicate_coordinate_counts - 1).sum()
            ),
            "affected_record_count": int(duplicate_coordinate_counts.sum()),
            "pairs": [
                {
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                    "record_count": int(count),
                }
                for (latitude, longitude), count in duplicate_coordinate_counts.items()
            ],
        },
    }


def write_documentation() -> None:
    """Write durable label semantics beside the generated landslide datasets."""
    text = """# GSI Sikkim historical-landslide processed datasets

These files are generated by `PREPROCESSING/09_extract_gsi_landslides.py`
from the field-validated GSI inventory PDF. Source values are preserved except
for normalized column names and collapsed PDF line-wrap whitespace.

## Label semantics

- `historically_affected = 1`: one or more records in the available GSI
  inventory intersect the 1 km grid cell.
- `historically_affected = 0`: no record for the cell is present in the
  available GSI inventory. It does **not** mean confirmed landslide-free.
- `inventory_record_count`: count of extracted inventory rows assigned to the
  cell. It must not be interpreted as true landslide frequency because the
  inventory can contain duplicates and uneven observation/collection effort.

## Temporal semantics

- `exact_date`: one unambiguous day-month-year event date; `event_date` is set.
- `year_only`: only a year is available; `event_date` remains empty.
- `range_or_multiple`: a date range or multiple event references are present.
- `other_interpretable`: temporal information exists but is coarser than an
  exact date, such as month-year or an approximate week.
- `missing`: the source History value is empty, NA, N/A, or NULL.

The year embedded in `slide_no` is never used to populate `event_date`; its
meaning is not documented in the source PDF and can disagree with History.

## Coordinate reference systems

- `gsi_sikkim_inventory.gpkg`: EPSG:4326 point geometry.
- `sikkim_historical_affected_cells.gpkg`: the existing grid CRS, EPSG:32645.
"""
    DOCUMENTATION_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    required_inputs = [SOURCE_PDF, GRID_PATH, STATIC_FEATURES_PATH]
    missing = [str(path) for path in required_inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required input files: {missing}")

    source_hash_before = sha256(SOURCE_PDF)
    inventory = extract_inventory()
    grid = gpd.read_file(GRID_PATH, layer="sikkim_grid_1km")
    require(grid.crs is not None, "Grid has no CRS")
    require(grid["cell_id"].is_unique, "Grid cell_id values are not unique")
    inventory, outside_grid_sl_nos, multiple_grid_matches = assign_grid_cells(
        inventory, grid
    )

    valid_coordinates = valid_coordinate_mask(inventory)
    mapped = inventory["cell_id"].ne("")
    affected_counts = inventory.loc[mapped, "cell_id"].value_counts().sort_index()
    affected_cells = grid.loc[grid["cell_id"].isin(affected_counts.index)].copy()
    affected_cells["historically_affected"] = 1
    affected_cells["inventory_record_count"] = (
        affected_cells["cell_id"].map(affected_counts).astype("int64")
    )
    affected_cells = affected_cells.sort_values("cell_id").reset_index(drop=True)

    static_features = pd.read_csv(STATIC_FEATURES_PATH)
    require(
        static_features["cell_id"].is_unique,
        "Static feature cell_id values are not unique",
    )
    require(
        set(static_features["cell_id"]) == set(grid["cell_id"]),
        "Static feature and grid cell IDs differ",
    )
    labels = affected_counts.rename("inventory_record_count")
    labelled_features = static_features.merge(
        labels,
        left_on="cell_id",
        right_index=True,
        how="left",
        validate="one_to_one",
    )
    labelled_features["inventory_record_count"] = (
        labelled_features["inventory_record_count"].fillna(0).astype("int64")
    )
    labelled_features["historically_affected"] = (
        labelled_features["inventory_record_count"].gt(0).astype("int64")
    )
    original_columns = static_features.columns.tolist()
    labelled_features = labelled_features[
        original_columns + ["historically_affected", "inventory_record_count"]
    ]

    LANDSLIDE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LABELLED_FEATURES_CSV.parent.mkdir(parents=True, exist_ok=True)
    inventory.to_csv(INVENTORY_CSV, index=False, encoding="utf-8")
    dated_events = inventory.loc[
        inventory["temporal_type"] == "exact_date"
    ].copy()
    dated_events.to_csv(DATED_EVENTS_CSV, index=False, encoding="utf-8")
    affected_cells.drop(columns="geometry").to_csv(
        AFFECTED_CELLS_CSV, index=False, encoding="utf-8"
    )
    labelled_features.to_csv(
        LABELLED_FEATURES_CSV, index=False, encoding="utf-8"
    )

    if INVENTORY_GPKG.exists():
        INVENTORY_GPKG.unlink()
    inventory_geometry = [
        Point(longitude, latitude)
        if is_valid
        else None
        for longitude, latitude, is_valid in zip(
            inventory["longitude"],
            inventory["latitude"],
            valid_coordinates,
            strict=True,
        )
    ]
    inventory_geospatial = gpd.GeoDataFrame(
        inventory.copy(), geometry=inventory_geometry, crs="EPSG:4326"
    )
    inventory_geospatial.to_file(
        INVENTORY_GPKG, layer=INVENTORY_LAYER, driver="GPKG"
    )

    if AFFECTED_CELLS_GPKG.exists():
        AFFECTED_CELLS_GPKG.unlink()
    affected_cells.to_file(
        AFFECTED_CELLS_GPKG,
        layer=AFFECTED_CELLS_LAYER,
        driver="GPKG",
    )
    write_documentation()

    temporal_counts = {
        temporal_type: int(
            (inventory["temporal_type"] == temporal_type).sum()
        )
        for temporal_type in sorted(TEMPORAL_TYPES)
    }
    duplicates = duplicate_summary(inventory)
    eligible_before = set(
        static_features.loc[static_features["model_eligible"].astype(bool), "cell_id"]
    )
    eligible_after = set(
        labelled_features.loc[
            labelled_features["model_eligible"].astype(bool), "cell_id"
        ]
    )
    source_hash_after = sha256(SOURCE_PDF)
    require(
        source_hash_before == source_hash_after,
        "The source PDF changed while the pipeline was running",
    )

    report = {
        "source": {
            "path": str(SOURCE_PDF),
            "sha256_before": source_hash_before,
            "sha256_after": source_hash_after,
            "source_unchanged": True,
            "pdf_pages_processed": [min(SIKKIM_PDF_PAGES), max(SIKKIM_PDF_PAGES)],
        },
        "inventory": {
            "total_rows": int(len(inventory)),
            "unique_sl_no_count": int(inventory["sl_no"].nunique()),
            "unique_nonmissing_slide_no_count": duplicates["slide_no"][
                "unique_nonmissing_count"
            ],
            "valid_coordinate_rows": int(valid_coordinates.sum()),
            "mapped_coordinate_rows": int(mapped.sum()),
            "outside_grid_record_count": int(len(outside_grid_sl_nos)),
            "outside_grid_sl_nos": outside_grid_sl_nos,
            "multiple_grid_match_count": int(len(multiple_grid_matches)),
            "multiple_grid_matches": multiple_grid_matches,
        },
        "temporal_quality_counts": temporal_counts,
        "dated_event_rows": int(len(dated_events)),
        "grid_labels": {
            "total_grid_cells": int(len(grid)),
            "affected_cells": int(len(affected_cells)),
            "maximum_records_in_one_cell": int(
                affected_cells["inventory_record_count"].max()
            ),
            "inventory_record_count_sum": int(
                affected_cells["inventory_record_count"].sum()
            ),
        },
        "duplicates": duplicates,
        "static_features": {
            "input_rows": int(len(static_features)),
            "output_rows": int(len(labelled_features)),
            "model_eligible_input_cells": int(len(eligible_before)),
            "model_eligible_output_cells": int(len(eligible_after)),
            "all_model_eligible_cells_preserved": eligible_before == eligible_after,
            "label_zero_semantics": (
                "not present in the available GSI inventory; not confirmed "
                "landslide-free"
            ),
            "inventory_record_count_semantics": (
                "inventory row count only; not true landslide frequency"
            ),
        },
        "reference_expectations": {
            "expected_inventory_rows": EXPECTED_REFERENCE_ROWS,
            "actual_inventory_rows": int(len(inventory)),
            "inventory_row_discrepancy": int(
                len(inventory) - EXPECTED_REFERENCE_ROWS
            ),
            "expected_affected_cells": EXPECTED_REFERENCE_AFFECTED_CELLS,
            "actual_affected_cells": int(len(affected_cells)),
            "affected_cell_discrepancy": int(
                len(affected_cells) - EXPECTED_REFERENCE_AFFECTED_CELLS
            ),
        },
    }

    # Re-open every final artifact before declaring success.
    inventory_check = pd.read_csv(INVENTORY_CSV, keep_default_na=False)
    dated_check = pd.read_csv(DATED_EVENTS_CSV, keep_default_na=False)
    affected_check = pd.read_csv(AFFECTED_CELLS_CSV)
    labelled_check = pd.read_csv(LABELLED_FEATURES_CSV)
    inventory_spatial_check = gpd.read_file(
        INVENTORY_GPKG, layer=INVENTORY_LAYER
    )
    affected_spatial_check = gpd.read_file(
        AFFECTED_CELLS_GPKG, layer=AFFECTED_CELLS_LAYER
    )
    require(len(inventory_check) == len(inventory), "Inventory CSV row mismatch")
    require(len(dated_check) == len(dated_events), "Dated-event CSV row mismatch")
    require(len(affected_check) == len(affected_cells), "Affected CSV row mismatch")
    require(
        len(labelled_check) == len(static_features),
        "Labelled static-feature row mismatch",
    )
    require(
        len(inventory_spatial_check) == len(inventory),
        "Inventory GPKG row mismatch",
    )
    require(
        inventory_spatial_check.crs.to_epsg() == 4326,
        "Inventory GPKG is not EPSG:4326",
    )
    require(
        len(affected_spatial_check) == len(affected_cells),
        "Affected-cell GPKG row mismatch",
    )
    require(
        affected_spatial_check.crs == grid.crs,
        "Affected-cell GPKG does not preserve the grid CRS",
    )
    require(
        dated_check["event_date"].ne("").all(),
        "Dated-event subset contains an empty event_date",
    )
    require(
        set(dated_check["temporal_type"]) == {"exact_date"},
        "Dated-event subset contains a non-exact temporal type",
    )
    require(
        int(affected_check["inventory_record_count"].sum()) == int(mapped.sum()),
        "Affected-cell record counts do not reconcile to mapped inventory rows",
    )
    require(
        labelled_check["historically_affected"].isin([0, 1]).all(),
        "Static labels are not binary",
    )
    require(
        (
            labelled_check["historically_affected"]
            == labelled_check["inventory_record_count"].gt(0).astype("int64")
        ).all(),
        "Static labels and inventory counts disagree",
    )
    require(
        report["reference_expectations"]["inventory_row_discrepancy"] == 0,
        "Extracted inventory count differs from the validated reference",
    )
    require(
        report["reference_expectations"]["affected_cell_discrepancy"] == 0,
        "Affected-cell count differs from the validated reference",
    )

    VALIDATION_REPORT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    for output in [
        INVENTORY_CSV,
        INVENTORY_GPKG,
        DATED_EVENTS_CSV,
        AFFECTED_CELLS_CSV,
        AFFECTED_CELLS_GPKG,
        LABELLED_FEATURES_CSV,
        VALIDATION_REPORT,
        DOCUMENTATION_PATH,
    ]:
        print(f"Created: {output}")


if __name__ == "__main__":
    main()
