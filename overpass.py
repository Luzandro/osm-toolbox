#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import defaultdict
import overpy
from streetnames import normalize_streetname
OVERPASS_URL = None
LOCAL_OVERPASS_URL = "http://localhost/cgi-bin/overpass-api/interpreter"

def set_overpass_url(url):
    global OVERPASS_URL
    OVERPASS_URL = url

def use_local_overpass(local):
    if local:
        set_overpass_url(LOCAL_OVERPASS_URL)

def get_existing_addresses(minlat, minlon, maxlat, maxlon):
    api = overpy.Overpass(url=OVERPASS_URL)
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