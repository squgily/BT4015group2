"""Nursery-fee lookup for childcare centres (Daryl's ``scripts/join_childcare_fees.py``, moved here
2026-11-10 so notebooks can import it; the matching logic is unchanged).

The ECDA fee table (``data/ListingofCentreServices.csv``) has one row per centre, age level,
service type and citizenship. The team's fee variable, ``FULL_DAY_SC_NURSERY_FEE``, is the
Nursery (4 years old) Full Day fee for Singapore citizens. A centre gets a fee only when its
rows for that level agree on a single most common value (``unique_mode``); otherwise it is left
missing rather than guessed.

Two ways to attach the fee:

* by ``centre_code`` (the 2026 layer, notebook 1_05): ``load_fee_records`` gives one
  ``FeeRecord`` per centre with a usable fee;
* by name (the legacy 2021 GeoJSON, which has no centre code): ``NameMatcher`` matches a centre
  name to the fee table with exact, core-name, conservative fuzzy and partial-name rules, using
  the postal code to break ties. ``write_fees_preserving_layout`` writes the result back into the
  line-formatted GeoJSON without reformatting it.
"""

from __future__ import annotations

import csv
import difflib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


BENCHMARK_LEVEL = "Nursery (4 yrs old)"
FEE_PROPERTY = "FULL_DAY_SC_NURSERY_FEE"
LEGACY_FEE_PROPERTY = "FULL_DAY_SC_FEE"
# Generic words that carry no location information when comparing centre names.
LOCATION_STOPWORDS = {
    "AND", "AT", "CARE", "CENTRE", "CHILD", "CHILDCARE", "DEVELOPMENT", "EDUCATION",
    "KINDERGARTEN", "LEARNING", "LIMITED", "LTD", "PRESCHOOL", "PRIVATE", "PTE", "SCHOOL", "THE",
}


@dataclass(frozen=True)
class FeeRecord:
    """One centre with a usable Nursery Full Day/SC fee."""

    centre_code: str
    centre_name: str
    postal_code: str
    fee: int | float


def normalize_name(value: str) -> str:
    """Normalize harmless spelling/formatting differences in centre names.

    Upper-cases, strips accents, spells out ``&`` and ``@``, unifies PRE-SCHOOL / CHILD CARE /
    PTE. LTD. and collapses everything that is not a letter or digit to a single space.
    """
    text = (
        unicodedata.normalize("NFKD", value or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .upper()
    )
    text = text.replace("&", " AND ").replace("@", " AT ")
    text = re.sub(r"\bPRE\s*[- ]?SCHOOL\b", "PRESCHOOL", text)
    text = re.sub(r"\bCHILD\s*CARE\b", "CHILDCARE", text)
    text = re.sub(r"\bPTE\.?\s*LTD\.?\b", "PTE LTD", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return " ".join(text.split())


def core_name(value: str) -> str:
    """Return a normalized name without legal-entity suffixes (PTE LTD, LIMITED, LLP ...)."""
    text = normalize_name(value)
    text = re.sub(
        r"\b(PRIVATE LIMITED|PTE LTD|PTE LIMITED|LIMITED|LTD|LLP)\b",
        " ",
        text,
    )
    return " ".join(text.split())


def numeric_tokens(value: str) -> tuple[str, ...]:
    """The digit groups in a name (block numbers), which must agree for two names to match."""
    return tuple(re.findall(r"\d+", normalize_name(value)))


def trigrams(value: str) -> set[str]:
    """Character trigrams of a padded string, for the fuzzy candidate index."""
    padded = f"  {value}  "
    return {padded[index : index + 3] for index in range(len(padded) - 2)}


def parse_fee(value: str) -> int | float:
    """Parse a fee string, returning an int when the amount is whole dollars."""
    amount = Decimal(value.strip())
    return int(amount) if amount == amount.to_integral_value() else float(amount)


def unique_mode(values: list[str]) -> int | float | None:
    """The most common fee, or None when the list is empty or the top two values tie."""
    counts = Counter(values)
    if not counts:
        return None
    ranked = counts.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    return parse_fee(ranked[0][0])


def load_fee_records(fees_path: Path, attributes_path: Path) -> list[FeeRecord]:
    """Read the ECDA fee table and return one ``FeeRecord`` per centre with a unique Nursery fee.

    Keeps the rows for ``BENCHMARK_LEVEL`` with service type "Full Day" and citizenship "SC",
    takes the unique mode of each centre's fees (centres whose rows conflict are dropped) and
    attaches the postal code from the centre attributes file, which the name matcher uses to
    break ties.
    """
    with fees_path.open(encoding="utf-8-sig", newline="") as handle:
        filtered = [
            row
            for row in csv.DictReader(handle)
            if row["type_of_service"].strip().casefold() == "full day"
            and row["type_of_citizenship"].strip().casefold() == "sc"
            and row["levels_offered"].strip() == BENCHMARK_LEVEL
        ]

    rows_by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in filtered:
        rows_by_code[row["centre_code"]].append(row)

    with attributes_path.open(encoding="utf-8-sig", newline="") as handle:
        attributes_by_code = {
            row["centre_code"]: row for row in csv.DictReader(handle)
        }

    records: list[FeeRecord] = []
    for centre_code, rows in rows_by_code.items():
        fee = unique_mode([row["fees"] for row in rows])
        if fee is None:
            continue

        attributes = attributes_by_code.get(centre_code, {})
        records.append(
            FeeRecord(
                centre_code=centre_code,
                centre_name=rows[0]["centre_name"].strip(),
                postal_code=attributes.get("postal_code", "").strip(),
                fee=fee,
            )
        )
    return records


class NameMatcher:
    """Match a centre name (plus postal code and address) to the fee records.

    Rules are tried in order: normalized exact name, core name (legal suffixes removed),
    conservative fuzzy match (trigram Jaccard + sequence ratio with strict thresholds), then a
    partial-name match that needs location evidence from the address. A match that leaves
    several different fees is resolved by postal code or reported as ``ambiguous``.
    """

    def __init__(self, records: list[FeeRecord]) -> None:
        self.by_name: dict[str, list[FeeRecord]] = defaultdict(list)
        self.by_core: dict[str, list[FeeRecord]] = defaultdict(list)
        for record in records:
            self.by_name[normalize_name(record.centre_name)].append(record)
            self.by_core[core_name(record.centre_name)].append(record)

        self.name_keys = list(self.by_name)
        self.key_cores = [core_name(key) for key in self.name_keys]
        self.key_trigrams = [trigrams(value) for value in self.key_cores]
        self.trigram_index: dict[str, list[int]] = defaultdict(list)
        for index, grams in enumerate(self.key_trigrams):
            for gram in grams:
                self.trigram_index[gram].append(index)

    @staticmethod
    def resolve_group(
        candidates: list[FeeRecord], postal_code: str
    ) -> tuple[int | float | None, bool]:
        """Reduce a group of matched records to one fee, using the postal code to break ties."""
        fees = {candidate.fee for candidate in candidates}
        used_postal = False
        if len(fees) > 1 and postal_code:
            postal_candidates = [
                candidate
                for candidate in candidates
                if candidate.postal_code == postal_code
            ]
            if postal_candidates:
                candidates = postal_candidates
                fees = {candidate.fee for candidate in candidates}
                used_postal = True
        return (next(iter(fees)), used_postal) if len(fees) == 1 else (None, used_postal)

    def fuzzy_group(
        self, name: str, postal_code: str
    ) -> list[FeeRecord] | None:
        """Conservative fuzzy match: same block numbers, high trigram and sequence similarity,
        and a clear margin over the runner-up (or a postal-code match with sequence >= 0.82)."""
        query_core = core_name(name)
        query_numbers = numeric_tokens(name)
        query_grams = trigrams(query_core)
        overlaps: Counter[int] = Counter()
        for gram in query_grams:
            overlaps.update(self.trigram_index.get(gram, ()))

        scored: list[tuple[float, float, bool, int]] = []
        candidate_indexes = sorted(
            overlaps, key=lambda index: (-overlaps[index], index)
        )[:30]
        for index in candidate_indexes:
            overlap = overlaps[index]
            candidate_name = self.name_keys[index]
            if numeric_tokens(candidate_name) != query_numbers:
                continue
            candidate_grams = self.key_trigrams[index]
            jaccard = overlap / len(query_grams | candidate_grams)
            sequence = difflib.SequenceMatcher(
                None, query_core, self.key_cores[index]
            ).ratio()
            score = 0.45 * jaccard + 0.55 * sequence
            postal_match = bool(postal_code) and any(
                record.postal_code == postal_code
                for record in self.by_name[candidate_name]
            )
            scored.append((score, sequence, postal_match, index))

        scored.sort(reverse=True)
        if not scored:
            return None
        postal_scored = [item for item in scored if item[2]]
        if postal_scored and postal_scored[0][1] >= 0.82:
            return self.by_name[self.name_keys[postal_scored[0][3]]]

        best_score, best_sequence, _, best_index = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        if (
            best_score < 0.90
            or best_sequence < 0.94
            or best_score - runner_up < 0.05
        ):
            return None
        return self.by_name[self.name_keys[best_index]]

    def partial_name_address_group(
        self, name: str, postal_code: str, address: str
    ) -> list[FeeRecord] | None:
        """Match a shorter legacy name using location evidence in its address."""
        query_core = core_name(name)
        query_tokens = set(query_core.split())
        address_tokens = set(normalize_name(address).split())
        if len(query_tokens) < 2:
            return None

        scored: list[tuple[bool, int, float, float, int]] = []
        for index, candidate_core in enumerate(self.key_cores):
            candidate_tokens = set(candidate_core.split())
            if not query_tokens.issubset(candidate_tokens):
                continue
            if numeric_tokens(name) != numeric_tokens(candidate_core):
                continue

            extra_tokens = candidate_tokens - query_tokens - LOCATION_STOPWORDS
            location_hits = extra_tokens & address_tokens
            candidate_group = self.by_name[self.name_keys[index]]
            postal_match = bool(postal_code) and any(
                record.postal_code == postal_code for record in candidate_group
            )
            overlap_ratio = len(query_tokens) / len(candidate_tokens)
            if not location_hits and not (postal_match and overlap_ratio >= 0.8):
                continue

            sequence = difflib.SequenceMatcher(
                None, query_core, candidate_core
            ).ratio()
            scored.append(
                (
                    postal_match,
                    len(location_hits),
                    overlap_ratio,
                    sequence,
                    index,
                )
            )

        if not scored:
            return None
        scored.sort(reverse=True)
        best = scored[0]
        if len(scored) > 1 and best[:4] == scored[1][:4]:
            return None
        return self.by_name[self.name_keys[best[4]]]

    def match(
        self, name: str, postal_code: str, address: str = ""
    ) -> tuple[int | float | None, str]:
        """Return ``(fee, method)``; fee is None with method ``unmatched`` or ``ambiguous``."""
        normalized = normalize_name(name)
        core = core_name(name)

        if normalized in self.by_name:
            candidates = self.by_name[normalized]
            method = "normalized_exact"
        elif core in self.by_core:
            candidates = self.by_core[core]
            method = "core_exact"
        else:
            candidates = self.fuzzy_group(name, postal_code)
            method = "conservative_fuzzy"

        if not candidates:
            candidates = self.partial_name_address_group(
                name, postal_code, address
            )
            method = "partial_name_address"

        if not candidates:
            return None, "unmatched"
        fee, used_postal = self.resolve_group(candidates, postal_code)
        if fee is None:
            return None, "ambiguous"
        if used_postal:
            method += "_postal_disambiguated"
        return fee, method


def write_fees_preserving_layout(
    geojson_path: Path, fees: list[int | float | None]
) -> None:
    """Add or replace the fee property in a line-formatted GeoJSON without reformatting it.

    Legacy step for ``data/ChildCareServices_2021.geojson``: ``fees`` has one entry per feature,
    in file order. Raises if the file is not line-formatted or the feature count differs.
    """
    raw = geojson_path.read_bytes()
    text = raw.decode("utf-8-sig")
    line_ending = "\r\n" if b"\r\n" in raw else "\n"
    final_newline = line_ending if raw.endswith((b"\n", b"\r")) else ""
    lines = text.splitlines()
    if len(lines) < len(fees):
        raise ValueError(
            "GeoJSON is not line-formatted; refusing to rewrite the whole file"
        )

    output: list[str] = []
    feature_index = 0
    in_properties = False
    fee_written = False
    for line in lines:
        stripped = line.strip()
        if stripped == '"properties" : {':
            in_properties = True
            fee_written = False

        if in_properties and (
            f'"{FEE_PROPERTY}"' in stripped
            or f'"{LEGACY_FEE_PROPERTY}"' in stripped
        ):
            indent = line[: len(line) - len(line.lstrip())]
            trailing_comma = "," if stripped.endswith(",") else ""
            output.append(
                f'{indent}"{FEE_PROPERTY}" : '
                f'{json.dumps(fees[feature_index], ensure_ascii=False)}'
                f"{trailing_comma}"
            )
            fee_written = True
            continue

        if in_properties and stripped == "}":
            if not fee_written:
                previous = len(output) - 1
                while previous >= 0 and not output[previous].strip():
                    previous -= 1
                if previous < 0:
                    raise ValueError("Empty GeoJSON properties object")
                indent = output[previous][
                    : len(output[previous]) - len(output[previous].lstrip())
                ]
                tail = output[previous:]
                del output[previous:]
                output.append(
                    f'{indent}"{FEE_PROPERTY}" : '
                    f'{json.dumps(fees[feature_index], ensure_ascii=False)},'
                )
                output.extend(tail)
            feature_index += 1
            in_properties = False

        output.append(line)

    if feature_index != len(fees):
        raise ValueError(
            f"Expected {len(fees)} property objects, found {feature_index}"
        )
    with geojson_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(line_ending.join(output) + final_newline)
