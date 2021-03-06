#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import string

# vor der Anwendung wird noch eine allgemeine Normalisierung vorgenommen, 
# d.h. Groß-/Kleinschreibung, Abstände, oder Bindestriche sind z.B. egal
ABBREVIATIONS = {
    "Doktor": "Dr.",
    "Professor": "Prof.",
    "Pfarrer": "Pf.",
    "Pater": "P.",
    "Wiener": "Wr.",
    "Sankt": "St.",
    "von": "v.",
    "van": "v.",
    "Abt": "A.",
    "Architekt": "Arch.",
    "Bürgermeister": "Bgm.",
    "Bgmst.": "Bgm.",
    "Nationalrat": "NR.",
    "Dechant": "D.",
    "Ingenieur": "Ing.",
    "Schwester": "Sr.",
    "Zur": "Z.",
    "Weissenbach bei Mödling": "Weissenbach",
    "Kais.Elisabeth": "Kaiserin Elisabeth",
    "Beethoven": "Ludwig van Beethoven",
    "Schedyfka": "Wilhelm Schedyfka",
    "Rückert": "Friedrich Rückert",
    "Rosegger": "Peter Rosegger",
    "Nestroy": "Johann Nestroy",
    "Billroth": "Theodor Billroth"
}

NAMES = ('Ad.', 'Adam', 'Adalbert', 'Adolf', 'Alexander', 'Alfons', 'Alfred', 'Alois', 'Alphons', 'Amadeus', 'Amand', 'Ambros', 'Ant.', 'Anselm', 'Anton', 'Arthur', 'Aug.', 'August',
    'Balthasar', 'Bernhard', 'Bertha',
    'Christoph', 'Clemens', 'Conrad',
    'Egon', 'Engelbert',
    'Felix', 'Ferd.', 'Ferdinand', 'Franz', 'Fr.', 'Friedr.', 'Friedrich',
    'Georg', 'Gottfr.', 'Gottfried', 'Gottlieb', 'Gustav',
    'Hans', 'Heinr.', 'Heinrich', 'Herbert', 'Hertha', 'Herta', 'Hironimus', 'Hugo', 
    'Isolde',
    'Jakob', 'Joh.', 'Johann', 'Josef', 'Joseph', 'Julius',
    'Karl', 
    'Leop.', 'Leopold', 'Ludwig',
    'Maria', 'Mathias', 'Max', 'Michael', 'Moritz', 'Mich.', 'Michel',
    'Nikolaus',
    'Oskar', 'Ottokar', 'Otto',
    'Richard', 'Robert', 'Rudolf', 
    'Sebastian', 
    'Theodor',
    'Viktor',
    'Walter', 'Wenzel', 'Wilhelm', 'Wolfgang', 
    'Xaver',
    'Zach.', 'Zacharias')

''' strips whitespace/dash, ß->ss, ignore case '''
def normalize_streetname(street, expand_abbreviations=True, ignore_street_postfix=False):
    valid_chars = string.ascii_letters + string.digits + "üäö.,()/;+ -'\"*`"
    translation_table = str.maketrans("áčéěëèíóőřšúž*`", "aceeeeioorsuz  ")
    s = street.replace("ß", "ss").lower()
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
    s = s.replace(" ", "").replace("-", "").replace("'", "").replace('"', "").lower()
    if ignore_street_postfix:
        if s.endswith("strasse"):
            s = s[:-7]
        elif s.endswith("gasse"):
            s = s[:-5]
        elif s.endswith("weg"):
            s = s[:-3]
    return s