import re
import logging
from typing import Dict, Any, List, Tuple, Optional
import defusedxml.ElementTree as ET
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, GeometryCollection, mapping
from shapely.geometry.base import BaseGeometry

logger = logging.getLogger(__name__)

class KMLParsingError(Exception):
    pass

class KMLParser:
    """Parses OGC KML files into geometries, attributes, and WGS84 CRS."""

    STANDARD_KML_CRS = "EPSG:4326"

    @staticmethod
    def _strip_ns(tag: str) -> str:
        if '}' in tag:
            return tag.split('}', 1)[1]
        return tag

    @classmethod
    def _find_elem(cls, root: ET.Element, path_with_ns: str, path_no_ns: str) -> Optional[ET.Element]:
        """Safely finds an XML element without relying on truthiness."""
        el = root.find(path_with_ns)
        if el is not None:
            return el
        return root.find(path_no_ns)

    @classmethod
    def _parse_coordinates(cls, coord_text: str) -> List[Tuple[float, float]]:
        """Parses KML coordinate string 'lon,lat,alt lon,lat,alt ...' into [(lon, lat), ...]."""
        coords = []
        if not coord_text:
            return coords
        # Split by whitespace or newlines
        tokens = re.split(r'\s+', coord_text.strip())
        for token in tokens:
            if not token:
                continue
            parts = token.split(',')
            if len(parts) >= 2:
                try:
                    lon = float(parts[0].strip())
                    lat = float(parts[1].strip())
                    coords.append((lon, lat))
                except ValueError:
                    continue
        return coords

    @classmethod
    def _extract_geometry(cls, elem: ET.Element) -> Optional[BaseGeometry]:
        """Recursively parses XML geometry elements into Shapely geometry."""
        tag = cls._strip_ns(elem.tag)

        if tag == "Point":
            coord_elem = cls._find_elem(elem, ".//{*}coordinates", ".//coordinates")
            if coord_elem is not None and coord_elem.text:
                coords = cls._parse_coordinates(coord_elem.text)
                if coords:
                    return Point(coords[0])

        elif tag == "LineString":
            coord_elem = cls._find_elem(elem, ".//{*}coordinates", ".//coordinates")
            if coord_elem is not None and coord_elem.text:
                coords = cls._parse_coordinates(coord_elem.text)
                if len(coords) >= 2:
                    return LineString(coords)

        elif tag == "Polygon":
            outer_ring = None
            outer_elem = cls._find_elem(elem, ".//{*}outerBoundaryIs//{*}coordinates", ".//outerBoundaryIs//coordinates")
            if outer_elem is not None and outer_elem.text:
                outer_coords = cls._parse_coordinates(outer_elem.text)
                if len(outer_coords) >= 3:
                    outer_ring = outer_coords

            if not outer_ring:
                return None

            inner_rings = []
            inner_elems = elem.findall(".//{*}innerBoundaryIs//{*}coordinates") or elem.findall(".//innerBoundaryIs//coordinates")
            for in_el in inner_elems:
                if in_el is not None and in_el.text:
                    in_coords = cls._parse_coordinates(in_el.text)
                    if len(in_coords) >= 3:
                        inner_rings.append(in_coords)

            return Polygon(outer_ring, inner_rings)

        elif tag == "MultiGeometry":
            sub_geoms = []
            for child in elem:
                sub = cls._extract_geometry(child)
                if sub is not None and not sub.is_empty:
                    sub_geoms.append(sub)
            if not sub_geoms:
                return None
            if all(isinstance(g, Polygon) for g in sub_geoms):
                return MultiPolygon(sub_geoms)
            return GeometryCollection(sub_geoms)

        # Fallback inspection for nested geometries
        for child in elem:
            res = cls._extract_geometry(child)
            if res is not None:
                return res

        return None

    @classmethod
    def parse_kml_bytes(cls, kml_bytes: bytes) -> Tuple[List[Dict[str, Any]], str, Tuple[float, float, float, float]]:
        """Parses KML raw bytes.
        
        Returns:
            Tuple of:
                - List of feature dicts
                - Source CRS string ("EPSG:4326")
                - Bounding box (minx, miny, maxx, maxy)
        """
        try:
            root = ET.fromstring(kml_bytes)
        except Exception as e:
            raise KMLParsingError(f"Invalid or corrupted KML XML content: {str(e)}")

        features = []
        all_minx, all_miny, all_maxx, all_maxy = float('inf'), float('inf'), float('-inf'), float('-inf')

        placemarks = root.findall(".//{*}Placemark")
        if not placemarks:
            placemarks = [el for el in root.iter() if cls._strip_ns(el.tag) == "Placemark"]

        for idx, pm in enumerate(placemarks):
            properties = {}
            for child in pm:
                ch_tag = cls._strip_ns(child.tag)
                if ch_tag in ["name", "description", "styleUrl"]:
                    if child.text:
                        properties[ch_tag] = child.text.strip()
                elif ch_tag == "ExtendedData":
                    for d in child.iter():
                        d_tag = cls._strip_ns(d.tag)
                        if d_tag == "Data":
                            name_attr = d.get("name")
                            val_elem = cls._find_elem(d, ".//{*}value", ".//value")
                            if name_attr and val_elem is not None and val_elem.text:
                                properties[name_attr] = val_elem.text.strip()
                        elif d_tag == "SimpleData":
                            name_attr = d.get("name")
                            if name_attr and d.text:
                                properties[name_attr] = d.text.strip()

            geom = None
            for child in pm:
                ch_tag = cls._strip_ns(child.tag)
                if ch_tag in ["Point", "LineString", "Polygon", "MultiGeometry"]:
                    geom = cls._extract_geometry(child)
                    if geom is not None:
                        break

            if geom is not None and not geom.is_empty:
                minx, miny, maxx, maxy = geom.bounds
                all_minx = min(all_minx, minx)
                all_miny = min(all_miny, miny)
                all_maxx = max(all_maxx, maxx)
                all_maxy = max(all_maxy, maxy)

            features.append({
                "feature_index": idx,
                "feature_id": properties.get("name", f"kml_{idx}"),
                "geometry_type": geom.geom_type if geom else "Unknown",
                "geometry": mapping(geom) if geom else None,
                "shapely_geom": geom,
                "properties": properties
            })

        bounds = (all_minx, all_miny, all_maxx, all_maxy) if all_minx != float('inf') else (0.0, 0.0, 0.0, 0.0)
        return features, cls.STANDARD_KML_CRS, bounds

kml_parser = KMLParser()
