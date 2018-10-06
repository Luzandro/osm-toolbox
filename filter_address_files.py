#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import xml.etree.cElementTree as ET
from collections import defaultdict
from math import cos, asin, sqrt
import overpy
import sys
from glob import glob

# TODO: addr:units

def get_existing_addresses(minlat, minlon, maxlat, maxlon):
    api = overpy.Overpass()
    result = api.query('nwr["addr:housenumber"](%s,%s,%s,%s);out center;' % (minlat, minlon, maxlat, maxlon))

    address_points = []
    address_points.extend(result.ways)
    address_points.extend(result.relations)
    for polygon in address_points:
        polygon.lat = polygon.center_lat
        polygon.lon = polygon.center_lon
    address_points.extend(result.nodes)

    addresses = defaultdict(lambda: defaultdict(list))
    for addr in address_points:
        if "addr:street" in addr.tags:
            street = addr.tags["addr:street"]
        elif "addr:place" in addr.tags:
            street = addr.tags["addr:place"]
        else:
            continue
        street = normalize_streetname(street)
        housenumber = addr.tags["addr:housenumber"].lower()

        address = {'lat': addr.lat, 'lon': addr.lon}
        if "addr:city" in addr.tags:
            address["city"] = addr.tags["addr:city"]
        if "addr:unit" in addr.tags:
            address["unit"] = addr.tags["addr:unit"]
        addresses[street][housenumber].append(address)
    return addresses

def filter_address_file(filename):
    tree = ET.parse(filename)
    root = tree.getroot()
    bounds = root.find("bounds")
    bb_tolerance = 0.001
    streets = get_existing_addresses(
        float(bounds.get("minlat"))-bb_tolerance,
        float(bounds.get("minlon"))-bb_tolerance,
        float(bounds.get("maxlat"))+bb_tolerance,
        float(bounds.get("maxlon"))+bb_tolerance)
    alt_names = get_alternative_streetnames(
        bounds.get("minlat"),
        bounds.get("minlon"),
        bounds.get("maxlat"),
        bounds.get("maxlon"))

    for street in list(streets.keys()):
        for alternative in alt_names[street]:
            streets[alternative] = streets[street]

    for node in root.findall('node'):
        tags = {}
        for tag in node.findall('tag'):
            tags[tag.get("k")] = tag.get("v")
        if "addr:street" in tags:
            street = tags["addr:street"]
        else:
            street = tags["addr:place"]
        street = normalize_streetname(street)
        housenumber = tags["addr:housenumber"].lower()
        if street in streets and housenumber in streets[street]:
            p1 = (float(node.get("lat")), float(node.get("lon")))
            for adr in streets[street][housenumber]:
                if "city" in adr and adr["city"] != tags["addr:city"]:
                    # ignore existing addresses with different city
                    continue
                p2 = (float(adr["lat"]), float(adr["lon"]))
                dist = get_distance(p1, p2)
                if dist < 150:
                    root.remove(node)
                    break
    if not root.find('node') is None:
        tree.write('%s_filtered.osm' % filename[:-4])

''' strips whitespace/dash, ß->ss, ignore case '''
def normalize_streetname(street):
    s = street.replace("ß", "ss").replace(" ", "").replace("-", "").lower()
    if s.endswith("str.") or s.endswith("g."):
        s = s[:-1] + "asse"
    s = s.replace("dr.", "doktor")
    return s

def get_alternative_streetnames(minlat, minlon, maxlat, maxlon, normalize_streetnames = True):
    if normalize_streetnames:
        normalize = normalize_streetname
    else:
        normalize = lambda x : x
    alt_names = defaultdict(set)
    api = overpy.Overpass()
    result = api.query('way[highway][alt_name](%s,%s,%s,%s);out;' % (minlat, minlon, maxlat, maxlon))
    for way in result.ways:
        name = normalize(way.tags["name"])
        alt_name = normalize(way.tags["alt_name"])
        alt_names[name].add(alt_name)
        alt_names[alt_name].add(name)
    result = api.query('way[highway][official_name](%s,%s,%s,%s);out;' % (minlat, minlon, maxlat, maxlon))
    for way in result.ways:
        name = normalize(way.tags["name"])
        official_name = normalize(way.tags["official_name"])
        alt_names[name].add(official_name)
        alt_names[official_name].add(name)
    return alt_names

def get_distance(point1, point2):
    lat1, lon1 = point1
    lat2, lon2 = point2
    p = 0.017453292519943295     #Pi/180
    a = 0.5 - cos((lat2 - lat1) * p)/2 + cos(lat1 * p) * cos(lat2 * p) * (1 - cos((lon2 - lon1) * p)) / 2
    return 12742 * asin(sqrt(a)) * 1000 #2*R*asin...

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if len(sys.argv) == 2:
            filenames = glob(sys.argv[1])
        else:
            filenames = sys.argv[1:]
        for filename in filenames:
            if not "_filtered.osm" in filename:
                print(filename)
                filter_address_file(filename)