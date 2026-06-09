# Country-code → display region for the language submenu grouping.
# Covers all ISO 3166-1 alpha-2 country codes so any future firmware language
# is automatically placed in the right submenu.  Only truly non-country codes
# (regional variants, custom codes, etc.) fall through to "Other".
# Key = 2-letter ISO country code (upper-case, matching lang[2:].upper()).

LANG_REGION = {
    # ── Americas ─────────────────────────────────────────────────────────────
    # North America
    "CA": "Americas", "GL": "Americas", "MX": "Americas", "PM": "Americas",
    "US": "Americas",
    # Caribbean
    "AG": "Americas", "AI": "Americas", "AN": "Americas", "AW": "Americas",
    "BB": "Americas", "BL": "Americas", "BM": "Americas", "BQ": "Americas",
    "BS": "Americas", "CU": "Americas", "CW": "Americas", "DM": "Americas",
    "DO": "Americas", "GD": "Americas", "GP": "Americas", "HT": "Americas",
    "JM": "Americas", "KN": "Americas", "KY": "Americas", "LC": "Americas",
    "MF": "Americas", "MQ": "Americas", "MS": "Americas", "PR": "Americas",
    "SX": "Americas", "TC": "Americas", "TT": "Americas", "VC": "Americas",
    "VG": "Americas", "VI": "Americas",
    # Central America
    "BZ": "Americas", "CR": "Americas", "GT": "Americas", "HN": "Americas",
    "NI": "Americas", "PA": "Americas", "SV": "Americas",
    # South America
    "AR": "Americas", "BO": "Americas", "BR": "Americas", "CL": "Americas",
    "CO": "Americas", "EC": "Americas", "FK": "Americas", "GF": "Americas",
    "GY": "Americas", "PE": "Americas", "PY": "Americas", "SR": "Americas",
    "UM": "Americas", "UY": "Americas", "VE": "Americas",

    # ── Europe ───────────────────────────────────────────────────────────────
    # Western
    "AD": "Europe", "AT": "Europe", "BE": "Europe", "CH": "Europe",
    "DE": "Europe", "FR": "Europe", "GB": "Europe", "GG": "Europe",
    "GI": "Europe", "IE": "Europe", "IM": "Europe", "JE": "Europe",
    "LI": "Europe", "LU": "Europe", "MC": "Europe", "NL": "Europe",
    "PT": "Europe",
    # Northern
    "AX": "Europe", "DK": "Europe", "EE": "Europe", "FI": "Europe",
    "FO": "Europe", "IS": "Europe", "LT": "Europe", "LV": "Europe",
    "NO": "Europe", "SE": "Europe", "SJ": "Europe",
    # Southern
    "AL": "Europe", "BA": "Europe", "CY": "Europe", "ES": "Europe",
    "GR": "Europe", "HR": "Europe", "IT": "Europe", "ME": "Europe",
    "MK": "Europe", "MT": "Europe", "RS": "Europe", "SI": "Europe",
    "SM": "Europe", "VA": "Europe", "XK": "Europe",
    # Eastern
    "BG": "Europe", "BY": "Europe", "CZ": "Europe", "HU": "Europe",
    "MD": "Europe", "PL": "Europe", "RO": "Europe", "RU": "Europe",
    "SK": "Europe", "UA": "Europe",

    # ── Middle East & Caucasus ───────────────────────────────────────────────
    # Caucasus
    "AM": "Middle East & Caucasus", "AZ": "Middle East & Caucasus",
    "GE": "Middle East & Caucasus",
    # Middle East
    "AE": "Middle East & Caucasus", "BH": "Middle East & Caucasus",
    "IL": "Middle East & Caucasus", "IQ": "Middle East & Caucasus",
    "IR": "Middle East & Caucasus", "JO": "Middle East & Caucasus",
    "KW": "Middle East & Caucasus", "LB": "Middle East & Caucasus",
    "OM": "Middle East & Caucasus", "PS": "Middle East & Caucasus",
    "QA": "Middle East & Caucasus", "SA": "Middle East & Caucasus",
    "SY": "Middle East & Caucasus", "TR": "Middle East & Caucasus",
    "YE": "Middle East & Caucasus",

    # ── Africa ───────────────────────────────────────────────────────────────
    # Northern
    "DZ": "Africa", "EG": "Africa", "EH": "Africa", "LY": "Africa",
    "MA": "Africa", "SD": "Africa", "TN": "Africa",
    # Western
    "BF": "Africa", "BJ": "Africa", "CI": "Africa", "CV": "Africa",
    "GH": "Africa", "GM": "Africa", "GN": "Africa", "GW": "Africa",
    "LR": "Africa", "ML": "Africa", "MR": "Africa", "NE": "Africa",
    "NG": "Africa", "SL": "Africa", "SN": "Africa", "ST": "Africa",
    "TG": "Africa",
    # Central
    "AO": "Africa", "CD": "Africa", "CF": "Africa", "CG": "Africa",
    "CM": "Africa", "GA": "Africa", "GQ": "Africa", "TD": "Africa",
    # Eastern
    "BI": "Africa", "DJ": "Africa", "ER": "Africa", "ET": "Africa",
    "IO": "Africa", "KE": "Africa", "KM": "Africa", "MG": "Africa",
    "MU": "Africa", "MW": "Africa", "MZ": "Africa", "RE": "Africa",
    "RW": "Africa", "SC": "Africa", "SH": "Africa", "SO": "Africa",
    "SS": "Africa", "TF": "Africa", "TZ": "Africa", "UG": "Africa",
    "YT": "Africa", "ZM": "Africa", "ZW": "Africa",
    # Southern
    "BW": "Africa", "LS": "Africa", "NA": "Africa", "SZ": "Africa",
    "ZA": "Africa",

    # ── Asia ─────────────────────────────────────────────────────────────────
    # Central
    "AF": "Asia", "KG": "Asia", "KZ": "Asia", "MN": "Asia",
    "TJ": "Asia", "TM": "Asia", "UZ": "Asia",
    # South
    "BD": "Asia", "BT": "Asia", "IN": "Asia", "LK": "Asia",
    "MV": "Asia", "NP": "Asia", "PK": "Asia",
    # East
    "CN": "Asia", "HK": "Asia", "JP": "Asia", "KP": "Asia",
    "KR": "Asia", "MO": "Asia", "TW": "Asia",
    # Southeast
    "BN": "Asia", "ID": "Asia", "KH": "Asia", "LA": "Asia",
    "MM": "Asia", "MY": "Asia", "PH": "Asia", "SG": "Asia",
    "TH": "Asia", "TL": "Asia", "VN": "Asia",

    # ── Oceania ──────────────────────────────────────────────────────────────
    "AS": "Oceania", "AU": "Oceania", "CC": "Oceania", "CK": "Oceania",
    "CX": "Oceania", "FJ": "Oceania", "FM": "Oceania", "GU": "Oceania",
    "HM": "Oceania", "KI": "Oceania", "MH": "Oceania", "MP": "Oceania",
    "NC": "Oceania", "NF": "Oceania", "NR": "Oceania", "NU": "Oceania",
    "NZ": "Oceania", "PF": "Oceania", "PG": "Oceania", "PN": "Oceania",
    "PW": "Oceania", "SB": "Oceania", "TK": "Oceania", "TO": "Oceania",
    "TV": "Oceania", "VU": "Oceania", "WF": "Oceania", "WS": "Oceania",
}

LANG_REGION_ORDER = [
    "Americas",
    "Europe",
    "Middle East & Caucasus",
    "Africa",
    "Asia",
    "Oceania",
]
