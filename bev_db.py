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
from progressbar import ProgressBar

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



