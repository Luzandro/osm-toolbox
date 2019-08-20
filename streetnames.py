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
    "Architekt": "Arch.",
    "Bürgermeister": "Bgm.",
    "Nationalrat": "NR.",
    "Dechant": "D.",
    "Ingenieur": "Ing.",
    "Schwester": "Sr.",
    "Weissenbach bei Mödling": "Weissenbach",
    "Kais.Elisabeth": "Kaiserin Elisabeth",
    "Beethoven": "Ludwig van Beethoven",
    "Schedyfka": "Wilhelm Schedyfka",
    "Rückert": "Friedrich Rückert",
    "Rosegger": "Peter Rosegger",
    "Nestroy": "Johann Nestroy",
    "Billroth": "Theodor Billroth"
}

NAMES = ('Adam', 'Adolf', 'Alexander', 'Alfons', 'Alfred', 'Alois', 'Alphons', 'Amadeus', 'Ambros', 'Ant.', 'Anton', 'Arthur', 'Aug.', 'August',
    'Balthasar', 'Bernhard', 'Bertha',
    'Christoph', 'Clemens', 'Conrad',
    'Engelbert',
    'Felix', 'Ferd.', 'Ferdinand', 'Franz', 'Fr.', 'Friedr.', 'Friedrich',
    'Georg', 'Gottfr.', 'Gottfried', 'Gottlieb', 'Gustav',
    'Hans', 'Heinr.', 'Heinrich', 'Herbert', 'Hertha', 'Herta', 'Hugo', 
    'Isolde',
    'Jakob', 'Joh.', 'Johann', 'Josef', 'Joseph', 
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
def normalize_streetname(street, expand_abbreviations=True):
    valid_chars = string.ascii_letters + string.digits + "üäö.,()/;+ -'"
    translation_table = str.maketrans("áčéěëèíóőřšúž", "aceeeeioorsuz")
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
    s = s.replace(" ", "").replace("-", "").replace("'", "").lower()
    return s