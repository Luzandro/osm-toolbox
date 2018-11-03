#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
