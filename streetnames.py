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
    "Bürgermeister": "Bgm.",
    "Dechant": "D.",
    "Ingenieur": "Ing.",
    "Schwester": "Sr.",
    "Weissenbach bei Mödling": "Weissenbach",
    "Kais.Elisabeth": "Kaiserin Elisabeth",
    "Beethoven": "Ludwig van Beethoven",
    "Schedyfka": "Wilhelm Schedyfka",
    "Rückert": "Friedrich Rückert",
}

NAMES = ('Adam', 'Adolf', 'Alexander', 'Alfred', 'Alois', 'Alphons', 'Amadeus', 'Ambros', 'Anton', 'Arthur',
    'Balthasar', 'Bernhard', 'Bertha',
    'Christoph', 'Clemens', 'Conrad',
    'Engelbert',
    'Felix', 'Ferd.', 'Ferdinand', 'Franz', 'Friedrich',
    'Georg', 'Gottfr.', 'Gottfried', 'Gustav',
    'Hans', 'Heinr.', 'Heinrich', 'Herbert', 'Hugo', 
    'Isolde',
    'Jakob', 'Joh.', 'Johann', 'Josef', 'Joseph', 
    'Karl', 
    'Leop.', 'Leopold', 'Ludwig',
    'Maria', 'Mathias', 'Max', 'Michael', 'Moritz',
    'Oskar', 'Ottokar', 'Otto',
    'Richard', 'Robert', 'Rudolf', 
    'Sebastian', 
    'Theodor',
    'Walter', 'Wenzel', 'Wilhelm', 'Wolfgang', 
    'Xaver',
    'Zach.', 'Zacharias')

''' strips whitespace/dash, ß->ss, ignore case '''
def normalize_streetname(street, expand_abbreviations=True):
    valid_chars = string.ascii_letters + string.digits + "üäö.,()/;"
    translation_table = str.maketrans("áčéěëèíóőřšúž", "aceeeeioorsuz")
    s = street.replace("ß", "ss").replace(" ", "").replace("-", "").replace("'", "").lower()
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
    return s