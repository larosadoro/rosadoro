# -*- coding: utf-8 -*-
"""
L’avviso ai motori di ricerca (IndexNow), per la pubblicazione del sito
-----------------------------------------------------------------------
Google trova da solo le pagine nuove; Bing no, o molto più tardi. E da Bing prendono i risultati
DuckDuckGo, Yahoo, Ecosia (in parte), Copilot e la ricerca di ChatGPT. IndexNow è il modo con cui un
sito dice a Bing, Yandex, Seznam e Naver «queste pagine sono nuove o cambiate»: un solo avviso a
api.indexnow.org arriva a tutti. Decidono poi loro se e quando metterle fra i risultati.

La chiave sta in costruisci.py (INDEXNOW) e la costruzione la mette online in sito/<chiave>.txt: è
così che i motori sanno che l’avviso viene davvero da larosadoro.org. Non è un segreto.

Lo usa il workflow di pubblicazione (.github/workflows/pages.yml), solo negli invii (push) al ramo
principale, mai nel giro di ogni ora delle dediche:

    python3 sorgenti/indexnow.py prepara <commit di prima> <commit di adesso>

prima di pubblicare: confronta i due commit e scrive in $GITHUB_OUTPUT «avviso=…» con le pagine della
mappa (sitemap.xml) cambiate; tutte, la prima volta che la chiave va online. Vuoto se non c’è niente
da dire, se manca il commit di prima (un ramo nuovo) o se git non risponde: la pubblicazione va avanti.

    python3 sorgenti/indexnow.py manda

dopo la pubblicazione, quando pagine e chiave sono già online: manda l’avviso (dalla variabile
AVVISO) e scrive nel resoconto che cosa ha risposto IndexNow.

I controlli sono in sorgenti/controlla-indexnow.py.
"""
import json, os, re, subprocess, sys, urllib.error, urllib.parse, urllib.request

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDIRIZZO = "https://api.indexnow.org/indexnow"


def impostazione(nome):
    """il valore di una impostazione di costruisci.py, senza eseguirlo"""
    sorgente = open(os.path.join(RADICE, "costruisci.py"), encoding="utf-8").read()
    trovata = re.search(r'^%s = "([^"]*)"' % nome, sorgente, re.M)
    return trovata.group(1) if trovata else ""


def da_avvisare(cambiati, mappa, dominio, chiave):
    """gli indirizzi della mappa le cui pagine sono fra i file cambiati, nell’ordine della mappa;
    tutti, se fra i cambiati c’è il file della chiave (la prima volta che va online)"""
    dominio = dominio.rstrip("/")
    indirizzi = re.findall(r"<loc>([^<]+)</loc>", mappa)
    cambiati = set(cambiati)
    if "sito/%s.txt" % chiave in cambiati:
        return indirizzi
    uscita = []
    for indirizzo in indirizzi:
        if not indirizzo.startswith(dominio + "/"):
            continue
        pagina = "sito/" + indirizzo[len(dominio) + 1:] + "index.html"
        if pagina in cambiati:
            uscita.append(indirizzo)
    return uscita


def avviso(indirizzi, dominio, chiave):
    """il corpo dell’avviso, nella forma che chiede IndexNow"""
    dominio = dominio.rstrip("/")
    return {"host": urllib.parse.urlsplit(dominio).hostname, "key": chiave,
            "keyLocation": "%s/%s.txt" % (dominio, chiave), "urlList": list(indirizzi)}


def cambiati_fra(prima, dopo):
    """i file cambiati fra due commit; il commit di prima si scarica da solo, perché la pubblicazione
    scarica solo l’ultimo"""
    subprocess.run(["git", "fetch", "--no-tags", "--depth=1", "origin", prima],
                   cwd=RADICE, check=True, capture_output=True, text=True, timeout=120)
    esito = subprocess.run(["git", "diff", "--name-only", prima, dopo, "--", "sito/"],
                           cwd=RADICE, check=True, capture_output=True, text=True, timeout=120)
    return [r for r in esito.stdout.splitlines() if r]


def scrivi_per_github(valore):
    uscita = os.environ.get("GITHUB_OUTPUT")
    if uscita:
        with open(uscita, "a", encoding="utf-8") as f:
            f.write("avviso=%s\n" % valore)


def prepara(prima, dopo):
    dominio, chiave = impostazione("DOMINIO"), impostazione("INDEXNOW")
    if not chiave:
        print("Avviso ai motori: INDEXNOW è vuoto in costruisci.py, niente avviso")
        return scrivi_per_github("")
    if not prima.strip("0"):
        print("Avviso ai motori: manca il commit di prima (ramo nuovo), niente avviso")
        return scrivi_per_github("")
    try:
        cambiati = cambiati_fra(prima, dopo)
    except (OSError, subprocess.SubprocessError) as e:
        dettaglio = getattr(e, "stderr", "") or str(e)
        print("Avviso ai motori: git non dà i file cambiati (%s), niente avviso questa volta" % dettaglio.strip()[-300:])
        return scrivi_per_github("")
    mappa = open(os.path.join(RADICE, "sito", "sitemap.xml"), encoding="utf-8").read()
    indirizzi = da_avvisare(cambiati, mappa, dominio, chiave)
    if not indirizzi:
        print("Avviso ai motori: nessuna pagina della mappa è cambiata")
        return scrivi_per_github("")
    print("Avviso ai motori: %d pagin%s da avvisare dopo la pubblicazione" % (len(indirizzi), "a" if len(indirizzi) == 1 else "e"))
    for indirizzo in indirizzi:
        print("  " + indirizzo)
    scrivi_per_github(json.dumps(avviso(indirizzi, dominio, chiave), separators=(",", ":")))


def posta(indirizzo, dati, intestazioni):
    """(codice, testo) della risposta"""
    richiesta = urllib.request.Request(indirizzo, data=dati, headers=intestazioni, method="POST")
    try:
        with urllib.request.urlopen(richiesta, timeout=60) as r:
            return r.status, r.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000).decode("utf-8", "replace")


SPIEGAZIONI = {
    200: "ricevuto",
    202: "ricevuto; la chiave si controlla fra poco",
    400: "l’avviso non è scritto bene",
    403: "la chiave non si trova online, o non corrisponde",
    422: "qualche indirizzo non è di larosadoro.org, o la chiave non corrisponde",
    429: "troppi avvisi in poco tempo",
}


def manda(testo, posta=posta):
    """manda l’avviso a IndexNow; True se l’ha ricevuto"""
    dati = testo.encode("utf-8")
    quante = len(json.loads(testo).get("urlList", []))
    try:
        codice, risposta = posta(INDIRIZZO, dati, {"Content-Type": "application/json; charset=utf-8",
                                                   "User-Agent": "rosadoro-pubblicazione"})
    except Exception as e:
        print("Avviso ai motori: IndexNow non risponde (%s). Le pagine si troveranno comunque dalla mappa." % e)
        return False
    spiegazione = SPIEGAZIONI.get(codice, "risposta inattesa")
    print("Avviso ai motori: %d pagine, IndexNow risponde %d (%s)%s"
          % (quante, codice, spiegazione, (": " + risposta.strip()[:300]) if risposta.strip() else ""))
    return codice in (200, 202)


def main():
    comando = sys.argv[1] if len(sys.argv) > 1 else ""
    if comando == "prepara" and len(sys.argv) == 4:
        prepara(sys.argv[2], sys.argv[3])
    elif comando == "manda":
        testo = os.environ.get("AVVISO", "")
        if not testo:
            print("Avviso ai motori: niente da mandare")
            return
        if not manda(testo):
            sys.exit(1)
    else:
        sys.exit("Uso: indexnow.py prepara <commit di prima> <commit di adesso> | indexnow.py manda (con AVVISO)")


if __name__ == "__main__":
    main()
