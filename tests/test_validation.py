from shapely.geometry import Polygon, MultiPolygon, GeometryCollection, Point, LineString
import sys
sys.path.insert(0, "data-ingestion")
from utils import ensure_multipolygon
import pytest

def test_valid_polygon():
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    result = ensure_multipolygon(poly)
    assert isinstance(result, MultiPolygon)
    assert len(result.geoms) == 1

def test_invalid_polygon_bowtie():
    # Bowtie invalid polygon
    poly = Polygon([(0, 0), (0, 2), (2, 0), (2, 2), (0, 0)])
    assert not poly.is_valid
    result = ensure_multipolygon(poly)
    assert isinstance(result, MultiPolygon)
    assert result.is_valid

def test_extract_from_collection():
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    pt = Point(0.5, 0.5)
    gc = GeometryCollection([poly, pt])
    result = ensure_multipolygon(gc)
    assert isinstance(result, MultiPolygon)
    assert len(result.geoms) == 1

def test_ignore_lines_and_points():
    pt = Point(0.5, 0.5)
    line = LineString([(0, 0), (1, 1)])
    gc = GeometryCollection([pt, line])
    result = ensure_multipolygon(gc)
    assert result is None
