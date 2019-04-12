#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import xml.etree.cElementTree as ET

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
    return (minlat-bb_tolerance, minlon-bb_tolerance, maxlat+bb_tolerance, maxlon+bb_tolerance)