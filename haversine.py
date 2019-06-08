#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from math import cos, asin, sqrt, sin, atan2, pi, radians, degrees
# see: https://www.movable-type.co.uk/scripts/latlong.html

EARTH_RADIUS = 6371000

def get_distance(point1, point2):
    lat1, lon1 = (float(x) for x in point1)
    lat2, lon2 = (float(x) for x in point2)
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2-lat1)
    delta_lambda = radians(lon2-lon1)
    a = sin(delta_phi/2) * sin(delta_phi/2) + cos(phi1) * cos(phi2) * sin(delta_lambda/2) * sin(delta_lambda/2)
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return EARTH_RADIUS * c

def bearing(point1, point2):
    lat1, lon1 = (float(x) for x in point1)
    lat2, lon2 = (float(x) for x in point2)
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2-lat1)
    delta_lambda = radians(lon2-lon1)
    y = sin(delta_lambda) * cos(phi2)
    x = cos(phi1) * sin(phi2) - sin(phi1)*cos(phi2)*cos(delta_lambda)
    return degrees(atan2(y,x)+360) % 360

def get_cross_track_distance(start, end, point):
    delta_13 = get_distance(start, point) / EARTH_RADIUS
    theta_13 = bearing(start, point)
    theta_12 = bearing(start, end)
    return abs(asin(sin(delta_13) * sin(radians(theta_13 - theta_12))) * EARTH_RADIUS)

if __name__ == "__main__":
    p1 = (48.0395233, 16.4363301)
    p2 = (48.0404657, 16.4362577)
    p3 = (48.0399806, 16.4363636)

    print(get_distance(p1, p2)) # should be around 105 meters
    print(get_cross_track_distance(p1,p2,p3)) # should be around 5 meters
