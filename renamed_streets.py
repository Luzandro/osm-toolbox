#!/usr/bin/env python3
# -*- coding: utf-8
import bev_db
import overpy
import csv
import re
from streetnames import normalize_streetname

def compare_street_names(db_date_old, db_date_new, ignore_minor_changes=False):
    csv_header = ['Gemeinde', db_date_old, db_date_new, 'Way ID', 'aktuell', 'OSM-Link']
    csv_filename = 'Geaenderte_Strassennamen_%s-%s.csv' % (db_date_old, db_date_new)
    con = bev_db.get_db_conn(db_date_old)
    cur = con.cursor()
    sql = "SELECT s.SKZ, s.STRASSENNAME FROM STRASSE s"
    streets = {}
    for row in cur.execute(sql):
        skz, name = row
        streets[skz] = name
    con.close()

    writer = csv.DictWriter(open(csv_filename, 'w'), csv_header, delimiter=";", quotechar='"')
    writer.writeheader()
    con = bev_db.get_db_conn(db_date_new)
    cur = con.cursor()
    placeholder = ",".join("?"*len(streets.keys()))
    sql = "SELECT s.SKZ, s.STRASSENNAME, g.GEMEINDENAME, g.GKZ FROM STRASSE s JOIN GEMEINDE g ON s.GKZ = g.GKZ WHERE s.SKZ IN (%s)" % placeholder
    for row in cur.execute(sql, list(streets.keys())):
        skz, name, gemeinde, gkz = row
        if name != streets[skz]:
            if ignore_minor_changes and (normalize_streetname(name) == normalize_streetname(streets[skz])):
                continue
            boundingbox = bev_db.get_street_bounds(skz, con)
            zoom = 17
            if boundingbox[0] is None:
                boundingbox = bev_db.get_district_bounds(gkz, con)
                zoom = 14
            old_id = get_way_id(streets[skz], boundingbox)
            if old_id == "":
                new_id = get_way_id(name, boundingbox)
                if new_id == "":
                    old_id = get_way_id(streets[skz], boundingbox, fuzzy=True)
                    if old_id == "":
                        way_id = ""
                        up2date = "?"
                    else:
                        way_id = old_id
                        up2date = "nein"
                else:
                    way_id = new_id
                    up2date = "wahrscheinlich"
            else:
                way_id = old_id
                up2date = "nein"

            row = {
                "Gemeinde": gemeinde, 
                db_date_old: streets[skz], 
                db_date_new: name, 
                "Way ID": way_id,
                "aktuell": up2date,
                "OSM-Link": get_osm_link(boundingbox, zoom)}
            print(row)
            writer.writerow(row)
    con.close()

def get_osm_link(boundingbox, zoom):
    if boundingbox[0] is None:
        return ""
    lat = (boundingbox[0] + boundingbox[2]) / 2
    lon = (boundingbox[1] + boundingbox[3]) / 2
    return "https://www.openstreetmap.org/#map=%s/%s/%s" % (zoom, lat, lon)

def get_way_id(streetname, boundingbox, fuzzy=False):
    if boundingbox[0] is None:
        return ""
    api = overpy.Overpass()
    s = streetname.replace('"', '\\"')
    b = str(boundingbox)
    if fuzzy:
        s = re.sub("[ -]", "[ -]*", s)
        s = s.replace("straße", "[ -]*straße")
        q = """(way[highway][name~"%s"]%s;nwr[place][name~"%s"]%s;);out;""" % (s, b, s, b)
    else:
        q = """(way[highway][name="%s"]%s;nwr[place][name="%s"]%s;);out;""" % (s, b, s, b)
    result = api.query(q)
    results = result.ways + result.nodes + result.relations
    if len(results) > 0:
        return results[0].id
    else:
        return ""


if __name__ == '__main__':
    compare_street_names("02042018", "01102018", True)
