#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import xml.etree.cElementTree as ET
from math import cos, asin, sqrt
import sys
from glob import glob
import os
import argparse
from osm_files import get_boundaries
from haversine import get_distance
import overpass
from streetnames import normalize_streetname

FILTERED_SUFFIX = "_filtered"

# TODO: addr:units
def filter_address_files(list_of_filenames):
    bounds = get_boundaries(list_of_filenames)
    addresses = overpass.get_existing_addresses(*bounds)
    alt_names = overpass.get_alternative_streetnames(*bounds)
    for street in list(addresses.keys()):
        for alternative in alt_names[street]:
            for housenumber in alternative:
                addresses[alternative][housenumber].append(addresses[street][housenumber])
    overall_count = 0
    filtered_count = 0
    for filename in list_of_filenames:
        if not FILTERED_SUFFIX+".osm" in filename or filename.startswith("NOTES_"):
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
    filtered_directory = "%s%s" % (directory, FILTERED_SUFFIX)
    if not os.path.exists(filtered_directory):
        os.mkdir(filtered_directory)
    filtered_filename = "%s%s.osm" % (filename[:-4], FILTERED_SUFFIX)
    filtered_path = os.path.join(filtered_directory, filtered_filename)
    if not root.find('node') is None:
        tree.write(filtered_path)
    elif os.path.exists(filtered_path):
        os.remove(filtered_path)
        # TODO: directory empty?
    return filtered_count, overall_count


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs=1, help="input directory")
    parser.add_argument("--local", action="store_true", help="use local overpass server (URL: %s)" % overpass.LOCAL_OVERPASS_URL, dest="local")
    ARGS = parser.parse_args()
    overpass.use_local_overpass(ARGS.local)
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
        
