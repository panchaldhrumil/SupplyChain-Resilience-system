from pipeline.config import IMPACT_MAP

def _get_impact(title):
    title_lower = title.lower()
    sectors_found, companies_found = [], []

    for keywords, sectors, companies in IMPACT_MAP:
        if any(kw in title_lower for kw in keywords):
            sectors_found.extend(sectors)
            companies_found.extend(companies)

    seen_s, seen_c = set(), set()
    unique_sectors, unique_companies = [], []
    for s in sectors_found:
        if s not in seen_s:
            seen_s.add(s)
            unique_sectors.append(s)
    for c in companies_found:
        if c not in seen_c:
            seen_c.add(c)
            unique_companies.append(c)

    if not unique_sectors:
        unique_sectors   = ["Broader Market"]
        unique_companies = ["NIFTY50"]

    return " | ".join(unique_sectors), " | ".join(unique_companies[:15])
