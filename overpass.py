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

def get_existing_addresses_around(lat, lon, distance=6.0):
    query = 'nwr["addr:housenumber"](around: %s,%s,%s);out center;' % (distance, lat, lon)
    return _get_existing_addresses(query)

def is_building_nearby(lat, lon, distance=3.0):
    query = 'nwr[building](around: %s,%s,%s);out center;' % (distance, lat, lon)
    api = overpy.Overpass(url=OVERPASS_URL)
    result = api.query(query)
    return (len(result.ways) + len(result.relations) > 0)

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

def admin_boundary_exists(minlat, minlon, maxlat, maxlon, name):
    api = overpy.Overpass(url=OVERPASS_URL)
    bounds = "%s,%s,%s,%s" % (minlat, minlon, maxlat, maxlon)
    query = """relation[boundary=administrative](%s);out;""" % bounds
    result = api.query(query)
    for boundary in result.relations:
        for tag in ("name", "name:de", "alt_name", "official_name", "short_name"):
            try:
                if tag in boundary.tags:
                    if boundary.tags[tag].startswith("Gemeinde "):
                        boundary_name = boundary.tags[tag][9:]
                    else:
                        boundary_name = boundary.tags[tag]
                    if boundary_name == name:
                        return True
            except ValueError:
                # ignore boundaries with unsupported characters
                pass
    return False
    

def place_exists(minlat, minlon, maxlat, maxlon, name, tolerance=0, ignore_postfix=False):
    api = overpy.Overpass(url=OVERPASS_URL)
    bounds = "%s,%s,%s,%s" % (minlat-tolerance, minlon-tolerance, maxlat+tolerance, maxlon+tolerance)
    query = """nwr[place](%s);out;""" % bounds
    result = api.query(query)
    places = []
    places.extend(result.nodes)
    places.extend(result.ways)
    places.extend(result.relations)
    for place in places:
        for tag in ("name", "name:de", "alt_name", "official_name", "short_name", "full_name"):
            try:
                if tag in place.tags:
                    search_name = name
                    found_name = place.tags[tag]
                    if ignore_postfix:
                        for postfix in ["im", "in", "am", "bei", "an der"]:
                            if " %s " % postfix in search_name:
                                search_name = search_name[:search_name.index(postfix)-1]
                            if " %s " % postfix in found_name:
                                found_name = found_name[:found_name.index(postfix)-1]
                    if normalize_streetname(search_name) == normalize_streetname(found_name):
                        return True
            except ValueError:
                # ignore places with unsupported characters
                pass
    return False

def streets_exist(minlat, minlon, maxlat, maxlon):
    api = overpy.Overpass(url=OVERPASS_URL)
    bounds = "%s,%s,%s,%s" % (minlat, minlon, maxlat, maxlon)
    result = api.query("way[highway](%s);out;" % bounds)
    return (len(result.ways) > 0)

def get_streets_by_name(minlat, minlon, maxlat, maxlon, name, tolerance=0):
    api = overpy.Overpass(url=OVERPASS_URL)
    bounds = "%s,%s,%s,%s" % (minlat-tolerance, minlon-tolerance, maxlat+tolerance, maxlon+tolerance)
    query = """way[highway](%s);(._;>;);out;""" % bounds
    result = api.query(query)
    ways = []
    nodes = {}
    for way in result.ways:
        for tag in ("name", "name:de", "alt_name", "official_name", "short_name", "name:left", "name:right"):
            try:
                if tag in way.tags and normalize_streetname(way.tags[tag]) == normalize_streetname(name):
                    ways.append(way)
            except ValueError:
                # ignore ways with unsupported characters
                pass
    for node in result.nodes:
        nodes[node.id] = node
    return (ways, nodes)

if __name__ == '__main__':
    api = overpy.Overpass(url=OVERPASS_URL)
    query = """[timeout:600];nwr["addr:housenumber"](area:3600052345);out;"""
    result = api.query(query)
    print(len(result.nodes) + len(result.ways) + len(result.relations))
