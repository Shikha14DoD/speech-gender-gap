
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


  ### Italy (Giorgia Meloni)
- Site's listing page (`governo.it/en/interventi-en`) returns a bot-detection
  block when scraped programmatically; same Wayback CDX + live-fetch
  workaround used as Denmark.
- The underlying `/en/articolo/` feed is a general government press feed
  (1,600+ items), not speeches-only -- filtered by requiring her name in
  the title, plus keyword-based speech/non-speech classification.
- Official English translations are published directly on the site (many
  marked "[Courtesy translation]") -- no machine translation needed.
- **Content format note:** some entries are interviews (Q&A format,
  interviewer questions interleaved with her answers), not monologue
  speeches. These are intentionally KEPT (substantive first-person
  content, sometimes on directly relevant topics like gender/women's
  themes) but `full_text` for these rows contains both the interviewer's
  questions and her answers -- word-frequency/theme analysis on raw
  `full_text` for these rows will partially reflect the journalist's
  questions, not just her own words. See the `content_type` column to
  identify and handle these rows differently if needed.

  ### Italy (Giorgia Meloni)
- Site's listing page (`governo.it/en/interventi-en`) returns a bot-detection
  block when scraped programmatically; same Wayback CDX + live-fetch
  workaround used as Denmark, drawing from the broader `/en/articolo/`
  government article namespace rather than the curated listing itself.
- Official English translations are published directly on the site (many
  marked "[Courtesy translation]") -- no machine translation needed.
- **Scope note:** the government's own curated "interventi-en"
  (interventions/speeches) listing contains ~329 entries across our date
  range (manually verified by browsing the live site). Our scraped
  dataset is broader (740 rows) because it draws from the wider article
  feed and uses keyword-based classification rather than the
  government's own curation -- meaning some rows are legitimate
  speech-like content the government didn't officially file under
  "interventions" (e.g. certain press statements, video messages). The
  `likely_speech` and `content_type` columns exist specifically to let
  downstream analysis filter to a narrower, more speech-like subset if
  desired, rather than treating all 740 rows as equivalent.
- **Recency lag confirmed and manually corrected:** cross-referencing
  our scraped data against the live site found 93 entries the Wayback
  Machine hadn't yet crawled (heavily skewed toward the most recent
  months -- 96% were from 2025-2026). Since we already had the exact
  URLs from manually browsing the site, these were fetched directly
  (bypassing Wayback) and added -- see `fill_missing_italy.py`. If
  re-running this scraper months from now, expect a similar small gap
  at the most recent end until Wayback catches up again; the same
  backfill approach can be reused.
- **`content_type` column** (Speech / Interview / Statement / Other):
  a few entries are interviews (Q&A format, interviewer questions
  interleaved with her answers), not monologue speeches. These are
  intentionally KEPT (substantive first-person content, sometimes on
  directly relevant topics like gender/women's themes) but `full_text`
  for these rows contains both the interviewer's questions and her
  answers -- word-frequency/theme analysis on raw `full_text` for these
  rows will partially reflect the journalist's questions, not just her
  own words.

  ### Slovenia (Nataša Pirc Musar)
- Unlike Denmark and Italy, this site's listing page (`predsednica-slo.si/en/news/all`)
  works fine with a plain HTTP request -- no JavaScript rendering, no
  bot-detection block. Scraped directly via pagination (`?start=N`,
  16 items per page), no Wayback Machine workaround needed.
- Scraped the site's English-language subsection directly, so `full_text`
  is already English -- no machine translation needed for this country.
- **Scope note (same caveat as documented from the start of the
  project):** this is a general news/activity feed, NOT a speeches-only
  feed. It mixes real remarks (New Year's messages, podcast episodes,
  formal statements) with routine news (ambassador credential
  ceremonies, bilateral meeting announcements, condolence messages).
  `likely_speech` and `content_type` skew heavily toward "maybe"/"Other"
  as a result (173 maybe / 40 yes / 0 no; 191 Other / 15 Statement /
  7 Speech) -- this reflects the real, mixed nature of the source, not
  a filtering bug. Manual review of "maybe" rows is expected before
  treating this as a final speeches-only dataset.
- **Date extraction:** article pages carry a reliable ISO-formatted date
  in a `<meta>` tag (more robust than parsing visible text, which uses
  an inconsistent format between the listing page and individual
  articles -- listing shows "Publish date: DD Mon YYYY", article pages
  show "Publish date  <City>, DD Mon YYYY" with no colon and a city
  name inserted). The scraper checks the meta tag first, falling back
  to the visible-text pattern only if that's missing.
- **Spouse-content fix:** the site's navigation includes a separate
  "Spouse" section, and the general news feed occasionally covers her
  husband's (Aleš Musar) activities specifically -- these share her
  surname, so a simple surname search can't tell them apart. One such
  row ("Dr Aleš Musar with Olena Zelenska and Eliza...") was found and
  removed via a targeted keyword exclusion on his full name. Checked
  that this doesn't risk excluding her own genuine content: the
  exclusion only applies to the title (not full_text), and no
  legitimate speech titles on this site follow a "her name + his name"
  pattern -- titles mentioning him by name are consistently *about* him
  specifically.
- **Verified she's the actual subject, not just mentioned in passing:**
  199 of 213 scraped rows mention "Pirc Musar" directly in the body
  text; the remaining 14 were manually reviewed -- mostly her own named
  podcast ("The President's Podcast") or quote-style headlines that
  don't repeat her surname, plus the one spouse-content row above
  (removed).
- **Completeness independently verified:** cross-checked against the
  live site's own pagination -- confirmed 19 total pages, 7 items on
  the final page, exactly matching what the scraper found and stopped
  at. No early-stopping or missed pages.
- Final row count: 212 (213 scraped, minus 1 spouse-content row removed).

- **Excel file limitation:** `denmark.xlsx` truncates ~7 of the longest
  speeches (New Year's addresses and similar lengthy remarks) at Excel's
  hard 32,767-character-per-cell limit. `denmark.csv` is NOT affected
  (no such limit) and contains the complete, untruncated text -- treat
  the CSV as the authoritative source; the .xlsx is for convenient
  viewing only.

  ### Samoa (Fiamē Naomi Mataʻafa)
- Standard WordPress category archive (`mygov.gov.ws/category/pm-corner/`),
  clean `/page/N/` pagination -- required switching to a browser-like
  User-Agent to avoid a bot-detection block (403 errors) that the site's
  security plugin returns for non-browser-looking traffic.
- Category is shared with her successor (male PM, since 16 Sep 2025) and
  his Deputy PM (a different woman) -- filtered by name marker in
  title/URL AND a hard date cutoff at her last day in office. Do not
  relax either check.
- **Major coverage gap, confirmed unrecoverable:** the site's entire
  archive only goes back to approximately March 2024 -- nothing from
  the start of her tenure (24 May 2021) or even the start of this
  project's date range (1 Jan 2023) is present. Checked the Wayback
  Machine directly for any archived version of this domain from
  2021-2023 (the same technique that recovered Denmark's missing
  speeches) -- found NOTHING (zero results). This strongly suggests the
  site was rebuilt/relaunched in 2024 and earlier content was not
  preserved anywhere accessible. Final dataset covers only
  [DATE_RANGE] -- a significantly shorter window than her actual tenure
  or the project's intended range for this country. This should be
  flagged explicitly in any analysis using this data, since Samoa's
  coverage is structurally different (much shorter) than the other
  three countries.

  ### Samoa (Fiamē Naomi Mataʻafa)
- Standard WordPress category archive (`mygov.gov.ws/category/pm-corner/`),
  clean `/page/N/` pagination -- required switching to a browser-like
  User-Agent to avoid a bot-detection block (403 errors) that the site's
  security plugin returns for non-browser-looking traffic.
- Category is shared with her successor (male PM, since 16 Sep 2025) and
  his Deputy PM (a different woman) -- filtered by name marker in
  title/URL AND a hard date cutoff at her last day in office. Do not
  relax either check.
- **Major coverage gap, confirmed unrecoverable:** the site's entire
  archive only goes back to approximately March 2024 -- nothing from
  the start of her tenure (24 May 2021) or even the start of this
  project's date range (1 Jan 2023) is present. Checked the Wayback
  Machine directly for any archived version of this domain from
  2021-2023 (the same technique that recovered Denmark's missing
  speeches) -- found NOTHING (zero results). This strongly suggests the
  site was rebuilt/relaunched in 2024 and earlier content was not
  preserved anywhere accessible.
- **Final dataset: 15 rows, covering only 26 Mar 2024 to 5 Jul 2024** --
  a roughly 3-month window, dramatically shorter than her actual
  ~4-year tenure or this project's intended 2023-2026 range for other
  countries. This should be flagged explicitly in any analysis using
  this data -- Samoa's coverage is structurally different (much
  shorter and narrower) than Denmark, Italy, and Slovenia, through no
  fault of the scraping approach; it reflects a genuine, verified gap
  in what's publicly available online for this leader's earlier
  speeches.

  - **⚠ CURRENT STATUS (as of [today's date]): PARTIAL DATASET.** The full
  scrape (~740 rows, previously validated) requires the Internet
  Archive's Wayback CDX API for URL discovery, which has been
  consistently unreachable (repeated timeouts/503/498 errors across
  multiple attempts). Current `italy.csv` contains only 91 rows --
  specifically the known-missing recent entries manually identified
  earlier (see `fill_missing_italy.py`), NOT the full dataset. Re-run
  `python main.py --country italy` once Wayback access is confirmed
  working again to restore full coverage.

  ### China (Xi Jinping)
- Scraped from `english.scio.gov.cn`'s curated English "Speeches"
  section (State Council Information Office coverage of Xi's
  governance activities) -- no JavaScript rendering or bot-detection
  issues encountered, unlike Denmark/Italy/Samoa's listing pages.
  Individual article pages carry a clean, machine-readable date
  directly in page metadata (`meta-publishdate`), similar to
  Slovenia's approach -- more reliable than parsing visible text.
- **Source-type note:** unlike the other four countries' sites (each
  an official leader/government office publishing directly), this
  content is distributed via Xinhua (China's state news agency),
  republished on a State Council body's site -- a step removed from
  "his own office publishing his own words." Flagged per-row in the
  `notes` column.
- **Scope note:** filtered to entries specifically framed under his
  PRESIDENTIAL title ("President Xi" / "Chinese President Xi Jinping"
  in the title) -- his other titles (General Secretary of the CPC,
  Chairman of the Central Military Commission) are excluded even
  though the source section covers him across all roles.
- **Date range differs from the other four countries:** scoped to
  Jan 2024 -- 2026 specifically (per project instruction), not
  Jan 2023 onward. Implemented via a per-country `date_range` override
  in `config.json` rather than the shared project-wide default.
- **Coverage is notably thinner than the other countries: 21 rows
  over ~2 years**, versus e.g. Denmark's 53 over 3.5 years or Italy's
  979. This likely reflects the curated feed's scope -- capturing his
  highest-profile international remarks (summits, state visits,
  signed articles for foreign media) rather than the fuller range of
  domestic speeches a head of state typically gives. Not yet
  independently validated against an alternative source; treat this
  as a preliminary, likely-incomplete dataset for this country until
  further checked.