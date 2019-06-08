#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import xml.etree.cElementTree as ET
import os
import argparse
import overpass

def find_fixmes(list_of_filenames, fixmes):
    for filename in list_of_filenames:
        tree = ET.parse(filename)
        for node in tree.getroot().findall('node'):
            if node.find("tag[@k='fixme']") is not None:
                fixmes[(node.get("lat"), node.get("lon"))] = node
    return fixmes

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs=1, help="directory containing BEV files with fixme notes")
    ARGS = parser.parse_args()
    overpass.use_local_overpass(False)
    if os.path.isdir(ARGS.directory[0]):
        fixmes = {}
        for root, dirs, files in os.walk(ARGS.directory[0]):
            if len(dirs) == 0 and len(files) > 0:
                print(root)
                find_fixmes([os.path.join(root, f) for f in files], fixmes)
        tree = ET.parse("import_fail.osm")
        root = tree.getroot()
        for node in root.findall('node'):
            coords = (node.get("lat"), node.get("lon"))
            if coords in fixmes.keys():
                for tag in fixmes[coords].findall('tag'):
                    if tag.get("k").startswith("fixme:BEV"):
                        ET.SubElement(node, "tag", k=tag.get("k"), v=tag.get("v"))
            else:
                root.remove(node)
        tree.write("repair_import.osm")
        
