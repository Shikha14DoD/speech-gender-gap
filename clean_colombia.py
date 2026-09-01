"""
Post-process data/processed/colombia_merged.csv AFTER translation,
BEFORE finalize.

Strips, from full_text / full_text_en / original_text, boilerplate that
is not part of the speech and can survive from either source:
  - the editorial provenance footer the PDF volumes and some archived
    pages append ("Fuente: Presidencia de la Republica ... Edicion:
    Unidad de Implementacion del Acuerdo de Paz.", and its English form)
  - trailing presidential-photographer credit blocks
  - trailing editorial end-markers "(Fin/...)", "(END/...)"

The PDF scraper already does this at source; this is the safety net for
the Wayback rows and for anything that slipped through.

Usage:  python clean_colombia.py
"""

import re
import pandas as pd

PATH = "data/processed/colombia_merged.csv"

FOOTERS = [
    re.compile(r"\s*Fuente\s*:\s*Presidencia\s+de\s+la\s+[¬\-\s]*Rep[uú\wí]*"
               r".*?Edici[oó]n\s*:\s*Unidad\s+de\s+Implementaci[oó]n\s+del\s+"
               r"Acuerdo\s+de\s+Paz\.?", re.I | re.S),
    re.compile(r"\s*Source\s*:\s*Presidency\s+of\s+the\s+Rep.*?"
               r"Edition\s*:\s*Peace\s+Agreement\s+Implementation\s+Unit\.?", re.I | re.S),
]
PHOTO = re.compile(
    r"\s*(Agradecemos el apoyo de la Presidencia.*?material fotogr[aá]fico\s*:.*$)"
    r"|(\n[A-ZÁÉÍÓÚ][\wÁÉÍÓÚáéíóúñ .'\-]{2,40}\s*[-–]\s*Fot[oó]graf[oa]s?\s+[Pp]residencia.*$)"
    r"|(\s*(Fot[oó]graf[oa]|Photographer)[^\n]*Presidential Photographer\s*$)",
    re.I | re.S)
ENDMARK = re.compile(r"\s*\((Fin|End|END)[/\w.]*\)\s*$", re.I)
NOTSIGN = {0x00ac: None, 0x00ad: None}


def scrub(v):
    if not isinstance(v, str):
        return v
    v = v.translate(NOTSIGN)
    for f in FOOTERS:
        v = f.sub("", v)
    v = PHOTO.sub("", v)
    v = ENDMARK.sub("", v)
    return v.rstrip()


def main():
    df = pd.read_csv(PATH, dtype=str, keep_default_na=False)
    cols = [c for c in ["full_text", "full_text_en", "original_text", "title", "title_en"]
            if c in df.columns]
    before = {c: df[c].str.contains("Acuerdo de Paz|Implementation Unit|Fotógraf|Photographer",
                                    regex=True, na=False).sum() for c in cols}
    for c in cols:
        df[c] = df[c].map(scrub)
    after = {c: df[c].str.contains("Acuerdo de Paz|Implementation Unit|Fotógraf|Photographer",
                                   regex=True, na=False).sum() for c in cols}
    df.to_csv(PATH, index=False, encoding="utf-8")
    print(f"scrubbed {len(df)} rows across {cols}")
    for c in cols:
        print(f"  {c}: rows matching boilerplate {before[c]} -> {after[c]}")


if __name__ == "__main__":
    main()
