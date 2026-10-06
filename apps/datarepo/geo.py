import json

MAX_GEOJSON_BYTES = 10 * 1024 * 1024
GEOJSON_TYPES = {
    "FeatureCollection",
    "Feature",
    "GeometryCollection",
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
}


class GeoJSONError(Exception):
    """The stored file isn't valid GeoJSON."""


class GeoJSONTooLarge(Exception):
    """The stored file is bigger than the map preview will serve."""


def load_geojson(dataset):
    with dataset.file.open("rb") as stream:
        raw = stream.read(MAX_GEOJSON_BYTES + 1)
    if len(raw) > MAX_GEOJSON_BYTES:
        raise GeoJSONTooLarge
    try:
        data = json.loads(raw)
    except ValueError as exc:  # JSONDecodeError and UnicodeDecodeError are both ValueErrors
        raise GeoJSONError("The GeoJSON file could not be read.") from exc
    if not isinstance(data, dict) or data.get("type") not in GEOJSON_TYPES:
        raise GeoJSONError("The file is JSON but not GeoJSON.")
    return data
