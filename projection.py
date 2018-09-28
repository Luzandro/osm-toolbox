#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from osgeo import osr
from osgeo import ogr
from math import cos, asin, sqrt

targetRef = osr.SpatialReference()
targetRef.ImportFromEPSG(4326)

westRef = osr.SpatialReference()
westRef.ImportFromEPSG(31254)
centerRef = osr.SpatialReference()
centerRef.ImportFromEPSG(31255)
eastRef = osr.SpatialReference()
eastRef.ImportFromEPSG(31256)

westTransform = osr.CoordinateTransformation(westRef, targetRef)
centralTransform = osr.CoordinateTransformation(centerRef, targetRef)
eastTransfrom = osr.CoordinateTransformation(eastRef, targetRef)

def reproject(sourceCRS, point):
    """This function reprojects an array of coordinates (a point) to the desired CRS
    depending on their original CRS given by the parameter sourceCRS"""
    point = ogr.CreateGeometryFromWkt("POINT ({} {})".format(point[0], point[1]))
    if sourceCRS == '31254':
        point.Transform(westTransform)
    elif sourceCRS == '31255':
        point.Transform(centralTransform)
    elif sourceCRS == '31256':
        point.Transform(eastTransfrom)
    else:
        print("unkown CRS: {}".format(sourceCRS))
        return([0, 0])
    wktPoint = point.ExportToWkt()
    transformedPoint = wktPoint.split("(")[1][:-1].split(" ")
    del(point)

    return [round(float(p), 6) for p in transformedPoint]

def get_distance(point1, point2):
    return _get_distance_haversine(point1, point2)

def _get_distance_haversine(point1, point2):
    lat1, lon1 = point1
    lat2, lon2 = point2
    p = 0.017453292519943295     #Pi/180
    a = 0.5 - cos((lat2 - lat1) * p)/2 + cos(lat1 * p) * cos(lat2 * p) * (1 - cos((lon2 - lon1) * p)) / 2
    return 12742 * asin(sqrt(a)) * 1000 #2*R*asin...

def _get_distance_osgeo_reprojection(point1, point2):
    # Note: 
    # results from this function differ quite significantly (nearly a factor 2)
    # from the haversine calculation. While it should probably be more accurate
    # as it's using local EPSG, I prefer haversine nevertheless, as it's more
    # consistent with the values, that JOSM is showing
    if point1[0] < 11.83:
        coordTransformation = osr.CoordinateTransformation(targetRef, westRef)
    elif point1[0] > 14.83:
        coordTransformation = osr.CoordinateTransformation(targetRef, eastRef)
    else:
        coordTransformation = osr.CoordinateTransformation(targetRef, centerRef)
    p1 = ogr.CreateGeometryFromWkt("POINT ({} {})".format(point1[0], point1[1]))
    p1.Transform(coordTransformation)
    p2 = ogr.CreateGeometryFromWkt("POINT ({} {})".format(point2[0], point2[1]))
    p2.Transform(coordTransformation)
    return p1.Distance(p2)
    
