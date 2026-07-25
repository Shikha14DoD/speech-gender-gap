
# Speech Gender Gap

#branch-> scraper-development

## Overview
This project investigates gender differences in the themes and priorities
that heads of state/government emphasize in their public speeches
(2023–2026), and how discourse on gender equality and women's rights has
shifted since 2023, broken down by the leader's sex.

## Current scope
Phase 1 covers speech collection for four female heads of state/government:

| Country | Leader | Role | Source |
|---|---|---|---|
| Slovenia | Nataša Pirc Musar | President | predsednica-slo.si |
| Italy | Giorgia Meloni | Prime Minister | governo.it |
| Denmark | Mette Frederiksen | Prime Minister | english.stm.dk |
| Samoa | Fiamē Naomi Mataʻafa | Prime Minister (until 16 Sep 2025) | mygov.gov.ws |

A matched sample of male heads of state/government will be added in a
later phase for the sex-comparison analysis.

## Project structure
(to be filled in as we build it out)

## Setup
(to be filled in)

## Usage
(to be filled in)

## Data sources & known limitations

### Denmark (Mette Frederiksen)
- The official site's speech listing page (`stm.dk/statsministeren/taler/`)
  loads its content via client-side JavaScript, which our scraper can't
  execute — the listing page itself returns no usable links to a plain
  HTTP request.
- **Workaround:** we use the Internet Archive's Wayback Machine CDX API
  to discover real speech URLs (it indexes what pages exist, regardless
  of how the site's own listing page loads), then fetch each page LIVE
  from the current site — never from the archive/cache itself — so the
  speech text is always current, not historical.
- This means completeness depends on the Wayback Machine having crawled
  a given speech. Verified (16 Jul 2026) that new speeches are archived
  quickly — her 11 June 2026 speech was crawled just 5 days later (16
  June 2026) — so recency lag is small in practice, but if re-running this scraper very close to an analysis/reporting date, the most recent speech or two may occasionally be missing until the Archive catches up.
- The URL list spans every Danish PM since 1998 (not just Frederiksen),so results are filtered both by her name appearing on the page and by date range.

- **Translation caveat:** `full_text_en` and `title_en` are machine-translated
  (Google Translate, via the free `deep-translator` library) — not
  official or professionally translated. Translation succeeded on all
  53 rows and reads as coherent, faithful English on spot-checks, but
  it is NOT verified sentence-by-sentence against the Danish originals.
  Known weakness: specialized political/administrative terms can
  translate poorly (e.g. "Valgudskrivelse" — the formal term for a PM
  calling an election — was translated as "Voting" instead of "Election
  announcement"). Treat `full_text_en`/`title_en` as good enough for
  thematic/content analysis, not as a certified accurate translation.
  The original-language `full_text`/`title` are preserved specifically
  so anyone can verify or re-translate a given passage if precision on
  a specific point matters.