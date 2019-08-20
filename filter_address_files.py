#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import xml.etree.cElementTree as ET
from math import cos, asin, sqrt
import sys
from glob import glob
import os
import argparse
from osm_files import get_boundaries
from haversine import get_distance, get_cross_track_distance
import overpass
from streetnames import normalize_streetname
import re
import enum

FILTERED_SUFFIX = "_filtered"

def filter_address_files(list_of_filenames):
    bounds = get_boundaries(list_of_filenames)
    addresses = overpass.get_existing_addresses(*bounds)
    alt_names = overpass.get_alternative_streetnames(*bounds)
    for street in list(addresses.keys()):
        for alternative in alt_names[street]:
            for housenumber in addresses[alternative]:
                addresses[street][housenumber].extend(addresses[alternative][housenumber])
            addresses[alternative] = addresses[street]
    overall_count = 0
    filtered_count = 0
    for filename in list_of_filenames:
        if not FILTERED_SUFFIX+".osm" in filename or filename.startswith("NOTES_"):
            print(filename)
            overall_count_file, filtered_count_file = filter_address_file(filename, addresses)
            overall_count += overall_count_file
            filtered_count += filtered_count_file
    return overall_count, filtered_count

def get_village_from_filename(filename):
    m = re.search("\d+_([^_]+)_", filename)
    return m.group(1)

def filter_address_file(filename, addresses):
    tree = ET.parse(filename)
    root = tree.getroot()
    overall_count = 0
    filtered_count = 0
    village = get_village_from_filename(filename)
    bounds = get_boundaries([filename])
    has_local_addresses = None
    streets = None
    place_exists = None

    for node in root.findall('node'):
        overall_count += 1
        tags = {}
        filtered = False
        for tag in node.findall('tag'):
            tags[tag.get("k")] = tag.get("v")
        has_fixme = "fixme" in tags
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
        if street in addresses:
            if has_local_addresses is None:
                has_local_addresses = True
            if housenumber in addresses[street]:
                p1 = (float(node.get("lat")), float(node.get("lon")))
                for adr in addresses[street][housenumber]:
                    p2 = (float(adr["lat"]), float(adr["lon"]))
                    dist = get_distance(p1, p2)
                    if dist < 150:
                        if ("city" in adr and adr["city"] != tags["addr:city"] and dist > 50 and 
                            "".join(c for c in adr["city"].lower() if c.isalnum()) != village):

                            # if city is set and differs (but isn't the village name) use higher threshold
                            fixme = "ähnliche Adresse in %dm Entfernung (addr:city = '%s' statt '%s')" % (dist, adr["city"], tags["addr:city"])
                            add_fixme(node, BevFixme.SIMILAR_ADR, fixme)
                            has_fixme = True
                            continue
                        root.remove(node)
                        filtered = True
                        filtered_count += 1
                        break
                    else:
                        fixme = "ähnliche Adresse in %dm Entfernung" % dist
                        has_fixme = add_fixme(node, BevFixme.SIMILAR_ADR, fixme)
        else:
            if SANITY_CHECKS and has_local_addresses is None:
                has_local_addresses = len(overpass.get_existing_addresses(*bounds)) > 0
        if SANITY_CHECKS and not (filtered or has_fixme):
            if has_local_addresses and len(overpass.get_existing_addresses_around(node.get("lat"), node.get("lon"))) > 0:
                has_fixme = add_fixme(node, BevFixme.CLOSE_ADR)
                continue
            if not "addr:place" in tags:
                # check streetname / distance
                if streets is None:
                    streets = overpass.get_streets_by_name(*bounds, street)
                if len(streets[0]) == 0:
                    if place_exists is None:
                        place_exists = overpass.place_exists(*bounds, street)
                    if place_exists:
                        has_fixme = add_fixme(node, BevFixme.ADDR_PLACE_NEEDED)
                    else:
                        if has_local_addresses or overpass.streets_exist(*bounds):
                            has_fixme = add_fixme(node, BevFixme.STREET_NOT_FOUND)
                        else:
                            has_fixme = add_fixme(node, BevFixme.NO_STREET_FOUND)
                    continue
                else:
                    # get nearest way
                    ways, nodes = streets
                    nearest_way = None
                    nearest_node = None
                    min_dist = None
                    for way in ways:
                        for i in range(len(way.nodes)):
                            #calculate distance to every node
                            p1 = (float(node.get("lat")), float(node.get("lon")))
                            p2 = (float(way.nodes[i].lat), float(way.nodes[i].lon))
                            dist = get_distance(p1, p2)
                            if min_dist is None or dist < min_dist:
                                min_dist = dist
                                nearest_node = i
                                nearest_way = way
                    nearest_node_tuple = (nearest_way.nodes[nearest_node].lat, nearest_way.nodes[nearest_node].lon)
                    address_location = (node.get("lat"), node.get("lon"))
                    if nearest_node > 0:
                        # check distance to way n-1 -> n
                        previous_node_tuple = (nearest_way.nodes[nearest_node-1].lat, nearest_way.nodes[nearest_node-1].lon)
                        dist = get_cross_track_distance(previous_node_tuple, nearest_node_tuple, address_location)
                        if min_dist is None or dist < min_dist:
                            min_dist = dist
                    if nearest_node < len(nearest_way.nodes) - 1:
                        # check distance to way n -> n+1
                        next_node_tuple = (nearest_way.nodes[nearest_node+1].lat, nearest_way.nodes[nearest_node+1].lon)
                        dist = get_cross_track_distance(nearest_node_tuple, next_node_tuple, address_location)
                        if min_dist is None or dist < min_dist:
                            min_dist = dist
                    if min_dist > 150:
                        has_fixme = add_fixme(node, BevFixme.DISTANT_STREET, "Straße weit entfernt (%dm)" % min_dist)
            #if not has_fixme:
                #if not overpass.is_building_nearby(node.get("lat"), node.get("lon")):
                    #has_fixme = add_fixme(node, BevFixme.NO_OSM_BUILDING)
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

class BevFixme(enum.Enum):
    NO_BUILDING = "Adresse ohne Gebäude oder Ident-Adresse"
    NO_OSM_BUILDING = "nicht innerhalb eines OSM-Gebäude"
    SIMILAR_ADR = "ähnliche Adresse in der Umgebung"
    CLOSE_ADR = "sehr nahe andere Adressen gefunden bzw. innerhalb eines Gebäudes/Bereichs mit anderer Adresse"
    NO_STREET_TAG = "Hausnummern ohne addr:street/addr:place in der Umgebung gefunden"
    PLACE_NOT_FOUND = "kein place namens '#NAME#' im Adressbereich gefunden"
    STREET_NOT_FOUND = "keine Straße namens '#NAME#' im Adressbereich gefunden"
    NO_STREET_FOUND = "keine Straße im Adressbereich gefunden"
    DISTANT_STREET = "Straße weit entfernt"
    ADDR_PLACE_NEEDED = "keine Straße aber ein Ort namens '#NAME#' im Adressbereich gefunden"

def add_fixme(node, category, text=None):
    if not SANITY_CHECKS:
        return False
    tags = {}
    for tag in node.findall('tag'):
        tags[tag.get("k")] = tag.get("v")
    if "addr:street" in tags:
        street = tags["addr:street"]
    else:
        street = tags["addr:place"]
    if not "fixme" in tags:
        ET.SubElement(node, "tag", k="fixme", v="BEV-Daten überprüfen")
    if text is None:
        text = category.value
        if category == BevFixme.PLACE_NOT_FOUND or category == BevFixme.STREET_NOT_FOUND or category == BevFixme.ADDR_PLACE_NEEDED:
            text = text.replace("#NAME#", street)
    ET.SubElement(node, "tag", k="fixme:BEV:%s" % category.name, v=text)
    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs=1, help="input directory")
    parser.add_argument("--local", action="store_true", help="use local overpass server (URL: %s)" % overpass.LOCAL_OVERPASS_URL, dest="local")
    parser.add_argument("--sanity_checks", action="store_true", help="validate data using various sanity checks", dest="sanity_checks")
    ARGS = parser.parse_args()
    SANITY_CHECKS = ARGS.sanity_checks
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
        
