# -*- coding: utf-8 -*-
"""
I controlli dell’avviso ai motori di ricerca (sorgenti/indexnow.py)
-------------------------------------------------------------------
indexnow.py dice a Bing (e con lui a DuckDuckGo, Yahoo, Ecosia, Copilot), a Yandex, a Seznam e a Naver
quali pagine della mappa sono nuove o cambiate in una pubblicazione. Qui gira con cambiamenti, una mappa e
risposte finte: non chiede niente in rete e non tocca sito/. Lo fa girare sorgenti/controlla.py, con gli altri
controlli; da solo:

    python3 sorgenti/controlla-indexnow.py

Ogni controllo dice che cosa deve succedere. Si scrive prima di cambiare indexnow.py, si vede fallire,
e solo dopo si cambia indexnow.py (CLAUDE.md, Elias 15.10).
"""
import contextlib, importlib.util, io, json, os, re, sys, tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
_spec = importlib.util.spec_from_file_location("indexnow", os.path.join(QUI, "indexnow.py"))
indexnow = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(indexnow)

DOMINIO = "https://larosadoro.org"
CHIAVE = "0123456789abcdef0123456789abcdef"
MAPPA = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://larosadoro.org/</loc><lastmod>2026-11-23</lastmod></url>
<url><loc>https://larosadoro.org/lasciti/</loc><lastmod>2026-11-23</lastmod></url>
<url><loc>https://larosadoro.org/lasciti/come-fare-testamento/</loc><lastmod>2026-11-23</lastmod></url>
<url><loc>https://larosadoro.org/dona/</loc><lastmod>2026-11-23</lastmod></url>
</urlset>
"""
TUTTE = ["https://larosadoro.org/", "https://larosadoro.org/lasciti/",
         "https://larosadoro.org/lasciti/come-fare-testamento/", "https://larosadoro.org/dona/"]
ZERI = "0" * 40

falliti = []


def atteso(nome, ottenuto, voluto):
    if ottenuto != voluto:
        falliti.append("%s\n    atteso:    %r\n    ottenuto:  %r" % (nome, voluto, ottenuto))


def da_avvisare(cambiati):
    return indexnow.da_avvisare(cambiati, MAPPA, DOMINIO, CHIAVE)


def giro(argomenti, cambiati=None, errore=None):
    """fa girare indexnow.main() con una mappa e una chiave finte; cambiati: i file che git dà per cambiati
    (errore: git non risponde). Dà quello che scrive per GitHub (dizionario) e quello che stampa"""
    with tempfile.TemporaryDirectory() as radice:
        os.makedirs(os.path.join(radice, "sito"))
        with open(os.path.join(radice, "costruisci.py"), "w", encoding="utf-8") as f:
            f.write('DOMINIO = "%s"\nINDEXNOW = "%s"\n' % (DOMINIO, CHIAVE))
        with open(os.path.join(radice, "sito", "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write(MAPPA)
        uscita_github = os.path.join(radice, "uscita-github")
        chiesti = []

        def cambiati_fra(prima, dopo):
            chiesti.append((prima, dopo))
            if errore:
                raise OSError(errore)
            return list(cambiati or [])

        prima = indexnow.RADICE, indexnow.cambiati_fra, sys.argv, os.environ.get("GITHUB_OUTPUT")
        indexnow.RADICE, indexnow.cambiati_fra = radice, cambiati_fra
        sys.argv = ["indexnow.py"] + argomenti
        os.environ["GITHUB_OUTPUT"] = uscita_github
        stampato = io.StringIO()
        try:
            with contextlib.redirect_stdout(stampato):
                indexnow.main()
        finally:
            indexnow.RADICE, indexnow.cambiati_fra, sys.argv = prima[:3]
            if prima[3] is None:
                os.environ.pop("GITHUB_OUTPUT", None)
            else:
                os.environ["GITHUB_OUTPUT"] = prima[3]
        scritto = {}
        if os.path.exists(uscita_github):
            for riga in open(uscita_github, encoding="utf-8").read().splitlines():
                nome, _, valore = riga.partition("=")
                scritto[nome] = valore
        return scritto, stampato.getvalue(), chiesti


# 1. Una pagina della mappa cambiata: si avvisa solo quella, con il suo indirizzo pulito.
atteso("una pagina cambiata", da_avvisare(["sito/lasciti/index.html"]), ["https://larosadoro.org/lasciti/"])
atteso("la home cambiata", da_avvisare(["sito/index.html"]), ["https://larosadoro.org/"])

# 2. La data della mappa, gli stili, il JavaScript, le immagini cambiano a ogni giro: da soli non sono pagine nuove.
atteso("solo mappa, stili, script e immagini",
       da_avvisare(["sito/sitemap.xml", "sito/css/stile.css", "sito/js/sito.js", "sito/img/tavola-spighe.svg"]), [])

# 3. Le pagine fuori dalla mappa (il giardino, la ricerca, il grazie dopo Stripe, le pagine «noindex») non si avvisano mai.
atteso("il giardino e le pagine fuori dalla mappa",
       da_avvisare(["sito/in-memoria/giardino-dei-ricordi/index.html", "sito/in-memoria/giardino-dei-ricordi/dediche.json",
                    "sito/cerca/index.html", "sito/dona/grazie/index.html", "sito/404.html"]), [])

# 4. I file fuori da sito/ (testi, assemblatore, controlli) non sono pagine.
atteso("file fuori da sito/", da_avvisare(["testi_pagine.py", "costruisci.py", "lasciti/index.html"]), [])

# 5. Più pagine cambiate: ognuna una volta sola, nell’ordine della mappa.
atteso("più pagine", da_avvisare(["sito/dona/index.html", "sito/index.html", "sito/dona/index.html"]),
       ["https://larosadoro.org/", "https://larosadoro.org/dona/"])

# 6. La prima volta che la chiave va online (il suo file è nuovo fra i cambiati) si avvisano tutte le pagine della mappa.
atteso("la chiave nuova", da_avvisare(["sito/%s.txt" % CHIAVE, "sito/sitemap.xml"]), TUTTE)

# 7. L’avviso ha la forma che chiede IndexNow: host senza https, chiave, dove sta la chiave, gli indirizzi.
atteso("la forma dell’avviso", indexnow.avviso(["https://larosadoro.org/dona/"], DOMINIO, CHIAVE),
       {"host": "larosadoro.org", "key": CHIAVE, "keyLocation": "https://larosadoro.org/%s.txt" % CHIAVE,
        "urlList": ["https://larosadoro.org/dona/"]})

# 8. Con la pubblicazione: le pagine cambiate fra il commit di prima e quello di adesso vanno in GITHUB_OUTPUT,
#    in una riga sola, pronte per essere mandate dopo la pubblicazione.
scritto, stampato, chiesti = giro(["prepara", "aaa111", "bbb222"], cambiati=["sito/lasciti/come-fare-testamento/index.html"])
atteso("chiede a git i cambiati fra i due commit", chiesti, [("aaa111", "bbb222")])
try:
    corpo = json.loads(scritto.get("avviso", "") or "null")
except ValueError:
    corpo = "non è JSON: %r" % scritto.get("avviso")
atteso("l’avviso per GitHub", corpo, indexnow.avviso(["https://larosadoro.org/lasciti/come-fare-testamento/"], DOMINIO, CHIAVE))
atteso("dice quante pagine avvisa", "1 pagin" in stampato, True)

# 9. Niente da avvisare: «avviso» resta vuoto, così il passo che manda non parte.
scritto, stampato, _ = giro(["prepara", "aaa111", "bbb222"], cambiati=["sito/sitemap.xml"])
atteso("niente da avvisare", scritto.get("avviso", ""), "")

# 10. Il primo invio su un ramo nuovo non ha un commit di prima (tutti zeri, o vuoto): non si chiede niente a git.
for primo in (ZERI, ""):
    scritto, stampato, chiesti = giro(["prepara", primo, "bbb222"], cambiati=["sito/index.html"])
    atteso("senza commit di prima (%r): niente git" % primo, chiesti, [])
    atteso("senza commit di prima (%r): niente avviso" % primo, scritto.get("avviso", ""), "")

# 11. Se git non risponde, l’avviso salta e basta: la pubblicazione non si ferma per questo.
scritto, stampato, _ = giro(["prepara", "aaa111", "bbb222"], errore="fetch rifiutato")
atteso("git non risponde: niente avviso", scritto.get("avviso", ""), "")
atteso("git non risponde: lo dice", "fetch rifiutato" in stampato, True)

# 12. Mandare: 200 e 202 vanno bene; 403 (la chiave non si trova online), 422, 429 e il silenzio no,
#     e il motivo si legge nel resoconto. L’avviso parte una volta sola verso api.indexnow.org, in JSON.
for codice, bene in ((200, True), (202, True), (403, False), (422, False), (429, False), (0, False)):
    mandati = []

    def posta(indirizzo, dati, intestazioni):
        mandati.append((indirizzo, json.loads(dati.decode("utf-8")), intestazioni.get("Content-Type", "")))
        if codice == 0:
            raise OSError("non risponde")
        return codice, "risposta %d" % codice

    stampato = io.StringIO()
    with contextlib.redirect_stdout(stampato):
        esito = indexnow.manda(json.dumps(indexnow.avviso(TUTTE, DOMINIO, CHIAVE)), posta=posta)
    atteso("risposta %d: esito" % codice, esito, bene)
    atteso("risposta %d: una volta sola, a IndexNow, in JSON" % codice,
           [(i, c.startswith("application/json")) for i, _, c in mandati], [("https://api.indexnow.org/indexnow", True)])
    atteso("risposta %d: manda le 4 pagine" % codice, mandati[0][1]["urlList"], TUTTE)
    atteso("risposta %d: scrive il codice nel resoconto" % codice, str(codice) in stampato.getvalue() or codice == 0, True)

# 13. La chiave vera: nel formato di IndexNow, e la costruzione la mette online accanto alle pagine (sito/<chiave>.txt),
#     con dentro la chiave e nient’altro.
sorgente = open(os.path.join(RADICE, "costruisci.py"), encoding="utf-8").read()
trovata = re.search(r'^INDEXNOW = "([^"]*)"', sorgente, re.M)
chiave = trovata.group(1) if trovata else ""
atteso("INDEXNOW in costruisci.py, nel formato di IndexNow", bool(re.fullmatch(r"[a-zA-Z0-9-]{8,128}", chiave)), True)
file_chiave = os.path.join(RADICE, "sito", chiave + ".txt")
atteso("il file della chiave in sito/", os.path.exists(file_chiave) and open(file_chiave, encoding="utf-8").read(), chiave)

if falliti:
    print("L’avviso ai motori non fa quello che deve (%d):" % len(falliti))
    for f in falliti:
        print("- " + f)
    sys.exit(1)
print("Avviso ai motori (IndexNow): le pagine giuste, una volta sola, solo quelle della mappa; la chiave è online")
