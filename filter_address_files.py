#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import xml.etree.cElementTree as ET
from collections import defaultdict
from math import cos, asin, sqrt
import overpy
import sys
from glob import glob
import os
import argparse
from abbreviations import ABBREVIATIONS, NAMES
import string

LOCAL_OVERPASS_URL = "http://localhost/cgi-bin/overpass-api/interpreter"
# TODO: addr:units
# TODO: Non ASCII characters like Esterházy

def get_existing_addresses(minlat, minlon, maxlat, maxlon):
    api = overpy.Overpass(url=OVERPASS_URL)
    query = 'nwr["addr:housenumber"](%s,%s,%s,%s);out center;' % (minlat, minlon, maxlat, maxlon)
    #print(query)
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
        try:
            street = normalize_streetname(street)
        except ValueError:
            error_file = open("invalid_characters.txt", "a+")
            error_file.write("%s %s %s %s\n\n" % (street, addr.id, addr.__class__, str(addr.tags)))
            error_file.close()
        housenumber = addr.tags["addr:housenumber"].lower()

        address = {'lat': addr.lat, 'lon': addr.lon}
        if "addr:city" in addr.tags:
            address["city"] = addr.tags["addr:city"]
        if "addr:unit" in addr.tags:
            address["unit"] = addr.tags["addr:unit"]
        elif "/" in housenumber:
            housenumber, address["unit"] = housenumber.split("/", 1)
        addresses[street][housenumber].append(address)

        # add single addresses for (simple) address ranges to existing addresses
        # i.e. for the existing address "49-51" add "49-51", "49" and "51"
        if "-" in housenumber:
            try:
                lower_bound, upper_bound = [int(n) for n in housenumber.split("-", 1)]
                for n in range(lower_bound, upper_bound+1, 2):
                    addresses[street][n].append(address)
            except ValueError:
                pass

    return addresses

def filter_address_files(list_of_filenames):
    bounds = get_boundaries(list_of_filenames)
    addresses = get_existing_addresses(*bounds)
    alt_names = get_alternative_streetnames(*bounds)
    for street in list(addresses.keys()):
        for alternative in alt_names[street]:
            for housenumber in alternative:
                addresses[alternative][housenumber].append(addresses[street][housenumber])
    overall_count = 0
    filtered_count = 0
    for filename in list_of_filenames:
        if not "_filtered.osm" in filename or filename.startswith("NOTES_"):
            print(filename)
            overall_count_file, filtered_count_file = filter_address_file(filename, addresses)
            overall_count += overall_count_file
            filtered_count += filtered_count_file
    return overall_count, filtered_count

def filter_address_file(filename, addresses):
    tree = ET.parse(filename)
    root = tree.getroot()
    overall_count = 0
    filtered_count = 0

    for node in root.findall('node'):
        overall_count += 1
        tags = {}
        for tag in node.findall('tag'):
            tags[tag.get("k")] = tag.get("v")
        if "addr:street" in tags:
            street = tags["addr:street"]
        else:
            street = tags["addr:place"]
        try:
            street = normalize_streetname(street)
        except ValueError:
            error_file = open("invalid_characters.txt", "a+")
            error_file.write("%s %s\n" % (street, str(tags)))
            error_file.close()
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
                    filtered_count += 1
                    break
    directory, filename = os.path.split(os.path.abspath(filename))
    filtered_directory = "%s_filtered" % directory
    if not os.path.exists(filtered_directory):
        os.mkdir(filtered_directory)
    filtered_filename = "%s_filtered.osm" % filename[:-4]
    filtered_path = os.path.join(filtered_directory, filtered_filename)
    #filtered_filename = '%s_filtered.osm' % filename[:-4]
    if not root.find('node') is None:
        tree.write(filtered_path)
    elif os.path.exists(filtered_path):
        os.remove(filtered_path)
        # TODO: directory empty?
    return filtered_count, overall_count

''' strips whitespace/dash, ß->ss, ignore case '''
def normalize_streetname(street, expand_abbreviations=True):
    valid_chars = string.ascii_letters + string.digits + "üäö.,()/;"
    translation_table = str.maketrans("áčéěëèíóőřšúž", "aceeeeioorsuz")
    s = street.replace("ß", "ss").replace(" ", "").replace("-", "").replace("'", "").lower()
    s = s.replace("\xa0", "") # non breaking space
    s = s.replace("&", "+")
    s = s.translate(translation_table)
    if expand_abbreviations:
        if s.endswith("str.") or s.endswith("g."):
            s = s[:-1] + "asse"
        if not hasattr(normalize_streetname, "abbreviations"):
            # preprocess abbr. and init static function variable
            normalize_streetname.abbreviations = {}
            for key, value in ABBREVIATIONS.items():
                new_key = normalize_streetname(key, False)
                new_value = normalize_streetname(value, False)
                # use shortened version for comparison as this is unambiguous
                if len(new_key) < len(new_value):
                    normalize_streetname.abbreviations[new_value] = new_key
                else:
                    normalize_streetname.abbreviations[new_key] = new_value
            for name in NAMES:
                name = name.lower()
                if name.startswith("th"):
                    normalize_streetname.abbreviations[name] = 'th.'
                else:
                    normalize_streetname.abbreviations[name] = name[0] + '.'
            #print(normalize_streetname.abbreviations)
        for key, value in normalize_streetname.abbreviations.items():
            s = s.replace(key, value)
    if not all([char in valid_chars for char in s]):
        raise ValueError("non ascii character found in street name: ", s)
    return s

def get_alternative_streetnames(minlat, minlon, maxlat, maxlon, normalize_streetnames = True):
    if normalize_streetnames:
        normalize = normalize_streetname
    else:
        normalize = lambda x : x
    alt_names = defaultdict(set)
    api = overpy.Overpass(url=OVERPASS_URL)
    result = api.query('way[highway][alt_name][name](%s,%s,%s,%s);out;' % (minlat, minlon, maxlat, maxlon))
    for way in result.ways:
        try:
            name = normalize(way.tags["name"])
            alt_name = normalize(way.tags["alt_name"])
            alt_names[name].add(alt_name)
            alt_names[alt_name].add(name)
        except ValueError:
            error_file = open("invalid_characters.txt", "a+")
            error_file.write("%s %s (alt_name)\n\n" % (way.tags["alt_name"], way.tags["name"]))
            error_file.close()
    result = api.query('way[highway][official_name](%s,%s,%s,%s);out;' % (minlat, minlon, maxlat, maxlon))
    for way in result.ways:
        try:
            name = normalize(way.tags["name"])
            official_name = normalize(way.tags["official_name"])
            alt_names[name].add(official_name)
            alt_names[official_name].add(name)
        except ValueError:
            error_file = open("invalid_characters.txt", "a+")
            error_file.write("%s %s (official_name)\n\n" % (way.tags["official_name"], way.tags["name"]))
            error_file.close()
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
    if bb_size > 27000 and not ARGS.local:
        sys.exit("Boundingbox too large (%s)" % bb_size)
    else:
        return (minlat-bb_tolerance, minlon-bb_tolerance, maxlat+bb_tolerance, maxlon+bb_tolerance)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs=1, help="input directory")
    parser.add_argument("--local", action="store_true", help="use local overpass server (URL: %s)" % LOCAL_OVERPASS_URL, dest="local")
    ARGS = parser.parse_args()
    if ARGS.local:
        OVERPASS_URL = LOCAL_OVERPASS_URL
    else:
        OVERPASS_URL = None
    if os.path.isdir(ARGS.directory[0]):
        overall_count = 0
        filtered_count = 0
        for root, dirs, files in os.walk(ARGS.directory[0]):
            dirs[:] = [d for d in dirs if not d.endswith("filtered")]
            if len(dirs) == 0 and len(files) > 0:
                print(root)
                overall_count_dir, filtered_count_dir = filter_address_files([os.path.join(root, f) for f in files])
                overall_count += overall_count_dir
                filtered_count += filtered_count_dir
                try:
                    print("%d / %d nodes filtered (%d%%)" % (overall_count_dir,filtered_count_dir,(float(overall_count_dir)/filtered_count_dir*100)))
                except ZeroDivisionError:
                    pass
        print("\nOverall:\n%d / %d nodes filtered (%d%%)" % (overall_count,filtered_count,(float(overall_count)/filtered_count*100)))
        
