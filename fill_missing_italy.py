"""
Fetches specific known URLs directly (bypassing Wayback discovery entirely)
and appends any new ones to italy.csv. Used to backfill entries the
Wayback CDX API hasn't crawled yet (recency lag) but that we already know
the real URL for, e.g. from manually browsing the site's own listing page.
"""

import pandas as pd

from src.config_loader import load_config, get_leader_config
from src.scraper_italy import _fetch_article
from src.text_processing import in_date_range
from src.utils import write_csv

# Paste the specific missing URLs here (from italy_manual_list.txt / the
# comparison script's "MISSING from our CSV" output). Use full URLs.
MISSING_URLS = [
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-prime-minister-montenegro-portugal/32377",
    "https://www.governo.it/en/articolo/president-meloni-s-address-police-officers-involved-special-local-prevention-and-patrol",
    "https://www.governo.it/en/articolo/new-draft-law-security-president-meloni-s-video-message/32357",
    "https://www.governo.it/en/articolo/president-meloni-addresses-meeting-provincial-committee-public-order-and-security",
    "https://www.governo.it/en/articolo/president-meloni-s-press-conference-introduction-2026-nato-summit/32303",
    "https://www.governo.it/en/articolo/design-technology-artificial-intelligence-agenda-alliance-between-italy-and-india/31859",
    "https://www.governo.it/en/articolo/forum-imprenditoriale-italia-germania-lintervento-del-presidente-meloni/30937",
    "https://www.governo.it/en/articolo/italy-has-charted-course-and-today-europe-following-it-video-message-president-meloni/31986",
    "https://www.governo.it/en/articolo/joint-op-ed-president-council-ministers-giorgia-meloni-and-prime-minister-japan-sanae",
    "https://www.governo.it/en/articolo/new-draft-law-security-president-meloni-s-video-message/32357",
    "https://www.governo.it/en/articolo/president-meloni-attends-confindustria-general-assembly/28886",
    "https://www.governo.it/en/articolo/president-meloni-s-address-italy-t-rkiye-business-forum/28358",
    "https://www.governo.it/en/articolo/president-meloni-s-address-joint-session-parliament-commemorate-pope-francis/28285",
    "https://www.governo.it/en/articolo/president-meloni-s-address-laying-groundwork-jobs-africa-core-infrastructure-and-business",
    "https://www.governo.it/en/articolo/president-meloni-s-address-police-officers-involved-special-local-prevention-and-patrol",
    "https://www.governo.it/en/articolo/president-meloni-s-beginning-year-press-conference/30735",
    "https://www.governo.it/en/articolo/president-meloni-s-briefing-chamber-deputies-government-s-activities/31521",
    "https://www.governo.it/en/articolo/president-meloni-s-closing-press-point-during-her-visit-saudi-arabia/27566",
    "https://www.governo.it/en/articolo/president-meloni-s-closing-press-point-g7-summit/29043",
    "https://www.governo.it/en/articolo/president-meloni-s-closing-remarks-second-italia-africa-summit/31135",
    "https://www.governo.it/en/articolo/president-meloni-s-letter-messaggero-newspaper-anniversary-earthquake-central-italy/29628",
    "https://www.governo.it/en/articolo/president-meloni-s-message-2025-federmanager-national-assembly/30189",
    "https://www.governo.it/en/articolo/president-meloni-s-message-2025-med-conference/30102",
    "https://www.governo.it/en/articolo/president-meloni-s-message-2026-farmindustria-assembly/32166",
    "https://www.governo.it/en/articolo/president-meloni-s-message-2026-national-meeting-italian-red-cross/31758",
    "https://www.governo.it/en/articolo/president-meloni-s-message-confartigianato-national-meeting/30435",
    "https://www.governo.it/en/articolo/president-meloni-s-message-event-ai-and-work-managing-transformation-multiplying",
    "https://www.governo.it/en/articolo/president-meloni-s-message-event-cambio-di-paradigma-forum-delleconomia-del-nuovo-mondo",
    "https://www.governo.it/en/articolo/president-meloni-s-message-second-edition-space-economy-states-general/30201",
    "https://www.governo.it/en/articolo/president-meloni-s-opening-remarks-first-mattei-plan-steering-committee-meeting/31386",
    "https://www.governo.it/en/articolo/president-meloni-s-press-conference-introduction-2026-nato-summit/32303",
    "https://www.governo.it/en/articolo/president-meloni-s-press-point-following-her-visit-jordan-and-lebanon/26894",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-chancellor-merz/28759",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-federal-chancellor-austria-christian-stocker/29272",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-fifth-italy-algeria-intergovernmental-summit/29333",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-following-conference-maritime-navigation-through-strait",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-following-her-meeting-prime-minister-tusk-poland/31777",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-president-aliyev-azerbaijan/31742",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-president-christodoulides-republic-cyprus/31225",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-president-ruto-kenya/31605",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-president-tebboune-algeria/31404",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-president-zelensky-ukraine-recovery-conference/29245",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-prime-minister-kingdom-denmark/28804",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-prime-minister-modi-india/31872",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-prime-minister-montenegro-portugal/32377",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-prime-minister-plenkovi-republic-croatia/30378",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-prime-minister-takaichi-japan/32101",
    "https://www.governo.it/en/articolo/president-meloni-s-press-statement-taoiseach-ireland-miche-l-martin/31915",
    "https://www.governo.it/en/articolo/president-meloni-s-remarks-uk-prime-minister-keir-starmer/29014",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-2025-coast-guard-global-summit/30084",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-2026-confindustria-agm/32046",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-20th-confederal-congress-cisl/29368",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-ceremony-feast-day-saint-francis/29965",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-cross-border-breakthrough-ceremony-brenner-base-tunnel/29805",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-event-l-agricoltura-il-futuro/31809",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-event-vote-women-80-years-italian-democracy/31427",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-italy-algeria-business-forum/29377",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-italy-uae-business-forum/27749",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-leonardo-awards-ceremony/28277",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-master-art-italian-cuisine-awards-ceremony/28120",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-national-meeting-federalberghi/31672",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-official-launch-apple-cable-car/30363",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-official-presentation-louis-vuitton-cup-and-americas-cup-trophies",
    "https://www.governo.it/en/articolo/president-meloni-s-speech-opening-ceremony-new-piazza-pia-rome/27432",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-18th-conference-italian-ambassadors/30907",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-2025-civil-protection-general-assembly/28184",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-2025-farmindustria-general-assembly/29196",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-2025-general-assembly-centromarca/28952",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-61st-national-congress-notaries/30111",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-80th-anniversary-ance/32165",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-agriculture/29334",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-ahead-workers-day-may-1st/28364",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-border-security-summit-london/28087",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-corri-libera-united-against-violence-against-women",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-eu-return-regulation/32119",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-european-parliament-mattei-plan-africa-and-global-0",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-event-italy-and-its-nrrp/31936",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-fii-priority-europe-2026-summit/32125",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-general-assembly-confcommercio-imprese-l-italia/28964",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-her-visit-saudi-arabia-qatar-and-united-arab-emirates",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-inail-annual-report-2024/29188",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-international-tourism-forum/31012",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-jubilee-youth/29409",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-marking-25th-anniversary-agenzia-delle-entrate/31416",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-national-conference-childhood-and-adolescence/29944",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-national-made-italy-day/31568",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-presentation-event-annual-report-parliament-addiction",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-reducing-financial-burden-energy-bills-households-and",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-release-alberto-trentini-and-mario-burl/30741",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-reopening-basilica-saint-benedict-norcia/30202",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-states-general-conference-italy-s-minor-marine-islands",
    "https://www.governo.it/en/articolo/president-meloni-s-video-message-third-edition-risorsa-mare-forum/29883",
    "https://www.governo.it/en/articolo/president-melonis-remarks-president-kyrgyz-republic/28902",
    "https://www.governo.it/en/articolo/president-melonis-remarks-president-republic-kazakhstan-kassym-jomart-tokayev/28865",
    "https://www.governo.it/en/articolo/president-melonis-remarks-president-republic-tajikistan/28904",
    "https://www.governo.it/en/articolo/president-melonis-remarks-president-republic-uzbekistan-shavkat-mirziyoyev/28870",
    "https://www.governo.it/en/articolo/president-melonis-remarks-president-turkmenistan/28903",
    "https://www.governo.it/en/articolo/video-message-general-assembly-italian-professional-accountants/22552",

]

def main():
    config = load_config()
    leader_config = get_leader_config("Italy", config)
    start_date = config["date_range"]["start"]
    end_date = config["date_range"]["end"]

    existing_df = pd.read_csv("data/processed/italy.csv")
    existing_urls = set(existing_df["source_url"])

    new_rows = []
    for url in MISSING_URLS:
        if url in existing_urls:
            print(f"  already have: {url}")
            continue
        article = _fetch_article(url, leader_config)
        if article is None:
            print(f"  [skip] could not fetch or not attributed to Meloni: {url}")
            continue
        if not in_date_range(article.date, start_date, end_date):
            print(f"  [skip] outside date range ({article.date}): {url}")
            continue
        new_rows.append(article)
        print(f"  added: {article.title}")

    if new_rows:
        write_csv(new_rows, "data/processed/italy.csv")
    print(f"\nDone. Added {len(new_rows)} new rows.")


if __name__ == "__main__":
    main()