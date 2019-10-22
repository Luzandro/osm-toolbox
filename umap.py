#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import bev_db
import projection
from gkz import get_bezirk, get_bundesland
from geojson import Point, Feature, FeatureCollection, dump, Polygon
from streetnames import normalize_streetname

class Umap():
    def __init__(self):
        self.layers = {}
        self.properties = {
            "easing": True,
            "embedControl": True,
            "fullscreenControl": True,
            "searchControl": True,
            "datalayersControl": True,
            "zoomControl": True,
            "slideshow": {},
            "captionBar": True,
            "limitBounds": {},
            "tilelayer": {
                "tms": False,
                "name": "OSM Carto",
                "maxZoom": 18,
                "minZoom": 0,
                "attribution": "Map data © by Openstreetmap contributors, Map Style CC-BY-SA licence 2.0",
                "url_template": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            }
        }

    def add_feature(self, feature, layer, umap_options=None):
        if umap_options:
            feature["properties"]["_umap_options"] = umap_options
        if layer in self.layers:
            self.layers[layer]["features"].append(feature)
        else:
            self.layers[layer] = FeatureCollection([])
            self.layers[layer]["_umap_options"] = {
                "displayOnLoad": False,
                "browsable": True,
                "remoteData": {},
                "name": layer,
                "description": "",
                "type": "Default",
                "cluster": {}
            }
            self.layers[layer]["features"].append(feature)

    def get_dict(self):
        umap = {
            "type": "umap",
            "properties": self.properties,
            "layers": []
        }
        for layer in sorted(self.layers.keys(), reverse=True):
            umap["layers"].append(self.layers[layer])
        return umap
    
    def dump(self, filename):
        with open(filename, 'w') as f:
            dump(self.get_dict(), f, indent=2)

    def get_josm_link(self, min_lon, max_lon, min_lat, max_lat, area_size=None):
        if area_size is None:
            area_size = projection.get_area_size(min_lon, max_lon, min_lat, max_lat)
        if area_size < 40:
            josm_link = "[[http://localhost:8111/load_and_zoom?left=%s&bottom=%s&right=%s&top=%s|Adress-Bereich in JOSM laden]]" % (min_lon, min_lat, max_lon, max_lat)
        else:
            josm_link = "[[http://localhost:8111/zoom?left=%s&bottom=%s&right=%s&top=%s|zoom JOSM auf Adress-Bereich]]" % (min_lon, min_lat, max_lon, max_lat)
        return josm_link

def ignore_streetname(name):
    name = name.lower()
    for substring in ["parzelle", "klg ", "kga ", "bundesstrasse"]:
        if substring in name:
            return True
    return False

def generate_new_street_umap(number_of_snapshots=len(bev_db.SNAPSHOTS), include_found_objects=False, gkz_starts_with = ""):
    ids = {}
    skz_found = {}
    gkz_starts_with += "%"
    con = bev_db.get_db_conn() # always use newest db to check found status
    for skz, found in con.execute("SELECT SKZ, FOUND FROM STRASSE"):
        if found is None:
            skz_found[skz] = bev_db.SearchStatus.NOT_FOUND
        else:
            skz_found[skz] = found
    umap = Umap()
    number_of_streets = 0
    number_of_missing_streets = 0
    for (old, new) in zip(bev_db.SNAPSHOTS[-number_of_snapshots:], bev_db.SNAPSHOTS[-number_of_snapshots+1:]):
        print(old, new)
        if not old in ids:
            con = bev_db.get_db_conn(old)
            ids[old] = set()
            for row in con.execute("SELECT SKZ FROM STRASSE"):
                ids[old].add(row[0])
        con = bev_db.get_db_conn(new)
        if not new in ids:
            ids[new] = set()
            for row in con.execute("SELECT SKZ FROM STRASSE"):
                ids[new].add(row[0])
        new_ids = ids[new] - ids[old]
        cur = con.cursor()
        query = """SELECT GEMEINDE.GKZ, GEMEINDE.GEMEINDENAME, STRASSE.SKZ, STRASSE.STRASSENNAME, 
            COUNT(ADRESSE.ADRCD), MIN(LAT), MIN(LON), MAX(LAT), MAX(LON) 
            FROM STRASSE JOIN ADRESSE ON ADRESSE.SKZ = STRASSE.SKZ JOIN GEMEINDE ON GEMEINDE.GKZ = ADRESSE.GKZ 
            WHERE STRASSE.GKZ LIKE ? AND STRASSE.SKZ IN ({}) AND ADRESSE.HAUSNRZAHL1 != ""
            GROUP BY STRASSE.SKZ HAVING COUNT(ADRESSE.ADRCD) > 1 ORDER BY 1, 4 DESC""".format(",".join("?"*len(new_ids)))
        parameters = [gkz_starts_with] + list(new_ids)
        for row in cur.execute(query, parameters):
            gkz, gemeindename, skz, strassenname, count, min_lat, min_lon, max_lat, max_lon = row
            if ignore_streetname(strassenname):
                continue
            bezirkname = get_bezirk(gkz)
            bundesland = get_bundesland(gkz)
            layer = "%s: %s" % (bundesland, bezirkname)
            try:
                area_size = projection.get_area_size(min_lon, max_lon, min_lat, max_lat)
            except TypeError:
                continue
            try:
                adr_per_km2 = count / area_size
            except ZeroDivisionError:
                adr_per_km2 = 0            
            josm_link = umap.get_josm_link(min_lon, max_lon, min_lat, max_lat, area_size=area_size)
            properties={"name": "#%s %s (%s)" % (gkz[3:], strassenname, gemeindename),
                        "description": "%s\nNeu mit Stichtag %s\n%s Adressen\nSKZ %s\nGröße: %4.2f km²\nAdr./km²: %s" % (josm_link, bev_db.format_key_date(new), count, skz, area_size, int(adr_per_km2))
            }
            feature = Feature(properties=properties, 
                geometry=Polygon([[[min_lon, min_lat], [min_lon, max_lat], [max_lon, max_lat], [max_lon, min_lat]]])
            )
            if skz not in skz_found or skz_found[skz] != bev_db.SearchStatus.FOUND:
                if skz in skz_found and skz_found[skz] == bev_db.SearchStatus.UNDER_CONSTRUCTION:
                    umap.add_feature(feature, layer, {"color": "Orange"})
                else:
                    number_of_missing_streets += 1
                    umap.add_feature(feature, layer, {"color": "Red"})
            elif include_found_objects:
                umap.add_feature(feature, layer)
            number_of_streets += 1
    if gkz_starts_with == "":
        filename = "new_streets.umap"
    else:
        filename = "new_streets_%s.umap" % (gkz_starts_with)
    umap.dump(filename)
    print("%s/%s streets missing" % (number_of_missing_streets, number_of_streets))

def generate_renamed_street_umap(number_of_snapshots=2, include_found_objects=False, ignore_minor_changes=True):
    streets = {}
    for snapshot in bev_db.SNAPSHOTS[-number_of_snapshots:]:
        print(snapshot)
        con = bev_db.get_db_conn(snapshot)
        cur = con.cursor()
        sql = "SELECT s.SKZ, s.STRASSENNAME, g.GEMEINDENAME, g.GKZ FROM STRASSE s JOIN GEMEINDE g ON s.GKZ = g.GKZ"
        for row in cur.execute(sql):
            skz, name, gemeinde, gkz = row
            if skz in streets:
                if ignore_minor_changes:
                    if normalize_streetname(streets[skz][-1][0]) != normalize_streetname(name):
                        streets[skz].append((name, snapshot, gemeinde, gkz))
                elif streets[skz][-1][0] != name:
                    streets[skz].append((name, snapshot, gemeinde, gkz))
            else:
                streets[skz] = [(name, snapshot, gemeinde, gkz)]
    
    renamed_skz = [skz for skz in streets if len(streets[skz]) > 1]
    query = """SELECT GEMEINDE.GKZ, GEMEINDE.GEMEINDENAME, STRASSE.SKZ, STRASSE.STRASSENNAME, STRASSE.FOUND, 
        COUNT(ADRESSE.ADRCD), MIN(LAT), MIN(LON), MAX(LAT), MAX(LON) 
        FROM STRASSE JOIN ADRESSE ON ADRESSE.SKZ = STRASSE.SKZ JOIN GEMEINDE ON GEMEINDE.GKZ = ADRESSE.GKZ WHERE STRASSE.SKZ IN ({}) 
        AND ADRESSE.HAUSNRZAHL1 != ""
        GROUP BY STRASSE.SKZ HAVING COUNT(ADRESSE.ADRCD) > 1 ORDER BY 1, 4 DESC""".format(",".join("?"*len(renamed_skz)))
    umap = Umap()
    for row in con.execute(query, tuple(renamed_skz)):
        gkz, gemeindename, skz, strassenname, found, count, min_lat, min_lon, max_lat, max_lon = row
        bezirkname = get_bezirk(gkz)
        bundesland = get_bundesland(gkz)
        layer = "%s: %s" % (bundesland, bezirkname)
        try:
            area_size = projection.get_area_size(min_lon, max_lon, min_lat, max_lat)
        except TypeError:
            continue
        try:
            adr_per_km2 = count / area_size
        except ZeroDivisionError:
            adr_per_km2 = 0
        changes = "\n".join(["%s: %s" % (bev_db.format_key_date(s[1]), s[0]) for s in streets[skz]])
        josm_link = umap.get_josm_link(min_lon, max_lon, min_lat, max_lat, area_size=area_size)
        properties={"name": "%s (%s)" % (strassenname, gemeindename),
                    "description": """%s\n%s\n%s Adressen\nSKZ %s\nGröße: %4.2f km²\nAdr./km²: %s""" % (josm_link, changes, count, skz, area_size, int(adr_per_km2))
        }
        feature = Feature(properties=properties, 
            geometry=Polygon([[[min_lon, min_lat], [min_lon, max_lat], [max_lon, max_lat], [max_lon, min_lat]]])
        )
        if found != bev_db.SearchStatus.FOUND:
            if found == bev_db.SearchStatus.UNDER_CONSTRUCTION:
                umap.add_feature(feature, layer, {"color": "Orange"})
            else:
                umap.add_feature(feature, layer, {"color": "Red"})
        elif include_found_objects:
            umap.add_feature(feature, layer)
    umap.dump('renamed_streets.umap')

def generate_missing_street_umap(gkz_starts_with=""):
    con = bev_db.get_db_conn()
    gkz_starts_with += "%"
    query = """SELECT GEMEINDE.GKZ, GEMEINDE.GEMEINDENAME, STRASSE.SKZ, STRASSENNAME, COUNT(ADRESSE.ADRCD), MIN(LAT), MIN(LON), MAX(LAT), MAX(LON) 
        FROM STRASSE JOIN ADRESSE ON ADRESSE.SKZ = STRASSE.SKZ JOIN GEMEINDE ON GEMEINDE.GKZ = ADRESSE.GKZ WHERE STRASSE.FOUND == 0 AND STRASSE.GKZ LIKE ?
        AND ADRESSE.HAUSNRZAHL1 != ""
        GROUP BY STRASSE.SKZ, STRASSENNAME HAVING COUNT(ADRESSE.ADRCD) == 1 ORDER BY 1, 4 DESC"""
    umap = Umap()
    for row in con.execute(query, (gkz_starts_with,)):
        gkz, gemeindename, skz, strassenname, count, min_lat, min_lon, max_lat, max_lon = row
        if ignore_streetname(strassenname):
                continue
        bezirkname = get_bezirk(gkz)
        try:
            area_size = projection.get_area_size(min_lon, max_lon, min_lat, max_lat)
        except TypeError:
            continue
        try:
            adr_per_km2 = count / area_size
        except ZeroDivisionError:
            adr_per_km2 = 0
        if adr_per_km2 > 100:
            josm_link = umap.get_josm_link(min_lon, max_lon, min_lat, max_lat, area_size=area_size)
            properties={"name": "%s (%s)" % (strassenname, gemeindename),
                        "description": """%s\n%s Adressen\nSKZ %s\nGröße: %4.2f km²\nAdr./km²: %s""" % (josm_link, count, skz, area_size, int(adr_per_km2))
            }
            feature = Feature(properties=properties, 
                geometry=Polygon([[[min_lon, min_lat], [min_lon, max_lat], [max_lon, max_lat], [max_lon, min_lat]]])
            )
            umap.add_feature(feature, bezirkname)
    if gkz_starts_with == "":
        filename = "missing_streets.umap"
    else:
        filename = "missing_streets_%s.umap" % gkz_starts_with
    umap.dump(filename)



if __name__ == "__main__":
    generate_new_street_umap()