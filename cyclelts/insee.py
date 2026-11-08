"""Step 2 - commuting mode shares of a commune from the INSEE census (tables NAV2A).

INSEE (the French national statistics institute) publishes, for every census
year, the number of employed people living in each commune by the **main mode
of transport used to go to work** (table *NAV2A*). From these counts we compute
the share (%) of each mode.

The transport categories changed in 2017:

=========  ==========================  ==========================
code       2006-2016                   2017-2022
=========  ==========================  ==========================
1          no transport                no transport
2          walking                     walking
3          two-wheelers (bike + moto)  **bicycle**
4          car                         motorised two-wheelers
5          public transport            car
6          -                           public transport
=========  ==========================  ==========================

To have one comparable series over 2006-2022 the column ``Deux-roues total``
(= bicycle + motorised two-wheelers from 2017) is used as the dependent
variable of the model. ``Vélo`` (bicycle only) exists only from 2017.

Output columns (French names kept, as in INSEE): ``Year, CODGEO, Commune,
Pas de déplacement, Marche, Deux-roues total, Vélo, Deux-roues motorisé,
Voiture, TC`` - all in percent of the employed population.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

MODE_COLUMNS = ["Pas de déplacement", "Marche", "Deux-roues total", "Vélo",
                "Deux-roues motorisé", "Voiture", "TC"]

#: English names, for plots
MODE_LABELS_EN = {
    "Pas de déplacement": "No transport (works at home)",
    "Marche": "Walking",
    "Deux-roues total": "Two-wheelers (bike + motorbike)",
    "Vélo": "Bicycle",
    "Deux-roues motorisé": "Motorised two-wheelers",
    "Voiture": "Car",
    "TC": "Public transport",
}


def extract_year_from_path(file_path, valid_years):
    """Data year of a NAV2A file, read from its path (last valid year found)."""
    matches = re.findall(r"(20\d{2})", str(file_path))
    valid = [int(m) for m in matches if int(m) in valid_years]
    return valid[-1] if valid else None


def find_header_row_excel(file_path, sheet_name):
    """Row where the real table starts (the one containing ``CODGEO``)."""
    preview = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=60)
    for i in range(len(preview)):
        row_values = preview.iloc[i].astype(str).str.strip().tolist()
        if "CODGEO" in row_values:
            return i
    raise ValueError(f"Could not find CODGEO header row in {file_path.name}")


def get_commune_sheet_name(file_path):
    """Name of the commune-level sheet (usually ``COM``)."""
    xls = pd.ExcelFile(file_path)
    if "COM" in xls.sheet_names:
        return "COM"
    possible = [s for s in xls.sheet_names if "COM" in s.upper()]
    return possible[0] if possible else xls.sheet_names[0]


def get_transport_mode_from_column(col):
    """Transport-mode code (``"1"``..``"6"``) of a NAV2A column, or None.

    Old format, 2006-2016: ``ILTR1_SEXE1_TRANS1*POP2011``, ...
    New format, 2017-2022: ``ILTR1_SEXE1_TRANS_191`` ... ``TRANS_196``.
    """
    col_str = str(col).upper().replace(" ", "")
    match_new = re.search(r"TRANS_19([1-6])", col_str)
    if match_new:
        return match_new.group(1)
    match_old = re.search(r"TRANS_?([1-6])(?=\D|$)", col_str)
    if match_old:
        return match_old.group(1)
    return None


def score_candidate_file(file_path, year):
    """Preference score when several files exist for one year."""
    score = 0
    if file_path.parent.name == f"NAV2A_{year}":
        score += 30          # file inside its NAV2A_<year> folder
    if file_path.suffix.lower() == ".xlsx":
        score += 10          # prefer xlsx
    if "NAV2A" in file_path.name.upper():
        score += 5
    return score


def find_nav2a_files(base_dir, years_wanted):
    """``{year: path}`` - one NAV2A Excel file per year, searched in all sub-folders."""
    excel_files = []
    for p in Path(base_dir).rglob("*"):
        if p.suffix.lower() not in [".xls", ".xlsx"] or p.name.startswith("~$"):
            continue
        year = extract_year_from_path(p, years_wanted)
        if year is not None:
            excel_files.append((year, p))
    files_by_year = {}
    for year, file_path in excel_files:
        if year not in files_by_year or score_candidate_file(file_path, year) > score_candidate_file(files_by_year[year], year):
            files_by_year[year] = file_path
    return files_by_year


def read_nav2a_table(file_path):
    """Commune-level sheet of one NAV2A file as a DataFrame (``CODGEO`` as 5-digit text)."""
    file_path = Path(file_path)
    sheet_name = get_commune_sheet_name(file_path)
    header_row = find_header_row_excel(file_path, sheet_name)
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row, dtype={"CODGEO": str})
    df["CODGEO"] = df["CODGEO"].astype(str).str.zfill(5)
    return df


def read_nav2a_commune(file_path, codgeo, year, table=None):
    """Mode shares (%) of one commune from one NAV2A file (see module docstring).

    ``table`` - the already loaded sheet (:func:`read_nav2a_table`), to avoid
    reading the same large Excel file once per city.
    """
    file_path = Path(file_path)
    year = int(year)
    codgeo = str(codgeo).zfill(5)
    df = read_nav2a_table(file_path) if table is None else table
    row_df = df[df["CODGEO"] == codgeo]
    if row_df.empty:
        raise ValueError(f"CODGEO {codgeo} not found in {file_path.name}")
    row = row_df.iloc[0]
    commune_name = row["LIBGEO"] if "LIBGEO" in df.columns else ""

    # Sum every column (sex x place of work x ...) of each transport mode
    mode_totals = {str(i): 0.0 for i in range(1, 7)}
    for col in df.columns:
        mode = get_transport_mode_from_column(col)
        if mode is None:
            continue
        value = row[col]
        if isinstance(value, str):
            value = value.replace(",", ".")
        value = pd.to_numeric(value, errors="coerce")
        if pd.notna(value):
            mode_totals[mode] += value

    if year <= 2016:   # old classification
        counts = {
            "Pas de déplacement": mode_totals["1"], "Marche": mode_totals["2"],
            "Deux-roues total": mode_totals["3"], "Vélo": np.nan, "Deux-roues motorisé": np.nan,
            "Voiture": mode_totals["4"], "TC": mode_totals["5"],
        }
    else:              # new classification, 2017-2022
        counts = {
            "Pas de déplacement": mode_totals["1"], "Marche": mode_totals["2"],
            "Vélo": mode_totals["3"], "Deux-roues motorisé": mode_totals["4"],
            "Deux-roues total": mode_totals["3"] + mode_totals["4"],
            "Voiture": mode_totals["5"], "TC": mode_totals["6"],
        }
    total = (counts["Pas de déplacement"] + counts["Marche"] + counts["Deux-roues total"]
             + counts["Voiture"] + counts["TC"])
    if total == 0:
        raise ValueError(f"No modal values found in {file_path.name}: {mode_totals}")
    shares = {mode: 100 * value / total if pd.notna(value) else np.nan for mode, value in counts.items()}
    shares["Year"] = year
    shares["CODGEO"] = codgeo
    shares["Commune"] = commune_name
    return shares


def modal_shares_for_communes(codgeos, base_dir, years=range(2006, 2023), verbose=True):
    """``{codgeo: table of yearly mode shares (%)}`` for several communes.

    Each yearly Excel file is read only once for all communes.
    """
    years = list(years)
    files_by_year = find_nav2a_files(base_dir, years)
    results = {str(c).zfill(5): [] for c in codgeos}
    for year in years:
        if year not in files_by_year:
            if verbose:
                print(f"{year}: missing file")
            continue
        table = read_nav2a_table(files_by_year[year])
        for codgeo in results:
            try:
                results[codgeo].append(read_nav2a_commune(files_by_year[year], codgeo, year, table=table))
            except Exception as e:  # keep going: one bad year must not stop the city
                print(f"{year} {codgeo}: ERROR -> {e}")
        if verbose:
            print(f"{year}: read {files_by_year[year].name}")
    out = {}
    for codgeo, rows in results.items():
        frame = pd.DataFrame(rows).sort_values("Year")
        out[codgeo] = frame[["Year", "CODGEO", "Commune", *MODE_COLUMNS]].reset_index(drop=True)
    return out


def modal_shares_for_commune(codgeo, base_dir, years=range(2006, 2023), verbose=True):
    """Table of yearly mode shares (%) of one commune ``codgeo``."""
    return modal_shares_for_communes([codgeo], base_dir, years, verbose)[str(codgeo).zfill(5)]


def modal_share_file(folder, slug, codgeo):
    """``<folder>/<slug>_<codgeo>_modal_shares_2006_2022.csv``."""
    return Path(folder) / f"{slug}_{codgeo}_modal_shares_2006_2022.csv"


def read_modal_shares(folder, slug):
    """Read the mode-share CSV of a city written by :func:`modal_shares_for_commune`."""
    found = sorted(Path(folder).glob(f"{slug}_[0-9]*_modal_shares_*.csv"))
    if not found:
        raise FileNotFoundError(f"No modal-share CSV for {slug!r} in {folder}")
    return pd.read_csv(found[0], encoding="utf-8-sig")
