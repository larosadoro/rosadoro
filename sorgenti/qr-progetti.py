# -*- coding: utf-8 -*-
"""
Il codice QR dei biglietti di soli auguri (Dacia, 25.11.2026): porta alla pagina dei progetti della Fondazione,
https://larosadoro.org/progetti/. Il biglietto lo disegna sito.js, accanto a «Scopri i nostri progetti» e all’indirizzo
del sito, al posto della frase sulla donazione.

Si rifà con:   python3 sorgenti/qr-progetti.py     (serve la libreria segno: pip install segno)
Scrive:        sito/img/qr-progetti.svg, un quadratino per modulo, in antracite, senza margine: il margine bianco
               intorno lo lascia il biglietto. sito.js lo disegna con un numero intero di pixel per modulo, così resta nitido.
Correzione degli errori Q (un quarto del codice può rovinarsi), perché il biglietto si stampa a casa e si manda anche
come immagine compressa.
"""
import os
import segno

INDIRIZZO = "https://larosadoro.org/progetti/"
ANTRACITE = "#1C1C1C"

QUI = os.path.dirname(os.path.abspath(__file__))
USCITA = os.path.join(QUI, "..", "sito", "img", "qr-progetti.svg")


def svg(qr):
    righe = list(qr.matrix)
    n = len(righe)
    quadri = "".join("M%d %dh1v1h-1z" % (x, y) for y, riga in enumerate(righe) for x, v in enumerate(riga) if v)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" shape-rendering="crispEdges">'
            '<path d="%s" fill="%s"/></svg>\n' % (n, n, n, n, quadri, ANTRACITE))


if __name__ == "__main__":
    qr = segno.make(INDIRIZZO, error="q", boost_error=False, micro=False)
    with open(USCITA, "w", encoding="utf-8") as f:
        f.write(svg(qr))
    print("Scritto %s (versione QR %s, %d moduli)" % (os.path.relpath(USCITA), qr.version, len(list(qr.matrix))))
