"""Refresh multilingual country/area names from the UN Statistics M49 table."""

import argparse
import json
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
M49_URL = "https://unstats.un.org/unsd/methodology/m49/overview/"
CANONICAL = {
    "US": "美国",
    "GB": "英国",
    "RU": "俄罗斯",
    "KR": "韩国",
    "KP": "朝鲜",
    "CD": "刚果（金）",
    "CG": "刚果（布）",
    "TZ": "坦桑尼亚",
    "BO": "玻利维亚",
    "VE": "委内瑞拉",
    "IR": "伊朗",
    "SY": "叙利亚",
    "LA": "老挝",
    "VN": "越南",
    "MD": "摩尔多瓦",
    "BN": "文莱",
    "CZ": "捷克",
    "CI": "科特迪瓦",
    "PS": "巴勒斯坦",
    "SZ": "斯威士兰",
    "HK": "中国香港",
    "MO": "中国澳门",
    "TR": "土耳其",
}
COMMON = {
    "US": ["United States", "American", "美国"],
    "GB": ["United Kingdom", "Britain", "British", "英国"],
    "RU": ["Russia", "Russian", "俄罗斯"],
    "KR": ["South Korea", "South Korean", "韩国"],
    "KP": ["North Korea", "North Korean", "朝鲜"],
    "CD": [
        "Democratic Republic of Congo",
        "DR Congo",
        "DRC",
        "Congo-Kinshasa",
        "刚果（金）",
    ],
    "CG": [
        "Republic of the Congo",
        "Republic of Congo",
        "Congo-Brazzaville",
        "刚果（布）",
        "刚果共和国",
    ],
    "GN": ["Republic of Guinea", "几内亚"],
    "TZ": ["Tanzania", "Tanzanian"],
    "BO": ["Bolivia", "Bolivian"],
    "VE": ["Venezuela", "Venezuelan"],
    "IR": ["Iran", "Iranian"],
    "SY": ["Syria", "Syrian"],
    "LA": ["Laos", "Lao PDR"],
    "VN": ["Vietnam", "Vietnamese"],
    "MD": ["Moldova"],
    "BN": ["Brunei"],
    "CZ": ["Czech Republic", "Czech"],
    "CI": ["Ivory Coast", "Ivorian", "Côte d'Ivoire"],
    "PS": ["Palestine"],
    "SZ": ["Eswatini", "Swaziland"],
    "TR": ["Turkey", "Turkish", "Türkiye"],
    "PG": ["PNG", "Papua New Guinea"],
    "BF": ["Burkinabe", "Burkinabè"],
    "ML": ["Malian"],
    "ZM": ["Zambian"],
    "ZW": ["Zimbabwean"],
    "GH": ["Ghanaian"],
    "NA": ["Namibian"],
    "BW": ["Botswanan"],
    "SN": ["Senegalese"],
    "ID": ["Indonesian"],
    "KZ": ["Kazakh", "Kazakhstani"],
    "UZ": ["Uzbek", "Uzbekistani"],
    "MN": ["Mongolian"],
}
AMBIGUOUS = {
    "SH": {"Santa Elena"},
    "GE": {"Georgia"},
    "JO": {"Jordan"},
    "TD": {"Chad"},
    "JE": {"Jersey"},
    "RE": {"Reunion", "Réunion", "Reunión"},
    "MS": {"Montserrat"},
}


def build_catalog(html: str) -> None:
    """Keep existing canonical names while adding names in six UN languages."""
    soup = BeautifulSoup(html, "html.parser")
    tables = {}
    for language in ("EN", "ZH", "FR", "ES", "RU", "AR"):
        table = soup.find(id="downloadTable" + language)
        if table is None:
            raise ValueError("Missing UN M49 language table")
        rows = [
            [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            for tr in table.find_all("tr")
        ]
        tables[language] = {row[10]: row for row in rows if len(row) > 11 and row[10]}
    if len(tables["EN"]) < 240:
        raise ValueError("Incomplete UN country/area catalog")
    entity_path = ROOT / "pipeline/config/entities.json"
    entities = json.loads(entity_path.read_text(encoding="utf-8"))
    old = entities["regions"]
    entries = []
    for code, english in tables["EN"].items():
        chinese = tables["ZH"][code]
        name = CANONICAL.get(code, chinese[8])
        aliases = {tables[lang][code][8] for lang in tables}
        aliases.update(COMMON.get(code, []))
        aliases.update(old.get(name, []))
        aliases.add(name)
        aliases.difference_update(AMBIGUOUS.get(code, set()))
        if code == "GE":
            aliases.update(["country of Georgia", "Georgian", "Republic of Georgia"])
        if code == "JO":
            aliases.update(["Jordanian", "Hashemite Kingdom of Jordan"])
        if code == "TD":
            aliases.update(["Republic of Chad", "Chadian"])
        # Ambiguous bare names match the wrong Congo or Korean jurisdiction.
        if code == "CG":
            aliases.discard("Congo")
            aliases.discard("刚果")
            aliases.discard("Конго")
            aliases.discard("الكونغو")
        if code == "KR":
            aliases.discard("Korean")
        entities["regions"][name] = sorted(aliases)
        entries.append(
            {
                "name": name,
                "iso2": code,
                "iso3": english[11],
                "english_name": english[8],
                "continent": chinese[3] or "极地",
                "subregion": chinese[5] or chinese[7] or "极地",
                "kind": "country_or_area",
            }
        )
    entries.append(
        {
            "name": "欧盟",
            "iso2": "EU",
            "iso3": "EU",
            "english_name": "European Union",
            "continent": "欧洲",
            "subregion": "区域组织",
            "kind": "organization",
        }
    )
    payload = {
        "basis": "UN M49 countries or areas; EU listed separately",
        "source_url": M49_URL,
        "items": entries,
    }
    for path, value in [
        (ROOT / "pipeline/config/countries.json", payload),
        (entity_path, entities),
    ]:
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"Updated {len(entries)} countries/areas and organizations")


def main() -> None:
    """Use a local official snapshot, or explicitly fetch the current table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()
    if args.snapshot:
        html = args.snapshot.read_text(encoding="utf-8")
    else:
        response = httpx.get(M49_URL, timeout=30)
        response.raise_for_status()
        html = response.text
    build_catalog(html)


if __name__ == "__main__":
    main()
