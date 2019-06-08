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

def _get_existing_addresses(query):
    api = overpy.Overpass(url=OVERPASS_URL)
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

def get_existing_addresses_around(lat, lon, distance=3.0):
    query = 'nwr["addr:housenumber"](around: %s,%s,%s);out center;' % (distance, lat, lon)
    return _get_existing_addresses(query)

def get_existing_addresses(minlat, minlon, maxlat, maxlon):
    query = 'nwr["addr:housenumber"](%s,%s,%s,%s);out center;' % (minlat, minlon, maxlat, maxlon)
    return _get_existing_addresses(query)

def get_alternative_streetnames(minlat, minlon, maxlat, maxlon, normalize_streetnames = True, add_inverse = False):
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
            if add_inverse:
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
            if add_inverse:
                alt_names[official_name].add(name)
        except ValueError:
            error_file = open("invalid_characters.txt", "a+")
            error_file.write("%s %s (official_name)\n\n" % (way.tags["official_name"], way.tags["name"]))
            error_file.close()
    return alt_names

def get_nearby_streets(lat, lon, distance=100):
    api = overpy.Overpass(url=OVERPASS_URL)
    result = api.query("way[highway~'residential|unclassified|primary|secondary|tertiary|service'](around: %s,%s,%s);out;" % (distance, lat, lon))
    return result.ways

def get_housenumbers_without_streetname(minlat, minlon, maxlat, maxlon):
    api = overpy.Overpass(url=OVERPASS_URL)
    result = api.query("nwr['addr:housenumber'][!'addr:street'][!'addr:place'](%s,%s,%s,%s);out;" % (minlat, minlon, maxlat, maxlon))
    housenumbers = []
    housenumbers.extend(result.nodes)
    housenumbers.extend(result.ways)
    housenumbers.extend(result.relations)
    return housenumbers

def place_exists(minlat, minlon, maxlat, maxlon, name):
    api = overpy.Overpass(url=OVERPASS_URL)
    bounds = "%s,%s,%s,%s" % (minlat, minlon, maxlat, maxlon)
    result = api.query("(nwr[place][name='%s'](%s);nwr[place]['name:de'='%s'](%s);nwr[place]['short_name'='%s'](%s);nwr[place][alt_name='%s'](%s);nwr[place][official_name='%s'](%s););out;" % (name, bounds, name, bounds, name, bounds, name, bounds, name, bounds))
    return (len(result.nodes) + len(result.ways) + len(result.relations) > 0)

def get_streets_by_name(minlat, minlon, maxlat, maxlon, name):
    api = overpy.Overpass(url=OVERPASS_URL)
    bounds = "%s,%s,%s,%s" % (minlat, minlon, maxlat, maxlon)
    query = """way[highway](%s);(._;>;);out;""" % bounds
    #print(query)
    result = api.query(query)
    ways = []
    nodes = {}
    for way in result.ways:
        try:
            if "name" in way.tags and normalize_streetname(way.tags["name"]) == normalize_streetname(name):
                ways.append(way)
            elif "alt_name" in way.tags and normalize_streetname(way.tags["alt_name"]) == normalize_streetname(name):
                ways.append(way)
            elif "official_name" in way.tags and normalize_streetname(way.tags["official_name"]) == normalize_streetname(name):
                ways.append(way)
            elif "short_name" in way.tags and normalize_streetname(way.tags["short_name"]) == normalize_streetname(name):
                ways.append(way)
        except ValueError:
            pass
    for node in result.nodes:
        nodes[node.id] = node
    return (ways, nodes)