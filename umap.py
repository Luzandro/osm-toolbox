#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import bev_db
import projection
from gkz import get_bezirk, get_bundesland
from geojson import Point, Feature, FeatureCollection, dump, Polygon

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

def generate_new_street_umap(number_of_snapshots=2, include_found_objects=False):
    ids = {}
    skz_found = {}
    con = bev_db.get_db_conn() # always use newest db to check found status
    for skz, found in con.execute("SELECT SKZ, FOUND FROM STRASSE"):
        if found is None or found == 0:
            skz_found[skz] = False
        else:
            skz_found[skz] = True
    for (old, new) in zip(bev_db.SNAPSHOTS[-number_of_snapshots:], bev_db.SNAPSHOTS[-number_of_snapshots+1:]):
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
            FROM STRASSE JOIN ADRESSE ON ADRESSE.SKZ = STRASSE.SKZ JOIN GEMEINDE ON GEMEINDE.GKZ = ADRESSE.GKZ WHERE STRASSE.SKZ IN ({}) 
            GROUP BY STRASSE.SKZ HAVING COUNT(ADRESSE.ADRCD) > 1 ORDER BY 1, 4 DESC""".format(",".join("?"*len(new_ids)))
        umap = Umap()
        for row in cur.execute(query, tuple(new_ids)):
            gkz, gemeindename, skz, strassenname, count, min_lat, min_lon, max_lat, max_lon = row
            bezirkname = get_bezirk(gkz)
            try:
                a = projection.get_distance((min_lon, min_lat), (min_lon, max_lat))
                b = projection.get_distance((min_lon, min_lat), (max_lon, min_lat))
            except TypeError:
                continue
            area_size = a * b / 1000000
            try:
                adr_per_km2 = count / area_size
            except ZeroDivisionError:
                adr_per_km2 = 0
            #josm_link = "[[http://localhost:8111/zoom?left=%s&bottom=%s&right=%s&top=%s|zoom JOSM auf Adress-Bereich]]"
            josm_link = "[[http://localhost:8111/load_and_zoom?left=%s&bottom=%s&right=%s&top=%s|Adress-Bereich in JOSM laden]]" % (min_lon, min_lat, max_lon, max_lat)
            properties={"name": "%s (%s)" % (strassenname, gemeindename),
                        "description": """%s\n%s Adressen\nSKZ %s\nGröße: %4.2f km²\nAdr./km²: %s""" % (josm_link, count, skz, area_size, int(adr_per_km2))
            }
            feature = Feature(properties=properties, 
                geometry=Polygon([[[min_lon, min_lat], [min_lon, max_lat], [max_lon, max_lat], [max_lon, min_lat]]])
            )
            if skz not in skz_found or not skz_found[skz]:
                umap.add_feature(feature, bezirkname, {"color": "Red"})
            elif include_found_objects:
                umap.add_feature(feature, bezirkname)
        umap.dump('new_streets_%s.umap' % new)

def generate_renamed_street_umap(number_of_snapshots=2, include_found_objects=False):
    streets = {}
    for snapshot in bev_db.SNAPSHOTS[-number_of_snapshots:]:
        print(snapshot)
        con = bev_db.get_db_conn(snapshot)
        cur = con.cursor()
        sql = "SELECT s.SKZ, s.STRASSENNAME, g.GEMEINDENAME, g.GKZ FROM STRASSE s JOIN GEMEINDE g ON s.GKZ = g.GKZ"
        for row in cur.execute(sql):
            skz, name, gemeinde, gkz = row
            if skz in streets:
                if streets[skz][-1][0] != name:
                    streets[skz].append((name, snapshot, gemeinde, gkz))
            else:
                streets[skz] = [(name, snapshot, gemeinde, gkz)]
    
    renamed_skz = [skz for skz in streets if len(streets[skz]) > 1]
    query = """SELECT GEMEINDE.GKZ, GEMEINDE.GEMEINDENAME, STRASSE.SKZ, STRASSE.STRASSENNAME, STRASSE.FOUND, 
        COUNT(ADRESSE.ADRCD), MIN(LAT), MIN(LON), MAX(LAT), MAX(LON) 
        FROM STRASSE JOIN ADRESSE ON ADRESSE.SKZ = STRASSE.SKZ JOIN GEMEINDE ON GEMEINDE.GKZ = ADRESSE.GKZ WHERE STRASSE.SKZ IN ({}) 
        GROUP BY STRASSE.SKZ HAVING COUNT(ADRESSE.ADRCD) > 1 ORDER BY 1, 4 DESC""".format(",".join("?"*len(renamed_skz)))
    umap = Umap()
    for row in con.execute(query, tuple(renamed_skz)):
        gkz, gemeindename, skz, strassenname, found, count, min_lat, min_lon, max_lat, max_lon = row
        bezirkname = get_bezirk(gkz)
        try:
            a = projection.get_distance((min_lon, min_lat), (min_lon, max_lat))
            b = projection.get_distance((min_lon, min_lat), (max_lon, min_lat))
        except TypeError:
            continue
        area_size = a * b / 1000000
        try:
            adr_per_km2 = count / area_size
        except ZeroDivisionError:
            adr_per_km2 = 0
        changes = "\n".join(["%s: %s" % (s[1], s[0]) for s in streets[skz]])
        if area_size < 40:
            josm_link = "[[http://localhost:8111/load_and_zoom?left=%s&bottom=%s&right=%s&top=%s|Adress-Bereich in JOSM laden]]" % (min_lon, min_lat, max_lon, max_lat)
        else:
            josm_link = "[[http://localhost:8111/zoom?left=%s&bottom=%s&right=%s&top=%s|zoom JOSM auf Adress-Bereich]]" % (min_lon, min_lat, max_lon, max_lat)
        properties={"name": "%s (%s)" % (strassenname, gemeindename),
                    "description": """%s\n%s\n%s Adressen\nSKZ %s\nGröße: %4.2f km²\nAdr./km²: %s""" % (josm_link, changes, count, skz, area_size, int(adr_per_km2))
        }
        feature = Feature(properties=properties, 
            geometry=Polygon([[[min_lon, min_lat], [min_lon, max_lat], [max_lon, max_lat], [max_lon, min_lat]]])
        )
        if not found:
            umap.add_feature(feature, bezirkname, {"color": "Red"})
        elif include_found_objects:
            umap.add_feature(feature, bezirkname)
    umap.dump('renamed_streets.umap')

if __name__ == "__main__":
    #generate_new_street_umap()
    generate_renamed_street_umap(9)
    