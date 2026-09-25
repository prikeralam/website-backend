import csv
import io
import zipfile
from itertools import islice

import pyarrow.parquet as pq


class PreviewError(Exception):
    """The stored file can't be previewed (corrupt, or no readable table inside)."""


class UnsupportedFormat(Exception):
    """No table previewer exists for the dataset's format."""


def _csv_page(stream, start, page_size):
    reader = csv.reader(io.TextIOWrapper(stream, encoding="utf-8"))
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


def _zip_page(stream, start, page_size):
    try:
        archive = zipfile.ZipFile(stream)
    except zipfile.BadZipFile as exc:
        raise PreviewError("The zip file could not be read.") from exc
    member = next(
        (
            info
            for info in archive.infolist()
            if not info.is_dir()
            and info.filename.lower().endswith(".csv")
            and not info.filename.startswith("__MACOSX/")
        ),
        None,
    )
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
