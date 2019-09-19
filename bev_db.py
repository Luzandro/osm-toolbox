#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv
import os.path
import sqlite3
import projection
import requests
import overpass
import sys
import zipfile
from gkz import get_bezirk, get_bundesland
from geojson import Point, Feature, FeatureCollection, dump, Polygon

class ProgressBar():
    def __init__(self, message=None):
        self.percentage = 0
        if message:
            print(message)
    
    def update(self, new_percentage):
        new_percentage = round(new_percentage, 2)
        if new_percentage > 100:
            new_percentage = 100
        if new_percentage != self.percentage:
            sys.stdout.write("\r{} %   ".format(str(new_percentage).ljust(6)))
            sys.stdout.write('[{}]'.format(('#' * int(new_percentage / 2)).ljust(50)))
            sys.stdout.flush()
        self.percentage = new_percentage

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.update(100)
        sys.stdout.write("\n")

def import_db(key_date):
    csv_files = ["STRASSE.csv", "GEMEINDE.csv", "ADRESSE.csv", "GEBAEUDE.csv", "ORTSCHAFT.csv"]
    if key_date:
        directory = "Adresse_Relationale_Tabellen-Stichtagsdaten_%s" % key_date
    else:
        directory = "Adresse_Relationale_Tabellen-Stichtagsdaten"
    if not os.path.exists(directory):
        if not os.path.exists("%s.zip" % directory):
            key_date = download_data(key_date)
        with zipfile.ZipFile('Adresse_Relationale_Tabellen-Stichtagsdaten.zip', 'r') as myzip:
            for csv_file in csv_files:
                print("extracting %s" % csv_file)
                myzip.extract(csv_file, "Adresse_Relationale_Tabellen-Stichtagsdaten")
    print("populating database")
    con = sqlite3.connect("%s.sqlite" % directory)
    cur = con.cursor()
    for csv_file in csv_files:
        csv_path = os.path.join(directory, csv_file)
        num_rows = sum(1 for row in open(csv_path, 'r'))
        with ProgressBar("import %s" % csv_file) as pb:
            reader = csv.DictReader(open(csv_path, 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
            table = csv_file[:-4]
            fieldnames = reader.fieldnames

            # don't mind possible sql-injections in this case
            cur.execute("CREATE TABLE %s (%s);" % (table, ",".join(fieldnames)))
            cur.execute("ALTER TABLE %s ADD FOUND BOOLEAN;" % table)
            fieldnames.append("FOUND")
            if table in ("ADRESSE", "GEBAEUDE"):
                cur.execute("ALTER TABLE %s ADD LAT Decimal(9,6);" % table)
                cur.execute("ALTER TABLE %s ADD LON Decimal(9,6);" % table)
                fieldnames.extend(["LAT", "LON"])
            placeholder = ",".join("?"*len(fieldnames))
            for i, row in enumerate(reader):
                current_percentage = float(i) / num_rows * 100
                pb.update(current_percentage)
                if table in ("ADRESSE", "GEBAEUDE"):
                    (row["LON"], row["LAT"]) = projection.reproject(row["EPSG"], (row["RW"], row["HW"]))
                cur.execute("INSERT INTO %s VALUES (%s);" % (table, placeholder), list(row.values()))
    print("adding flag for ambiguous streetnames")
    cur.execute("ALTER TABLE STRASSE ADD COLUMN IST_MEHRDEUTIG BOOLEAN DEFAULT 0")
    cur.execute("UPDATE STRASSE SET IST_MEHRDEUTIG=1 WHERE SKZ IN (SELECT S1. SKZ FROM STRASSE S1, STRASSE S2 WHERE S1.GKZ == S2.GKZ AND S1.STRASSENNAME == S2.STRASSENNAME AND S1.SKZ != S2.SKZ)")
    con.commit()
    con.close()

def download_data(key_date=None):
    """This function downloads the address data from BEV and displays its terms
    of usage"""

    if key_date:
        address_data_url = "http://www.bev.gv.at/pls/portal/docs/PAGE/BEV_PORTAL_CONTENT_ALLGEMEIN/0200_PRODUKTE/UNENTGELTLICHE_PRODUKTE_DES_BEV/ARCHIV/Adresse_Relationale_Tabellen-Stichtagsdaten_%s.zip" % key_date
    else:
        address_data_url = "http://www.bev.gv.at/pls/portal/docs/PAGE/BEV_PORTAL_CONTENT_ALLGEMEIN/0200_PRODUKTE/UNENTGELTLICHE_PRODUKTE_DES_BEV/Adresse_Relationale_Tabellen-Stichtagsdaten.zip"
    response = requests.get(address_data_url, stream=True)
    if not response.ok:
        print("Download for key date %s failed" % key_date)
        sys.exit(1)
    with open(address_data_url.split('/')[-1], 'wb') as handle, ProgressBar("downloading address data from BEV") as pb:
        for i, data in enumerate(response.iter_content(chunk_size=1000000)):
            handle.write(data)
            current_percentage = i * 1.3
            pb.update(current_percentage)
    if not key_date:
        z = zipfile.ZipFile('Adresse_Relationale_Tabellen-Stichtagsdaten.zip', 'r')
        for f in z.infolist():
            if f.filename == 'ADRESSE.csv':
                key_date = "%02d%02d%d" % tuple(reversed(f.date_time[:3]))
                break
        os.rename('Adresse_Relationale_Tabellen-Stichtagsdaten.zip', 'Adresse_Relationale_Tabellen-Stichtagsdaten_%s.zip' % key_date)
        os.symlink('Adresse_Relationale_Tabellen-Stichtagsdaten_%s.zip' % key_date, 'Adresse_Relationale_Tabellen-Stichtagsdaten.zip')
    return key_date

def search_osm_objects(db_con):
    overpass.use_local_overpass(True)
    select_cursor = db_con.cursor()
    update_cursor = db_con.cursor()
    for row in select_cursor.execute("""SELECT GEMEINDE.GKZ, GEMEINDENAME, MIN(LAT), MIN(LON), MAX(LAT), MAX(LON) 
        FROM GEMEINDE JOIN ADRESSE ON ADRESSE.GKZ = GEMEINDE.GKZ WHERE GEMEINDE.FOUND IS NULL 
        GROUP BY GEMEINDE.GKZ, GEMEINDENAME ORDER BY GEMEINDENAME"""):

        gkz, gemeindename, min_lat, min_lon, max_lat, max_lon = row
        found = overpass.admin_boundary_exists(min_lat, min_lon, max_lat, max_lon, gemeindename)
        print(gemeindename, found)
        update_cursor.execute("UPDATE GEMEINDE SET FOUND = ? WHERE GEMEINDE.GKZ=?;", (found, gkz))
        db_con.commit()
    
    count = select_cursor.execute("SELECT COUNT(*) FROM ORTSCHAFT WHERE ORTSCHAFT.FOUND IS NULL AND ORTSCHAFT.GKZ LIKE '317%'").fetchone()[0]
    i = 0
    with ProgressBar("suche Ortschaften...") as pb:
        for row in select_cursor.execute("""SELECT ORTSCHAFT.OKZ, ORTSNAME, MIN(LAT), MIN(LON), MAX(LAT), MAX(LON) 
            FROM ORTSCHAFT JOIN ADRESSE ON ADRESSE.OKZ = ORTSCHAFT.OKZ WHERE ORTSCHAFT.FOUND IS NULL OR ORTSCHAFT.FOUND == 0 AND ORTSCHAFT.GKZ LIKE '317%'
            GROUP BY ORTSCHAFT.OKZ, ORTSNAME ORDER BY ORTSNAME"""):

            i += 1
            current_percentage = float(i) / count * 100
            pb.update(current_percentage)

            okz, ortsname, min_lat, min_lon, max_lat, max_lon = row
            if (ortsname.startswith("Wien") or 
                ortsname.startswith("Graz") or
                ortsname.startswith("Klagenfurt")):
                
                found = True
            else:
                found = overpass.place_exists(min_lat, min_lon, max_lat, max_lon, ortsname, tolerance=0.01, ignore_postfix=True)
            #print(ortsname, found)
            update_cursor.execute("UPDATE ORTSCHAFT SET FOUND = ? WHERE ORTSCHAFT.OKZ=?;", (found, okz))
        db_con.commit()

    count = select_cursor.execute("SELECT COUNT(*) FROM STRASSE WHERE STRASSE.FOUND IS NULL OR STRASSE.FOUND == 0 AND STRASSE.GKZ LIKE '317%'").fetchone()[0]
    i = 0
    with ProgressBar("suche Straßen...") as pb:
        try:
            for row in select_cursor.execute("""SELECT STRASSE.SKZ, STRASSE.STRASSENNAME, COUNT(ADRESSE.ADRCD), MIN(LAT), MIN(LON), MAX(LAT), MAX(LON) 
                FROM STRASSE JOIN ADRESSE ON ADRESSE.SKZ = STRASSE.SKZ 
                JOIN ORTSCHAFT ON ORTSCHAFT.OKZ = ADRESSE.OKZ
                WHERE STRASSE.FOUND IS NULL OR STRASSE.FOUND == 0 AND STRASSE.GKZ LIKE '317%'
                AND STRASSE.STRASSENNAME != ORTSCHAFT.ORTSNAME
                GROUP BY STRASSE.SKZ, STRASSE.STRASSENNAME ORDER BY COUNT(ADRESSE.ADRCD) DESC"""):

                i += 1
                current_percentage = float(i) / count * 100
                pb.update(current_percentage)

                skz, strassenname, adr_count, min_lat, min_lon, max_lat, max_lon = row
                streets = overpass.get_streets_by_name(min_lat, min_lon, max_lat, max_lon, strassenname, tolerance=0.01)
                if len(streets[0]) == 0:
                    found = overpass.place_exists(min_lat, min_lon, max_lat, max_lon, strassenname, tolerance=0.01)
                else:
                    found = True
                #print(skz, strassenname, found)
                update_cursor.execute("UPDATE STRASSE SET FOUND = ? WHERE STRASSE.SKZ=?;", (found, skz))
        except KeyboardInterrupt:
            print("abort...")
    db_con.commit()

def generate_missing_place_html(db_con):
    cur = db_con.cursor()
    f = open('missing_places.html','w')
    f.write("<html><head></head><body>")
    places = {}
    for row in cur.execute("""SELECT GEMEINDE.GKZ, ORTSCHAFT.OKZ, ORTSNAME, COUNT(ADRESSE.ADRCD), MIN(LAT), MIN(LON), MAX(LAT), MAX(LON) 
        FROM ORTSCHAFT JOIN ADRESSE ON ADRESSE.OKZ = ORTSCHAFT.OKZ JOIN GEMEINDE ON GEMEINDE.GKZ = ADRESSE.GKZ WHERE ORTSCHAFT.FOUND == 0
        GROUP BY ORTSCHAFT.OKZ, ORTSNAME ORDER BY 4 DESC"""):

        gkz, okz, ortsname, count, min_lat, min_lon, max_lat, max_lon = row
        land = get_bundesland(gkz)
        bezirk = get_bezirk(gkz)
        if not land in places:
            places[land] = {}
        if not bezirk in places[land]:
            places[land][bezirk] = []
        places[land][bezirk].append("<li><a href='http://localhost:8111/zoom?left=%s&bottom=%s&right=%s&top=%s'>%s</a> (%s Adr.; OKZ %s)</li>" % (min_lon, min_lat, max_lon, max_lat, ortsname, count, okz))

        #f.write("<li><a href='http://localhost:8111/zoom?left=%s&bottom=%s&right=%s&top=%s'>%s</a> (%s Adr.; OKZ %s)</li>" % (min_lon, min_lat, max_lon, max_lat, ortsname, count, okz))
    for land in places.keys():
        f.write("<h1>%s (%d)</h1>" % (land, sum([len(places[land][bezirk]) for bezirk in places[land]])))
        for bezirk in places[land].keys():
            f.write("<h2>%s (%d)</h2>" % (bezirk, len(places[land][bezirk])))
            f.write("<ol>")
            f.write("\n".join(places[land][bezirk]))
            f.write("</ol>")
    f.write("</body></html>")
    f.close()

def generate_missing_place_geojson(db_con):
    cur = db_con.cursor()
    f = open('missing_places.geojson','w')
    features = []
    for row in cur.execute("""SELECT GEMEINDE.GKZ, ORTSCHAFT.OKZ, ORTSNAME, COUNT(ADRESSE.ADRCD), MIN(LAT), MIN(LON), MAX(LAT), MAX(LON) 
        FROM ORTSCHAFT JOIN ADRESSE ON ADRESSE.OKZ = ORTSCHAFT.OKZ JOIN GEMEINDE ON GEMEINDE.GKZ = ADRESSE.GKZ WHERE ORTSCHAFT.FOUND == 0
        GROUP BY ORTSCHAFT.OKZ, ORTSNAME ORDER BY 4 DESC"""):

        gkz, okz, ortsname, count, min_lat, min_lon, max_lat, max_lon = row
        #features.append(Feature(properties={"name": ortsname,
            #"description": "[[http://localhost:8111/zoom?left=%s&bottom=%s&right=%s&top=%s|zoom JOSM auf Adress-Bereich]]\n%s Adressen\nOKZ %s" % (min_lon, min_lat, max_lon, max_lat, count, okz)},
            #geometry=Point([min_lon, min_lat])
        #))
        features.append(Feature(properties={"name": ortsname,
            "description": "[[http://localhost:8111/zoom?left=%s&bottom=%s&right=%s&top=%s|zoom JOSM auf Adress-Bereich]]\n%s Adressen\nOKZ %s" % (min_lon, min_lat, max_lon, max_lat, count, okz)},
            geometry=Polygon([[[min_lon, min_lat], [min_lon, max_lat], [max_lon, max_lat], [max_lon, min_lat]]])
        ))
    fc = FeatureCollection(features)
    dump(fc,f, indent=2)
    f.close()

def generate_missing_street_geojson(db_con):
    cur = db_con.cursor()
    f = open('missing_streets.geojson','w')
    features = []
    for row in cur.execute("""SELECT GEMEINDE.GKZ, GEMEINDE.GEMEINDENAME, STRASSE.SKZ, STRASSENNAME, COUNT(ADRESSE.ADRCD), MIN(LAT), MIN(LON), MAX(LAT), MAX(LON) 
        FROM STRASSE JOIN ADRESSE ON ADRESSE.SKZ = STRASSE.SKZ JOIN GEMEINDE ON GEMEINDE.GKZ = ADRESSE.GKZ WHERE STRASSE.FOUND == 0 AND STRASSE.GKZ LIKE '3%'
        GROUP BY STRASSE.SKZ, STRASSENNAME HAVING COUNT(ADRESSE.ADRCD) > 5 ORDER BY 4 DESC"""):

        gkz, gemeindename, skz, strassenname, count, min_lat, min_lon, max_lat, max_lon = row
        a = projection.get_distance((min_lon, min_lat), (min_lon, max_lat))
        b = projection.get_distance((min_lon, min_lat), (max_lon, min_lat))
        area_size = a * b / 1000000
        try:
            adr_per_km2 = count / area_size
        except ZeroDivisionError:
            adr_per_km2 = 0

        if adr_per_km2 > 100:
            features.append(Feature(properties={"name": "%s (%s)" % (strassenname, gemeindename),
                "description": "[[http://localhost:8111/zoom?left=%s&bottom=%s&right=%s&top=%s|zoom JOSM auf Adress-Bereich]]\n%s Adressen\nSKZ %s\nGröße: %4.2f km²\nAdr./km²: %s" % (min_lon, min_lat, max_lon, max_lat, count, skz, area_size, int(adr_per_km2))},
                geometry=Polygon([[[min_lon, min_lat], [min_lon, max_lat], [max_lon, max_lat], [max_lon, min_lat]]])
            ))
    fc = FeatureCollection(features)
    dump(fc,f, indent=2)
    f.close()

def generate_missing_street_umap(db_con):
    cur = db_con.cursor()
    f = open('missing_streets.umap','w')
    layers = []
    layer = None
    #features = []
    prev_bezirk = None
    for row in cur.execute("""SELECT GEMEINDE.GKZ, GEMEINDE.GEMEINDENAME, STRASSE.SKZ, STRASSENNAME, COUNT(ADRESSE.ADRCD), MIN(LAT), MIN(LON), MAX(LAT), MAX(LON) 
        FROM STRASSE JOIN ADRESSE ON ADRESSE.SKZ = STRASSE.SKZ JOIN GEMEINDE ON GEMEINDE.GKZ = ADRESSE.GKZ WHERE STRASSE.FOUND == 0 AND STRASSE.GKZ LIKE '3%'
        GROUP BY STRASSE.SKZ, STRASSENNAME HAVING COUNT(ADRESSE.ADRCD) > 5 ORDER BY 1, 4 DESC"""):

        gkz, gemeindename, skz, strassenname, count, min_lat, min_lon, max_lat, max_lon = row
        bezirkname = get_bezirk(gkz)
        a = projection.get_distance((min_lon, min_lat), (min_lon, max_lat))
        b = projection.get_distance((min_lon, min_lat), (max_lon, min_lat))
        area_size = a * b / 1000000
        try:
            adr_per_km2 = count / area_size
        except ZeroDivisionError:
            adr_per_km2 = 0

        if adr_per_km2 > 100:
            feature = Feature(properties={"name": "%s (%s)" % (strassenname, gemeindename),
                "description": "[[http://localhost:8111/zoom?left=%s&bottom=%s&right=%s&top=%s|zoom JOSM auf Adress-Bereich]]\n%s Adressen\nSKZ %s\nGröße: %4.2f km²\nAdr./km²: %s" % (min_lon, min_lat, max_lon, max_lat, count, skz, area_size, int(adr_per_km2))},
                geometry=Polygon([[[min_lon, min_lat], [min_lon, max_lat], [max_lon, max_lat], [max_lon, min_lat]]])
            )
            if bezirkname == prev_bezirk:
                layer["features"].append(feature)
            else:
                if prev_bezirk is not None:
                    layers.append(layer)
                layer = FeatureCollection([])
                layer["_umap_options"] = {
                    "displayOnLoad": False,
                    "browsable": True,
                    "remoteData": {},
                    "name": bezirkname,
                    "description": "",
                    "type": "Default",
                    "cluster": {}
                }
                layer["features"].append(feature)
            prev_bezirk = bezirkname
    #fc = FeatureCollection(features)
    umap = {
        "type": "umap",
        "uri": "https://umap.openstreetmap.de/de/map/test_957",
        "properties": {
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
        },
        "layers": layers
    }
    dump(umap,f, indent=2)
    f.close()

def generate_missing_street_html(db_con):
    cur = db_con.cursor()
    f = open('missing_streets.html','w')
    f.write("<html><head></head><body>")
    places = {}
    for row in cur.execute("""SELECT GEMEINDE.GKZ, STRASSE.SKZ, STRASSENNAME, COUNT(ADRESSE.ADRCD), MIN(LAT), MIN(LON), MAX(LAT), MAX(LON) 
        FROM STRASSE JOIN ADRESSE ON ADRESSE.SKZ = STRASSE.SKZ JOIN GEMEINDE ON GEMEINDE.GKZ = ADRESSE.GKZ WHERE STRASSE.FOUND == 0 AND STRASSE.GKZ LIKE '3%'
        GROUP BY STRASSE.SKZ, STRASSENNAME HAVING COUNT(ADRESSE.ADRCD) > 5 ORDER BY 4 DESC"""):

        gkz, skz, strassenname, count, min_lat, min_lon, max_lat, max_lon = row
        land = get_bundesland(gkz)
        bezirk = get_bezirk(gkz)
        if not land in places:
            places[land] = {}
        if not bezirk in places[land]:
            places[land][bezirk] = []
        places[land][bezirk].append("<li><a href='http://localhost:8111/zoom?left=%s&bottom=%s&right=%s&top=%s'>%s</a> (%s Adr.)</li>" % (min_lon, min_lat, max_lon, max_lat, strassenname, count))

        #f.write("<li><a href='http://localhost:8111/zoom?left=%s&bottom=%s&right=%s&top=%s'>%s</a> (%s Adr.; OKZ %s)</li>" % (min_lon, min_lat, max_lon, max_lat, ortsname, count, okz))
    for land in places.keys():
        f.write("<h1>%s (%d)</h1>" % (land, sum([len(places[land][bezirk]) for bezirk in places[land]])))
        for bezirk in places[land].keys():
            f.write("<h2>%s (%d)</h2>" % (bezirk, len(places[land][bezirk])))
            f.write("<ol>")
            f.write("\n".join(places[land][bezirk]))
            f.write("</ol>")
    f.write("</body></html>")
    f.close()

def get_db_conn(key_date=None):
    if key_date:
        db_filename = "Adresse_Relationale_Tabellen-Stichtagsdaten_%s.sqlite" % key_date
    else:
        db_filename = "Adresse_Relationale_Tabellen-Stichtagsdaten.sqlite"
    if not os.path.exists(db_filename):
        import_db(key_date)
    return sqlite3.connect(db_filename)

def _get_bounds(db_con, sql, parameter):
    (min_lon, min_lat, max_lon, max_lat) = (None, None, None, None)
    cur = db_con.cursor()
    cur.execute(sql, parameter)
    for row in cur:
        lon, lat = row[:-1]
        if lon == '' or lat == '':
            continue
        lon, lat = projection.reproject(row[2], row[:-1])
        if min_lon is None:
            min_lon = lon
            max_lon = lon
            min_lat = lat
            max_lat = lat
        else:            
            if lon < min_lon:
                min_lon = lon
            elif lon > max_lon:
                max_lon = lon
            if lat < min_lat:
                min_lat = lat
            elif lat > max_lat:
                max_lat = lat
    if min_lon is not None:
        min_lat -= 0.01
        min_lon -= 0.01
        max_lat += 0.01
        max_lon += 0.01
    return (min_lat, min_lon, max_lat, max_lon)


def get_district_bounds(gkz, db_con):
    # could get quite large
    return _get_bounds(db_con, "SELECT RW, HW, EPSG FROM ADRESSE WHERE GKZ == ?;", [str(gkz),])

def get_street_bounds(skz, db_con):
    return _get_bounds(db_con, "SELECT RW, HW, EPSG FROM ADRESSE WHERE SKZ == ?;", [str(skz),])

def execute(sql, db_con=None):
    if db_con is None:
        db_con = get_db_conn()
    cur = db_con.cursor()
    for row in cur.execute(sql):
        print(row)

def print_district_partitions(gemeindename):
    execute("SELECT GEMEINDE.GKZ, OKZ, ORTSNAME FROM GEMEINDE JOIN ORTSCHAFT ON GEMEINDE.GKZ = ORTSCHAFT.GKZ WHERE GEMEINDENAME='%s'" % gemeindename)


if __name__ == "__main__":
    #search_osm_objects(get_db_conn())
    #generate_missing_place_html(get_db_conn())
    #generate_missing_street_html(get_db_conn())
    #download_data("01102018")
    #get_db_conn()
    generate_missing_street_umap(get_db_conn())



