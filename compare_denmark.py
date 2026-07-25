"""
One-off verification: compares our scraped Denmark CSV against the list
of speech URLs manually copied from the live site's date-filtered view
(01-01-2023 to 31-12-2026), to confirm we captured everything real.
"""

import pandas as pd

# Slugs manually copied from stm.dk's own date-filtered speech list.
site_slugs = """
statsministerens-aabningstale-paa-folkemoedet-11-juni-2026
valgudskrivelse-den-26-februar-2026
statsministerens-indledning-til-pressestatement-i-elyseepalaeet-den-28-januar-2026
statsminister-mette-frederiksens-nytaarstale-1-januar-2026
statsminister-mette-frederiksens-tale-til-aarsdagen-for-krystalnatten-i-koebenhavn-den-9-november-2025
statsministeren-mette-frederiksens-indledning-til-borgermoede-om-kronikerpakker-den-27-oktober-2025
statsminister-mette-frederiksens-tale-ved-folketingets-aabning-den-7-oktober-2025
statsministerens-tale-ved-aabningsplenaren-til-european-political-community-d-2-oktober
statsministerens-tale-til-copenhagen-competitiveness-summit-den-1-oktober-2025
statsministerens-tale-om-hybride-angreb
statsministerens-tale-til-undskyldningsarrangement-i-spiralsagen-den-24-september-2025
statsministerens-tale-til-flagdag-for-danmarks-udsendte-den-5-september-2025-1
statsministerens-praesentation-af-de-danske-formandskabsprioriteter-i-strasbourg
statsministerens-tale-ved-aabningsceremonien-for-det-danske-eu-formandskab-paa-aarhus-raadhus-3-juli-2025
statsministerens-aabningstale-paa-folkemoedet-12-juni-2025
statsministerens-tale-til-grundlovsdag-paa-roedding-hoejskole
statsministerens-indledning-til-lancering-af-brev-om-konventioner-den-22-maj-2025
statsminister-mette-frederiksens-tale-til-folketingets-afslutningsdebat-den-21-maj-2025
statsministerens-tale-ved-80-aaret-for-danmarks-befrielse-den-4-maj-2025
statsminister-mette-frederiksens-tale-til-kl-topmoede-2025
statsminister-mette-frederiksens-nytaarstale-den-1-januar-2025
statsministerens-tale-ved-folketingets-aabning-den-1-oktober-2024
statsminister-mette-frederiksens-tale-ved-flagdagen-for-danmarks-udsendte-den-5-september-2024
statsministerens-indledning-til-lancering-af-skaermalliance
statsministerens-tale-i-normandiet-ved-markeringen-af-80-aarsdagen-for-d-dag
statsminister-mette-frederiksens-tale-ved-grundlovsfejring-i-folketinget-den-5-juni-2024
statsministerens-tale-ved-folketingets-afslutning-den-29-maj-2024
statsminister-mette-frederiksens-tale-til-naturmoedet-2024
statsminister-mette-frederiksens-tale-ved-copenhagen-democracy-summit-2024
statsministerens-tale-til-dm-i-skills-2024
statsminister-mette-frederiksens-tale-til-regionernes-politiske-topmoede
statsministerens-tale-ved-aabent-debatmoede-i-landstingssalen-om-ukraine-den-19-marts-2024
statsminister-mette-frederiksens-tale-til-kick-off-regeringens-arbejde-med-styrket-engagement-i-afrika
mette-frederiksens-tale-til-kvinfo
statsminister-mette-frederiksens-tale-til-fredsgudstjeneste-paa-2-aarsdagen-for-angrebet-paa-ukraine
statsminister-mette-frederiksens-tale-ved-stormoedet-om-aeldres-velfaerd-i-fredericia-den-30-januar-2024
statsminister-mette-frederiksens-tale-til-auschwitz-dag-den-27-januar-2024
statsminister-mette-frederiksens-tale-og-hm-kong-frederik-10s-budskab-til-folketinget
proklamation-af-tronskiftet-den-14-januar-2024
statsminister-mette-frederiksens-nytaarstale-den-1-januar-2024
statsminister-mette-frederiksens-tale-ved-krystalnatten-den-9-november-2023
statsminister-mette-frederiksens-tale-i-koebenhavns-synagoge-den-14-oktober-2023
statsministerens-tale-ved-folketingets-aabning-den-3-oktober-2023
statsminister-mette-frederiksens-tale-til-det-ukrainske-parlament
statsminister-mette-frederiksens-tale-i-folketinget-i-anledning-af-besoeg-fra-ukraines-praesident-zelenskyy
statsminister-mette-frederiksens-tale-ved-aabning-af-folkemoedet
statsminister-mette-frederiksens-tale-til-folketingets-afslutningsdebat-den-31-maj-2023
statsminister-mette-frederiksens-tale-ved-kommunalpolitisk-topmoede-den-16-marts-2023
statsminister-mette-frederiksens-tale-ved-demonstration-ved-den-russiske-ambassade-den-24-februar-2023
statsminister-mette-frederiksens-tale-ved-gudstjeneste-paa-aarsdagen-for-invasionen-af-ukraine-24-februar-2023
statsminister-mette-frederiksens-tale-ved-arrangement-paa-koebenhavns-raadhus-den-24-februar-2023
statsminister-mette-frederiksens-redegoerelse-til-folketinget-den-17-januar-2023
mette-frederiksens-nytaarstale-1-januar-2023
""".strip().splitlines()

site_slugs = set(site_slugs)
print(f"Site list: {len(site_slugs)} unique speeches")

df = pd.read_csv("data/processed/denmark.csv")
our_slugs = set(
    url.rstrip("/").split("/")[-1] for url in df["source_url"]
)
print(f"Our CSV:   {len(our_slugs)} rows, {len(our_slugs)} unique URLs")

missing_from_ours = site_slugs - our_slugs
extra_in_ours = our_slugs - site_slugs

print(f"\nOn site but MISSING from our CSV: {len(missing_from_ours)}")
for s in sorted(missing_from_ours):
    print(" -", s)

print(f"\nIn our CSV but NOT on the site's filtered list: {len(extra_in_ours)}")
for s in sorted(extra_in_ours):
    print(" -", s)