
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

  - **One article (May 7, 2024, China-France Business Council speech)
  required a special fix:** it's linked correctly on the site, but
  our standard `requests`-based fetch was served a stripped
  placeholder page for this specific URL, while a browser-like fetch
  got the real content -- likely the same category of disguised
  bot-detection already solved elsewhere in this project (Wayback
  Machine, Samoa). Fixed by fetching this one article with `curl_cffi`
  (browser impersonation) instead; see `fill_missing_china.py`.
- **Final validated dataset: 37 rows, 2024-05-07 to 2026-07-18.**
  Cross-checked against a manually browsed listing of the site's own
  pages; all entries accounted for.

  - **Completeness validated against a manually browsed reference list
  (38 entries, May 2024 -- July 2026): 37/38 match exactly by date.**
  The one difference (Oct 29, 2025, "Explanation of the Recommendations
  ... 15th Five-Year Plan") was deliberately excluded -- Xi delivered
  it, but the site frames it under his Party role (General Secretary
  of the CPC Central Committee) rather than his presidential title,
  consistent with this project's scope of his PRESIDENTIAL activity
  specifically.

  ### China — Li Qiang (Premier)
- **Discovery method: manually curated via targeted web searches, not
  automated site scraping.** Li Qiang's speeches are published across
  `english.www.gov.cn`'s general `/news/` feed (no dedicated section),
  and the site's own search interface is JavaScript-rendered --
  results are invisible to a plain fetch (confirmed via direct
  dev-tools investigation: checked every network request behind the
  search page, found only template/config data, no callable results
  API). The Wayback Machine CDX approach used successfully elsewhere
  in this project also failed here: this domain's Wayback crawl
  history is dominated by old, periodically re-crawled pages, leaving
  no room for genuinely recent content in each year's capped (500)
  result set.
- **Final dataset: 14 speeches, individually identified and verified**
  via targeted searches (2024-01-17 to 2026-06-25), added via
  `seed_liqiang.py`. Covers major international summits (G20, BRICS,
  SCO, ASEAN, East Asia Summit, APEC-adjacent forums), the World
  Economic Forum (Davos, both 2024 and the 2026 Summer Davos), a
  state-visit banquet speech, and the China Development Forum keynote.
- **Deliberately excluded: the three annual "Government Work Reports"**
  (delivered each March to the National People's Congress -- 2024,
  2025, 2026). Independently confirmed via multiple news sources that
  he personally delivers this report, but it was judged not to be a
  "speech" in the sense the rest of this dataset captures -- more a
  formal policy document read into the record than personally-authored
  remarks. Consistent with the same judgment call made for Xi Jinping's
  15th Five-Year Plan explanation document.
- This is NOT a comprehensive scrape -- treat as a curated sample of
  his major addresses, not full coverage of every remark or statement
  he's made. Add more entries to `seed_liqiang.py`'s `KNOWN_URLS` list
  as additional real speeches are identified.

  ### China — Xi Jinping (People's Daily database, supplementary source)
- **Source:** `jhsjk.people.cn`, People's Daily's official "Xi Jinping
  Series of Important Speeches Database" -- a dedicated, much larger
  archive (128 speech-type entries for 2024-2026 alone) than the
  English SCIO site, filterable by content type and year. The site's
  own UI is JavaScript-driven; found the real underlying JSON search
  API via browser dev tools (same technique used for Li Qiang).
- **Content is in Chinese** -- machine-translated via `deep-translator`
  (Google Translate), with a fallback to `MyMemoryTranslator` for
  chunks that failed on the primary service. This was necessary: the
  free Google Translate endpoint showed significant, unpredictable
  intermittent failures under this volume/document length (confirmed
  via direct testing -- identical-length chunks from the same document
  sometimes succeeded, sometimes failed, with no consistent size
  threshold). The fallback recovered the large majority of failures;
  final dataset has 100% successful translation coverage.
- **Chunking note:** Chinese-to-English translation expands text
  substantially (~4.5x by character count in testing) -- chunk size
  limits had to account for the translated OUTPUT length against
  Google's cap, not just the Chinese input length, which was the
  initial source of a large batch of early translation failures.
- **Final dataset: 127 rows** (2024-01-01 to 2026-07-31), after
  removing 1 row classified `likely_speech: "no"`. `likely_speech` and
  `content_type` were computed from the translated English titles
  (`title_en`), not the original Chinese, since the classifier only
  recognizes English keywords.
- **Relationship to the SCIO dataset:** this is a separate, larger,
  supplementary source for the same person, not a replacement -- the
  two datasets are stored separately (`china.csv` for SCIO,
  `xipeoplecn.csv` for this source) and may contain overlapping
  events described differently; not yet deduplicated against each
  other.


### Barbados (Mia Mottley)
- Site (`pmo.gov.bb`) blocks plain `requests` library traffic with a
  403 -- same category of bot-detection issue solved elsewhere in
  this project; fixed with `curl_cffi` (browser impersonation) plus a
  proper polite-delay/retry pattern.
- **Important structural finding:** the site's homepage uses a broken
  dual-widget layout (a "Recent Posts" section frozen at old content,
  duplicated alongside a "Latest Posts" sidebar that repeats the same
  4 items on every page) -- neither paginates correctly. The
  `/category/speeches/` feed (originally suggested) stopped being
  tagged after Feb 2025, just before this project's date range starts.
  **Used `/category/latest/` instead** -- confirmed via direct
  inspection to be a properly, singly-paginated, genuinely
  chronological feed with no duplication issues.
- Feed mixes real speeches with routine government announcements;
  `likely_speech`/`content_type` flag but don't filter ambiguous rows.
- Final dataset: 7 rows, 2025-03-12 to 2026-02-16 (date range requested
  was Feb 5 2025 onward; the one entry from Feb 4 2025 -- one day
  before the cutoff -- was correctly excluded).

- **`content_type`/`likely_speech` are set directly to "Speech"/"yes"
  for this country**, not computed via the generic title-keyword
  classifier used elsewhere -- Barbados's titles (e.g. "A call to
  action emphasizes consumer mobilization...") don't follow the
  "President X's speech at Y" pattern the classifier expects, so it
  would mislabel genuine speeches as low-confidence. Since every row
  here already passed strict first-person/byline filtering (see above),
  labeling is based on that verification instead.

### USA — Joe Biden (President, through 20 Jan 2025)
- Source: `bidenwhitehouse.archives.gov`, the frozen official Biden
  White House archive (no longer updated, covers his full term).
  Plain server-rendered HTML, clean `/page/N/` pagination -- no
  JavaScript rendering or bot-detection issues.
- Feed shared with the Vice President, First Lady, and staff --
  filtered to entries attributed to "President Biden" specifically.
  Caught and fixed a real bug during this: non-breaking space
  characters (`&nbsp;`) in some titles (e.g. "Jill  Biden" with
  irregular spacing) were bypassing the exact-string exclusion check
  -- fixed at the shared `clean_text()` level, benefiting every
  scraper in the project, not just this one.
- Final dataset: 374 rows, 2024-01-05 to 2025-01-19 (his tenure ends
  20 Jan 2025). Spot-checked a random sample -- genuine, substantial
  transcripts with authentic White House formatting.

# USA — Donald Trump: Coverage & Validation Notes

## Source
Primary source: the [Senate Democratic Caucus's Trump Transcripts
archive](https://www.democrats.senate.gov/newsroom/trump-transcripts),
republishing Roll Call Factbase transcripts. This became the primary
source after whitehouse.gov removed official transcripts from its site
in late May 2025. A small number of early rows (Jan 19 – Apr 30, 2025)
come from an earlier scrape of whitehouse.gov itself, before that
removal; that original source is no longer live and cannot be
re-scraped if ever lost, so this early slice should be treated as
irreplaceable and backed up carefully.

## Coverage
- **Date range:** 2025-01-19 to 2026-07-13
- **Total rows:** 521
- **Content type breakdown (`likely_speech`):** 76 "yes", 365 "maybe",
  80 "no" — all retained, per the project's requirement to keep every
  content type with a classification column rather than filtering at
  scrape time (see bug note below).

## Bug found and fixed (Aug 2026)
An early version of the scraper's page-processing loop included:
```python
if article.likely_speech == "no":
    continue
```
This silently **dropped** any article whose title-keyword classifier
guessed "not a speech" (e.g. "Meets with...", "Holds a Bilat with...",
"Attends a Ceremony at..."), instead of keeping it with a classification
label for downstream filtering. This directly conflicted with the
project's methodology decision to retain all content types.

A separate, smaller issue was also found and fixed: the speaker-label
match in `_fetch_article` only accepted `"president trump"` and
`"trump"`, missing pages using `"president donald trump"` — broadened
to catch that variant too, though this turned out not to be the actual
cause of the missing rows in this case.

**Fix:** removed the `likely_speech == "no"` skip. A full re-scrape
after the fix recovered rows previously dropped across the entire date
range (433 → 521 rows after re-merging the early-2025 rows and removing
6 confirmed exact-duplicate rows caused by pagination overlap).

## Validation approach
Given no independent structured export exists for this source, validation
was done by manually comparing the CSV against the source site's own
listing pages for specific date windows:

| Window checked | Source entries | Found in CSV | Result |
|---|---|---|---|
| 2026-07-01 to 2026-07-13 | 20 | 20 | All present, 0 missing |
| 2026-06-17 to 2026-06-29 | 19 unique* | 21 | All present, 0 missing (2 extra legitimate rows not visible in the checked source snippet) |

\* The source lists this window's Marc Caputo/Axios interview
(6.18.26) under two different URLs — a duplicate on the source's own
side, not a scraper error. Documented here so it isn't mistaken for a
scraping bug if seen again.

**Scope of validation:** these two windows (spanning ~40 entries) were
checked in full; the remaining ~480 rows were not individually spot
checked against the live source due to pagination access limits during
this review. Confidence in the rest of the dataset rests on: (1) the
bug fix was applied uniformly across the full re-scrape, not just the
checked windows, and (2) the two checked windows — one recent, one
~2 weeks earlier — both came back clean after the fix.

## Known limitations
- The source archive itself lags "today" by roughly 2–4 weeks at any
  given time (it updates periodically, not daily) — this is a property
  of the source, not a scraping gap.
- Jan–Apr 2025 rows come from a now-dead source (whitehouse.gov) and
  cannot be re-verified or re-scraped if lost — treat with extra care.
- Deduplication is based on exact match of (date, title, full_text);
  near-duplicates with minor text differences would not be caught by
  this method.

# Mexico — Claudia Sheinbaum Pardo & Andrés Manuel López Obrador (AMLO):
# Coverage & Validation Notes

## Source
Primary source: gob.mx Presidencia archive (bot-protected, scraped via
curl_cffi with chrome impersonation).
- Sheinbaum (current term): `gob.mx/presidencia/es/archivo/articulos`,
  individual articles under `/presidencia/articulos/...`.
- AMLO (2018-2024 term, Jan-Sep 2024 covered here): after the
  administration change, his content moved to `gob.mx/amlo/...` --
  the old `/presidencia/articulos/...` URLs for his content now
  redirect to the homepage (confirmed via manual browser test, not
  just bot detection). Listing: `gob.mx/amlo/archivo/articulos`,
  articles under `/amlo/articulos/...`.

## Coverage
- **Sheinbaum:** 901 rows, 2024-10-02 (inauguration) to 2026-08-09,
  EXCLUDING 2026-07-09 to 2026-07-27 (already uploaded separately by
  Ginette's team -- removed here to avoid duplication when merged).
- **AMLO:** 254 rows, 2024-01-02 to 2024-09-30 (his last day in office).
- Combined: continuous coverage 2024-01-02 to 2026-08-09 (excluding the
  above window), across both presidents.

## Bugs found and fixed (Aug 2026)
Building the Sheinbaum scraper from scratch surfaced three real bugs,
found through iterative testing rather than a single validation pass:

1. **Wrong date source.** First attempt used a `<div class="date-marque">`
   element found on article pages -- turned out to be an unrelated
   sitewide "latest headlines" ticker widget, not the article's own
   date. Every article was getting today's/recent dates regardless of
   its actual content. Fixed by using the listing page's own
   `<time date="...">` attribute instead, which is genuinely
   per-article and reliable.

2. **Multi-paragraph speeches truncated to one sentence.** The site
   only labels the FIRST paragraph of a speaker's turn with a
   `<strong>` tag; all following paragraphs in that same turn are
   unlabeled plain `<p>` tags. Initial extraction required a label on
   every paragraph, so only the opening line of most speeches was
   captured (avg. text length ~3,100 chars). Fixed by tracking "current
   speaker" across unlabeled paragraphs until a new labeled speaker (or
   a section-break marker) appears. After the fix, avg. text length
   rose to ~22,000-27,000 chars -- a more plausible length for full
   press conference transcripts including Q&A.

3. **Unrecognized speakers (moderator, crowd chants) leaking through.**
   A logic bug meant that ANY labeled paragraph got appended regardless
   of whether the speaker matched Sheinbaum's name, as long as it
   wasn't on an explicit exclude list. This let moderator introductions
   and crowd "¡Viva!" chants leak into her attributed text. Fixed by
   flipping the logic: only append when the speaker is POSITIVELY
   confirmed as her, not merely "not on the exclude list."

For AMLO, the older site template (pre-Oct 2024) turned out to have no
`<strong>` tags at all -- speaker labels are plain text like
"PRESIDENTE ANDRÉS MANUEL LÓPEZ OBRADOR: ..." Required a different,
text-pattern-based speaker detection (all-caps text before a colon)
rather than the tag-based approach used for Sheinbaum.

## Validation approach
- **Automated checks** across full datasets: null date count (0 for
  both), duplicate detection (6 confirmed exact duplicates removed from
  Sheinbaum's 927-row initial pull, caused by the same kind of
  pagination-boundary overlap seen in the Trump dataset; 0 duplicates
  in AMLO's 254 rows), text-length distribution sanity checks.
- **Manual leak-checks**: searched both datasets for common other-speaker
  identifiers (governors, secretaries, moderator, crowd). All matches
  found were confirmed to be Sheinbaum/AMLO using those words naturally
  in their own speech (e.g. "I want to thank the Secretary of..."), not
  actual leaked paragraphs from other speakers.
- **Source spot-checks**: for Sheinbaum, two windows (2026-07-01 to
  07-13, and 2026-06-17 to 06-29) were checked against the live listing
  page -- both came back with zero missing entries. For AMLO, the
  2024-06-10 to 06-20 window was checked the same way; one apparent
  discrepancy (source showing 2 entries for 06-10, dataset showing 1)
  turned out to be correct: the second entry was a press conference by
  Sheinbaum as president-elect during the transition, correctly
  excluded from AMLO's own dataset.
- **Full manual read-through**: one complete Sheinbaum transcript
  (Reforestación, Aug 9 2026) read start to finish -- coherent, no
  leaked or duplicated content, natural beginning and ending.

**Scope of validation:** as with Trump, these spot-checks cover
specific windows (~40-50 entries total across both leaders), not every
row individually. Confidence in the rest rests on the same fixes being
applied uniformly across the full re-scrape, plus multiple independent
windows (spanning different months/years) coming back clean.

## Known limitations
- AMLO's original source (`gob.mx/presidencia/articulos/...` for his
  term) is dead -- pages redirect to the homepage. Cannot be
  re-scraped or re-verified from that original path if the `/amlo/...`
  path is ever also removed. Treat AMLO's dataset with the same care
  as Trump's Jan-Apr 2025 whitehouse.gov-sourced rows.
- The source site is intermittently flaky (~500 errors observed on
  both listing and article pages, self-recovering on retry most of the
  time). A listing page that fails all retries would be silently
  skipped with no visible gap in the output -- this is a known risk,
  not something this validation pass can fully rule out. If exact
  per-day completeness ever matters for analysis, this is the first
  place to check.
- Deduplication is based on exact match of (date, title); near-duplicates
  with minor text differences would not be caught.


# Mexico — Claudia Sheinbaum Pardo & Andrés Manuel López Obrador (AMLO):
# Coverage & Validation Notes

## Source
Primary source: gob.mx Presidencia archive (bot-protected, scraped via
curl_cffi with chrome impersonation).
- Sheinbaum (current term): `gob.mx/presidencia/es/archivo/articulos`,
  individual articles under `/presidencia/articulos/...`.
- AMLO (2018-2024 term, Jan-Sep 2024 covered here): after the
  administration change, his content moved to `gob.mx/amlo/...` --
  the old `/presidencia/articulos/...` URLs for his content now
  redirect to the homepage (confirmed via manual browser test, not
  just bot detection). Listing: `gob.mx/amlo/archivo/articulos`,
  articles under `/amlo/articulos/...`.

## Coverage
- **Sheinbaum:** 901 rows, 2024-10-02 (inauguration) to 2026-08-09,
  EXCLUDING 2026-07-09 to 2026-07-27 (already uploaded separately by
  Ginette's team -- removed here to avoid duplication when merged).
- **AMLO:** 254 rows, 2024-01-02 to 2024-09-30 (his last day in office).
- Combined: continuous coverage 2024-01-02 to 2026-08-09 (excluding the
  above window), across both presidents.

## Bugs found and fixed (Aug 2026)
Building the Sheinbaum scraper from scratch surfaced three real bugs,
found through iterative testing rather than a single validation pass:

1. **Wrong date source.** First attempt used a `<div class="date-marque">`
   element found on article pages -- turned out to be an unrelated
   sitewide "latest headlines" ticker widget, not the article's own
   date. Every article was getting today's/recent dates regardless of
   its actual content. Fixed by using the listing page's own
   `<time date="...">` attribute instead, which is genuinely
   per-article and reliable.

2. **Multi-paragraph speeches truncated to one sentence.** The site
   only labels the FIRST paragraph of a speaker's turn with a
   `<strong>` tag; all following paragraphs in that same turn are
   unlabeled plain `<p>` tags. Initial extraction required a label on
   every paragraph, so only the opening line of most speeches was
   captured (avg. text length ~3,100 chars). Fixed by tracking "current
   speaker" across unlabeled paragraphs until a new labeled speaker (or
   a section-break marker) appears. After the fix, avg. text length
   rose to ~22,000-27,000 chars -- a more plausible length for full
   press conference transcripts including Q&A.

3. **Unrecognized speakers (moderator, crowd chants) leaking through.**
   A logic bug meant that ANY labeled paragraph got appended regardless
   of whether the speaker matched Sheinbaum's name, as long as it
   wasn't on an explicit exclude list. This let moderator introductions
   and crowd "¡Viva!" chants leak into her attributed text. Fixed by
   flipping the logic: only append when the speaker is POSITIVELY
   confirmed as her, not merely "not on the exclude list."

For AMLO, the older site template (pre-Oct 2024) turned out to have no
`<strong>` tags at all -- speaker labels are plain text like
"PRESIDENTE ANDRÉS MANUEL LÓPEZ OBRADOR: ..." Required a different,
text-pattern-based speaker detection (all-caps text before a colon)
rather than the tag-based approach used for Sheinbaum.

## Validation approach
- **Automated checks** across full datasets: null date count (0 for
  both), duplicate detection (6 confirmed exact duplicates removed from
  Sheinbaum's 927-row initial pull, caused by the same kind of
  pagination-boundary overlap seen in the Trump dataset; 0 duplicates
  in AMLO's 254 rows), text-length distribution sanity checks.
- **Manual leak-checks**: searched both datasets for common other-speaker
  identifiers (governors, secretaries, moderator, crowd). All matches
  found were confirmed to be Sheinbaum/AMLO using those words naturally
  in their own speech (e.g. "I want to thank the Secretary of..."), not
  actual leaked paragraphs from other speakers.
- **Source spot-checks**: for Sheinbaum, two windows (2026-07-01 to
  07-13, and 2026-06-17 to 06-29) were checked against the live listing
  page -- both came back with zero missing entries. For AMLO, the
  2024-06-10 to 06-20 window was checked the same way; one apparent
  discrepancy (source showing 2 entries for 06-10, dataset showing 1)
  turned out to be correct: the second entry was a press conference by
  Sheinbaum as president-elect during the transition, correctly
  excluded from AMLO's own dataset.
- **Full manual read-through**: one complete Sheinbaum transcript
  (Reforestación, Aug 9 2026) read start to finish -- coherent, no
  leaked or duplicated content, natural beginning and ending.

**Scope of validation:** as with Trump, these spot-checks cover
specific windows (~40-50 entries total across both leaders), not every
row individually. Confidence in the rest rests on the same fixes being
applied uniformly across the full re-scrape, plus multiple independent
windows (spanning different months/years) coming back clean.

## Translation
Both datasets translated to English via `translate_csv.py --language es`
(Google Translate primary, MyMemoryTranslator fallback), adding
`title_en` and `full_text_en` columns alongside the Spanish originals.
- Sheinbaum: 901/901 rows translated, 0 failed chunks.
- AMLO: 254/254 rows translated, 0 failed chunks.

One chunk initially failed on both translators and left a
`[TRANSLATION FAILED FOR THIS SECTION: ...]` placeholder in one
Sheinbaum row (2024-10-15, US-Mexico CEO summit results). Root cause:
the MyMemoryTranslator fallback was being passed a bare language code
(`"es"`) instead of the locale-formatted code it expects (`"es-ES"`),
so it rejected the request outright. Fixed in `translate_helper.py` by
adding a source-language mapping for the fallback translator; affected
row was cleared and successfully re-translated. Worth checking for the
same issue on any other language if this fallback path triggers again
elsewhere (e.g. Moldova, once that source is identified).

## Known limitations
- AMLO's original source (`gob.mx/presidencia/articulos/...` for his
  term) is dead -- pages redirect to the homepage. Cannot be
  re-scraped or re-verified from that original path if the `/amlo/...`
  path is ever also removed. Treat AMLO's dataset with the same care
  as Trump's Jan-Apr 2025 whitehouse.gov-sourced rows.
- The source site is intermittently flaky (~500 errors observed on
  both listing and article pages, self-recovering on retry most of the
  time). A listing page that fails all retries would be silently
  skipped with no visible gap in the output -- this is a known risk,
  not something this validation pass can fully rule out. If exact
  per-day completeness ever matters for analysis, this is the first
  place to check.
- Deduplication is based on exact match of (date, title); near-duplicates
  with minor text differences would not be caught.