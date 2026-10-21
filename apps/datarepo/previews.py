import csv
import io
import zipfile
from itertools import islice

import pyarrow.parquet as pq


class PreviewError(Exception):
    """The stored file can't be previewed (corrupt, or no readable table inside)."""


class UnsupportedFormat(Exception):
    """No table previewer exists for the dataset's format."""


# utf-8-sig drops the byte-order mark Excel and pri-data put at the start of a UTF-8 CSV (so Malayalam opens correctly
# in Excel); without it the first column name would start with "﻿". Files without a BOM read the same.
CSV_ENCODING = "utf-8-sig"


def _csv_page(stream, start, page_size):
    reader = csv.reader(io.TextIOWrapper(stream, encoding=CSV_ENCODING))
    try:
        header = next(reader, [])
        return header, list(islice(reader, start, start + page_size))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise PreviewError("The CSV file could not be read.") from exc


def _json_safe(value):
    return value if value is None or isinstance(value, (str, int, float, bool)) else str(value)


def _parquet_page(stream, start, page_size):
    try:
        parquet_file = pq.ParquetFile(stream)
        header = parquet_file.schema_arrow.names
        rows = []
        seen = 0
        for batch in parquet_file.iter_batches(batch_size=page_size):
            if seen + batch.num_rows > start:
                for row in batch.to_pylist()[max(0, start - seen) :]:
                    rows.append([_json_safe(row[name]) for name in header])
                    if len(rows) == page_size:
                        return header, rows
            seen += batch.num_rows
        return header, rows
    except (OSError, ValueError) as exc:  # pyarrow raises ArrowInvalid (ValueError) or IO errors (OSError)
        raise PreviewError("The parquet file could not be read.") from exc


def _first_csv(archive):
    """The first CSV file in a zip archive (macOS metadata folders skipped), or None."""
    return next(
        (
            info
            for info in archive.infolist()
            if not info.is_dir()
            and info.filename.lower().endswith(".csv")
            and not info.filename.startswith("__MACOSX/")
        ),
        None,
    )


def _zip_page(stream, start, page_size):
    try:
        archive = zipfile.ZipFile(stream)
    except zipfile.BadZipFile as exc:
        raise PreviewError("The zip file could not be read.") from exc
    member = _first_csv(archive)
    if member is None:
        raise PreviewError("The zip file contains no CSV file to preview.")
    with archive.open(member) as csv_stream:
        return _csv_page(csv_stream, start, page_size)


_PAGERS = {"csv": _csv_page, "parquet": _parquet_page, "zip": _zip_page}


def table_page(dataset, page, page_size):
    """Return (header, rows) for one page of the dataset's table.

    Raises PreviewError if the file can't be read, and UnsupportedFormat for a format with no previewer.
    """
    pager = _PAGERS.get(dataset.format)
    if pager is None:
        raise UnsupportedFormat(dataset.format)
    with dataset.file.open("rb") as stream:
        return pager(stream, (page - 1) * page_size, page_size)


def _count_csv(stream):
    reader = csv.reader(io.TextIOWrapper(stream, encoding=CSV_ENCODING))
    header = next(reader, [])
    return sum(1 for _ in reader), header


def profile_file(dataset):
    """(row_count, column names) for the dataset's file, or None when it can't be read.

    CSV, the first CSV in a ZIP, and Parquet count data rows; GeoJSON counts features and lists the property names
    in first-seen order.
    """
    try:
        if dataset.format == "parquet":
            with dataset.file.open("rb") as stream:
                parquet_file = pq.ParquetFile(stream)
                return parquet_file.metadata.num_rows, list(parquet_file.schema_arrow.names)
        if dataset.format == "geojson":
            from .geo import load_geojson

            data = load_geojson(dataset)
            features = data.get("features", []) if data.get("type") == "FeatureCollection" else [data]
            names = {}
            for feature in features:
                for key in (feature.get("properties") or {}) if isinstance(feature, dict) else {}:
                    names.setdefault(key, None)
            return len(features), list(names)
        with dataset.file.open("rb") as stream:
            if dataset.format == "zip":
                archive = zipfile.ZipFile(stream)
                member = _first_csv(archive)
                if member is None:
                    return None
                with archive.open(member) as csv_stream:
                    return _count_csv(csv_stream)
            if dataset.format == "csv":
                return _count_csv(stream)
    except Exception:  # noqa: BLE001 - a file we can't profile must never break saving the dataset
        return None
    return None
