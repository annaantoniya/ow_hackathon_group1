"""Inhalt der Startseite. Hier lassen sich alle Texte ändern, ohne app.py anzufassen.

Alles hier ist ein Entwurf der Gruppe und keine Messung. Personas und Bewertungen sind erfunden und stehen auf der
Seite ausdrücklich als fiktiv. Das Modell bewertet Standorte nach Zielgruppe und Wettbewerb. Kassenfreier Einkauf,
Sortiment und Lieferung ändern den Standort-Score nicht, sondern das Format des Ladens.
"""

# Arbeitstitel. Alle Buchstaben stecken in "Oliver Wyman". Alternativen mit der gleichen Eigenschaft: LEMON, MELON, VINO.
MARKE = "OLIVE"
BEZEICHNUNG = "Urbaner Supermarkt mit Deli"
VOLLER_NAME = "OLIVER WYMAN"
CLAIM = "Grab. Go. Gather."
UNTERZEILE = "Frisch von morgens bis Mitternacht. Keine Kasse, keine Warteschlange."
VERANSTALTUNG = "Oliver Wyman × STADS Hackathon · 8. Oktober 2026"

BUSINESS_FRAGE = ("In welchen Stadtteilen von München, Frankfurt und Berlin findet ein neuer Laden dieser Art "
                  "am meisten Nachfrage, die der Handel heute nicht bedient?")

# Bilder: Die App sucht unter assets/bilder/<schluessel>.jpg (oder .png/.webp). Fehlt die Datei, steht eine Farbfläche
# mit "Bild folgt". Die Prompts für die Bilder stehen in Bild_Prompts_Nano_Banana.md.
HERO_BILD = "hero"

# Einleitung nach dem Vorbild von M&S Food: große Überschrift, Linie, Einleitungstext, rechts das Logo
INTRO_TITEL = "Frisches Essen, schnell. Auch spät und ohne Warteschlange."
INTRO_UNTERSTRICHEN = "spät"
INTRO_TEXT = ("OLIVE ist ein urbaner Supermarkt mit Deli-Theke. Tagsüber holen Berufstätige hier Kaffee, Pastries und ein gesundes "
              "Mittagessen. Abends kaufen Anwohner frisches Brot, Käse, vegane und vegetarische Gerichte und etwas Gutes zu trinken. "
              "Bezahlt wird per App, ohne Kasse.")

# Vorteile in der Streifenzeile, nach dem Vorbild von Waitrose. Symbol: phone, clock, moon, bag oder leaf
USPS = [
    ("phone", "Bezahlen per App", "Einchecken, mitnehmen, fertig. Es gibt keine Kasse."),
    ("clock", "Keine Warteschlange", "Auch zur Stoßzeit ohne Anstehen."),
    ("moon", "Bis spät frisch", "Brot und Pastries auch am Abend."),
    ("bag", "Lieferung", "Über Plattformen, ohne eigene Fahrer."),
    ("leaf", "Vegan und vegetarisch", "Große pflanzliche Auswahl."),
]

# Wertversprechen: zwei Kacheln, links Farbfläche mit Text, rechts Bild mit Plakette
WERT = [
    {"farbe": "#0B1B4D", "titel": "Grab & go für den Arbeitstag",
     "text": "Frische Sandwiches, Säfte und Snacks für den Weg zwischen zwei Terminen. In der App bezahlen und einfach gehen.",
     "plakette": ["No", "checkout"], "bild": "wert_tag"},
    {"farbe": "#002C77", "titel": "Hochwertige Snacks für den Abend",
     "text": "Brot, Käse, Aufschnitt, Oliven, Nüsse, Obst und Wein, auch noch spät. Für Besuch, Picknick und den spontanen Abend.",
     "plakette": ["Fresh", "bread, late"], "bild": "wert_abend"},
]

# Sortiment: sechs Karten mit Bild (Titel, Text, Bildschlüssel)
SORTIMENT = [
    ("Italienisch", "Belegte Ciabatta und Panini mit Hähnchen, Avocado, Schinken und Tomate, dazu frische Pasta und Antipasti.", "italienisch"),
    ("Mediterran", "Mezze, Hummus, griechischer Salat mit Feta, gegrilltes Gemüse, Oliven und Brot.", "mediterran"),
    ("Französische Bäckerei", "Pain au chocolat, Palmiers, Pastéis de nata und süße Pastries, frisch gebacken und auch abends noch da.", "franzoesisch"),
    ("Frisch zum Mitnehmen", "Salate, Wraps, frisch gepresste Säfte und Joghurt-Becher aus der Kühltheke, für unterwegs.", "regional"),
    ("Bowls & Salate", "Açaí, Poke und saisonale Salate. Große vegane und vegetarische Auswahl.", "bowls"),
    ("Drinks & Cocktails", "Frische Cocktails, Mocktails und Limonaden mit Minze, Beeren und Zitrus, dazu Naturwein und Craft Beer zum Mitnehmen.", "drinks"),
]

# Die Beschreibung der Stadt ist eine Hypothese, abgeleitet aus der Spec (Abschnitt 2).
STAEDTE = [
    {"key": "frankfurt", "name": "Frankfurt", "bild": "assets/staedte/frankfurt.jpg",
     "text": "Viele Pendler und Büros. Trägt die Tagesbevölkerung allein einen Standort?"},
    {"key": "berlin", "name": "Berlin", "bild": "assets/staedte/berlin.jpg",
     "text": "Viele Zentren und viele kleine Haushalte. Hält das Kaufkraft-Signal bei niedrigen Mieten?"},
    {"key": "muenchen", "name": "München", "bild": "assets/staedte/muenchen.jpg",
     "text": "Hohe Kaufkraft fast überall. Findet das Modell trotzdem Unterschiede?"},
]

# Foto: optional. Legt eine Bilddatei unter dem Pfad ab, dann erscheint sie statt der Initialen (siehe Persona_Bild_Prompts.md).
PERSONAS = [
    {
        "stadt": "Frankfurt", "name": "Christina", "alter": "45", "rolle": "Consultant", "kuerzel": "C",
        "foto": "assets/personas/christina.jpg",
        "sterne": 5, "titel": "Endlich ein Kaffee vor dem Daily, der nicht nach Tankstelle schmeckt",
        "text": "Morgens hole ich mir hier einen guten Kaffee und ein frisches Pastry, nichts Teures, aber richtig gut. "
                "Fürs Büro bestellen wir hier Snacks, die besser sind als der Standardkarton aus dem Supermarkt. "
                "Bezahlt ist in zehn Sekunden.",
        "signale": ["Büros", "Haltestellen"], "quelle": "OpenStreetMap", "modell": "Potenzial der Tagesbevölkerung",
    },
    {
        "stadt": "Berlin", "name": "Simon und Fatima", "alter": "36 und 32", "rolle": "Paar", "kuerzel": "S+F",
        "foto": "assets/personas/simon_fatima.jpg",
        "sterne": 5, "titel": "Klein wohnen, groß einkaufen und abends spontan Gäste haben",
        "text": "Wir wohnen auf wenig Raum und wollen trotzdem gut einkaufen: Bio, viel vegan und vegetarisch. "
                "Wenn abends Freunde kommen, finden wir hier noch frisches Brot, Dips und etwas Besonderes zu trinken.",
        "signale": ["Einwohner 20 bis 49", "kleine Haushalte", "Miete", "Cafés und Bars"],
        "quelle": "Zensus 2022, OpenStreetMap", "modell": "Potenzial der Anwohner und Affinität",
    },
    {
        "stadt": "München", "name": "Justus", "alter": "20", "rolle": "Student", "kuerzel": "J",
        "foto": "assets/personas/justus.jpg",
        "sterne": 5, "titel": "Hochwertig essen, ohne durch drei Läden zu rennen",
        "text": "Ich trainiere viel und achte auf mein Essen. Hier gibt es hochwertige Proteinquellen, und meine Freundin "
                "findet ihren Matcha, ohne dass wir noch woanders hin müssen.",
        "signale": ["Hochschulen", "Fitnessstudios", "Cafés"], "quelle": "OpenStreetMap",
        "modell": "Potenzial der Tagesbevölkerung und Affinität",
    },
]

# Lieferung: mögliche Partner, noch keine Gespräche geführt
LIEFERUNG_TEXT = "Lieferung über bestehende Plattformen, ohne eigene Fahrer."
LIEFERUNG_PARTNER = [
    ("Deliveroo", "assets/partner/deliveroo.svg"),
    ("Uber Eats", "assets/partner/ubereats.svg"),
    ("Just Eat Takeaway", "assets/partner/justeat.svg"),
    ("Lieferando", "assets/partner/lieferando.png"),
    ("Wolt", "assets/partner/wolt.png"),
]
LIEFERUNG_HINWEIS = ""

PILOT_TEXT = ("Je Stadt der beste White Spot aus dem Modell.")

HINWEIS = ("Personas und Bewertungen sind erfunden. Kleine Haushalte stehen in den Daten, gehen aber noch nicht in den Score ein, "
           "weil sie die Städte kaum trennen.")
