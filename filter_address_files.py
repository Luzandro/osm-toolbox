#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import xml.etree.cElementTree as ET
from collections import defaultdict
from math import cos, asin, sqrt
import overpy
import sys
from glob import glob
import os
from abbreviations import ABBREVIATIONS

# TODO: addr:units

def get_existing_addresses(minlat, minlon, maxlat, maxlon):
    api = overpy.Overpass()
    query = 'nwr["addr:housenumber"](%s,%s,%s,%s);out center;' % (minlat, minlon, maxlat, maxlon)
    result = api.query(query)

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
        elif "/" in housenumber:
            housenumber, address["unit"] = housenumber.split("/", 1)
        addresses[street][housenumber].append(address)
    return addresses

def filter_address_file(filename, addresses):
    tree = ET.parse(filename)
    root = tree.getroot()

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
        if street in addresses and housenumber in addresses[street]:
            p1 = (float(node.get("lat")), float(node.get("lon")))
            for adr in addresses[street][housenumber]:
                p2 = (float(adr["lat"]), float(adr["lon"]))
                dist = get_distance(p1, p2)
                #print(street, housenumber, dist)
                if dist < 150:
                    if "city" in adr and adr["city"] != tags["addr:city"] and dist > 50:
                        # if city is set and differs use higher threshold
                        continue
                    root.remove(node)
                    break
    filtered_filename = '%s_filtered.osm' % filename[:-4]
    if not root.find('node') is None:
        tree.write(filtered_filename)
    elif os.path.exists(filtered_filename):
        os.remove(filtered_filename)

''' strips whitespace/dash, ß->ss, ignore case '''
def normalize_streetname(street, expand_abbreviations=True):
    s = street.replace("ß", "ss").replace(" ", "").replace("-", "").lower()
    if expand_abbreviations:
        if s.endswith("str.") or s.endswith("g."):
            s = s[:-1] + "asse"
        if not hasattr(normalize_streetname, "abbreviations"):
            # preprocess abbr. and init static function variable
            normalize_streetname.abbreviations = {}
            for key, value in ABBREVIATIONS.items():
                new_key = normalize_streetname(key, False)
                new_value = normalize_streetname(value, False)
                if new_key in new_value:
                    normalize_streetname.abbreviations[new_value] = new_key
                else:
                    normalize_streetname.abbreviations[new_key] = new_value
            print(normalize_streetname.abbreviations)
        for key, value in normalize_streetname.abbreviations.items():
            s = s.replace(key, value)
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

def get_boundaries(filenames):
    minlat, minlon, maxlat, maxlon = None, None, None, None
    bb_tolerance = 0.001
    for filename in filenames:
        tree = ET.parse(filename)
        root = tree.getroot()
        bounds = root.find("bounds")
        file_minlat = float(bounds.get("minlat"))
        file_minlon = float(bounds.get("minlon"))
        file_maxlat = float(bounds.get("maxlat"))
        file_maxlon = float(bounds.get("maxlon"))
        if minlat is None:
            minlat = file_minlat
            minlon = file_minlon
            maxlat = file_maxlat
            maxlon = file_maxlon
        else:
            if file_minlat < minlat:
                minlat = file_minlat
            if file_minlon < minlon:
                minlon = file_minlon
            if file_maxlat > maxlat:
                maxlat = file_maxlat
            if file_maxlon > maxlon:
                maxlon = file_maxlon
    bb_size = get_distance((minlat, minlon), (maxlat, maxlon))
    if bb_size > 20000:
        sys.exit("Boundingbox too large (%s)" % bb_size)
    else:
        return (minlat-bb_tolerance, minlon-bb_tolerance, maxlat+bb_tolerance, maxlon+bb_tolerance)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if len(sys.argv) == 2:
            filenames = glob(sys.argv[1])
        else:
            filenames = sys.argv[1:]
        bounds = get_boundaries(filenames)
        addresses = get_existing_addresses(*bounds)
        alt_names = get_alternative_streetnames(*bounds)
        for street in list(addresses.keys()):
            for alternative in alt_names[street]:
                for housenumber in alternative:
                    addresses[alternative][housenumber].append(addresses[street][housenumber])
        for filename in filenames:
            if not "_filtered.osm" in filename:
                print(filename)
                filter_address_file(filename, addresses)