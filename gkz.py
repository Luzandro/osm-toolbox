#!/usr/bin/env python3
# -*- coding: utf-8 -*-

BUNDESLAND = {
    "1": "Burgenland",
    "2": "Kärnten",
    "3": "Niederösterreich",
    "4": "Oberösterreich",
    "5": "Salzburg",
    "6": "Steiermark",
    "7": "Tirol",
    "8": "Vorarlberg",
    "9": "Wien"
}

BEZIRK = {
    "101": "Eisenstadt-Stadt",
    "102": "Rust-Stadt",
    "103": "Eisenstadt-Umgebung",
    "104": "Güssing",
    "105": "Jennersdorf",
    "106": "Mattersburg",
    "107": "Neusiedl_am_See",
    "108": "Oberpullendorf",
    "109": "Oberwart",
    "201": "Klagenfurt-Stadt",
    "202": "Villach-Stadt",
    "203": "Hermagor",
    "204": "Klagenfurt-Land",
    "205": "St.Veit_Glan",
    "206": "Spittal_Drau",
    "207": "Villach-Land",
    "208": "Völkermarkt",
    "209": "Wolfsberg",
    "210": "Feldkirchen",
    "301": "Krems-Stadt",
    "302": "St.Pölten-Stadt",
    "303": "Waidhofen_Ybbs-Stadt",
    "304": "Wr.Neustadt-Stadt",
    "305": "Amstetten",
    "306": "Baden",
    "307": "Bruck_Leitha",
    "308": "Gänserndorf",
    "309": "Gmünd",
    "310": "Hollabrunn",
    "311": "Horn",
    "312": "Korneuburg",
    "313": "Krems-Land",
    "314": "Lilienfeld",
    "315": "Melk",
    "316": "Mistelbach",
    "317": "Mödling",
    "318": "Neunkirchen",
    "319": "St.Pölten-Land",
    "320": "Scheibbs",
    "321": "Tulln",
    "322": "Waidhofen_Thaya",
    "323": "Wr.Neustadt-Land",
    "324": "Wien-Umgebung",
    "325": "Zwettl",
    "401": "Linz-Stadt",
    "402": "Steyr-Stadt",
    "403": "Wels-Stadt",
    "404": "Braunau_Inn",
    "405": "Eferding",
    "406": "Freistadt",
    "407": "Gmunden",
    "408": "Grieskirchen",
    "409": "Kirchdorf_Krems",
    "410": "Linz-Land",
    "411": "Perg",
    "412": "Ried_Innkreis",
    "413": "Rohrbach",
    "414": "Schärding",
    "415": "Steyr-Land",
    "416": "Urfahr-Umgebung",
    "417": "Vöcklabruck",
    "418": "Wels-Land",
    "501": "Salzburg-Stadt",
    "502": "Hallein",
    "503": "Salzburg-Umgebung",
    "504": "St.Johann_Pongau",
    "505": "Tamsweg",
    "506": "Zell_am_See",
    "601": "Graz-Stadt",
    "603": "Deutschlandsberg",
    "606": "Graz-Umgebung",
    "610": "Leibnitz",
    "611": "Leoben",
    "612": "Liezen",
    "614": "Murau",
    "616": "Voitsberg",
    "617": "Weiz",
    "620": "Murtal",
    "621": "Bruck-Mürzzuschlag",
    "622": "Hartberg-Fürstenfeld",
    "623": "Südoststeiermark",
    "701": "Innsbruck-Stadt",
    "702": "Imst",
    "703": "Innsbruck-Land",
    "704": "Kitzbühel",
    "705": "Kufstein",
    "706": "Landeck",
    "707": "Lienz",
    "708": "Reutte",
    "709": "Schwaz",
    "801": "Bludenz",
    "802": "Bregenz",
    "803": "Dornbirn",
    "804": "Feldkirch",
    "900": "Wien-Stadt",
    "901": "01-Innere_Stadt",
    "902": "02-Leopoldstadt",
    "903": "03-Landstraße",
    "904": "04-Wieden",
    "905": "05-Margareten",
    "906": "06-Mariahilf",
    "907": "07-Neubau",
    "908": "08-Josefstadt",
    "909": "09-Alsergrund",
    "910": "10-Favoriten",
    "911": "11-Simmering",
    "912": "12-Meidling",
    "913": "13-Hietzing",
    "914": "14-Penzing",
    "915": "15-Rudolfsheim-Fünfhaus",
    "916": "16-Ottakring",
    "917": "17-Hernals",
    "918": "18-Währing",
    "919": "19-Döbling",
    "920": "20-Brigittenau",
    "921": "21-Floridsdorf",
    "922": "22-Donaustadt",
    "923": "23-Liesing"
}

def get_bundesland(gkz):
    return BUNDESLAND[str(gkz)[0]]

def get_bezirk(gkz):
    return BEZIRK[str(gkz)[:3]]