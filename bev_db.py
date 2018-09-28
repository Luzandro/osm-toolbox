#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv
import os.path
import sqlite3
import projection

def import_db(directory):
    csv_files = ["STRASSE.csv", "GEMEINDE.csv", "ADRESSE.csv", "GEBAEUDE.csv", "ORTSCHAFT.csv"]
    con = sqlite3.connect("%s.sqlite" % directory)
    cur = con.cursor()
    for csv_file in csv_files:
        csv_path = os.path.join(directory, csv_file)
        reader = csv.DictReader(open(csv_path, 'r', encoding='UTF-8-sig'), delimiter=';', quotechar='"')
        table = csv_file[:-4]

        # don't mind possible sql-injections in this case
        cur.execute("CREATE TABLE %s (%s);" % (table, ",".join(reader.fieldnames)))
        placeholder = ",".join("?"*len(reader.fieldnames))
        for row in reader:
            cur.execute("INSERT INTO %s VALUES (%s);" % (table, placeholder), list(row.values()))
    con.commit()
    con.close()

def get_db_conn(db_date):
    directory = "Adresse_Relationale_Tabellen-Stichtagsdaten_%s" % db_date
    db_filename = "%s.sqlite" % directory
    if not os.path.exists(db_filename):
        import_db(directory)
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
