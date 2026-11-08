"""Explicit, independently acquired release profiles. No inferred current release."""

APRIL_ID = "icd10cm-2026-04-01"
FY2027_ID = "icd10cm-2026-10-01"

PROFILES = {
    APRIL_ID: {
        "release": {
            "id": APRIL_ID,
            "system": "ICD-10-CM",
            "fiscal_year": 2026,
            "effective_from": "2026-04-01",
            "effective_through": "2026-09-30",
        },
        "text_archive": "icd10cm-table-and-index-April-1-2026.zip",
        "xml_archive": "icd10cm-April-1-2026-XML.zip",
        "codes": "icd10cm-codes-April-1-2026.txt",
        "order": "icd10cm-order-April-1-2026.txt",
        "tabular": "icd10c-tabular-April-1-2026.xml",
        "indexes": {
            kind: f"icd10cm-{name}-April-1-2026-XML.xml"
            for kind, name in [
                ("diseases", "index"),
                ("external_causes", "eindex"),
                ("drugs", "drug"),
                ("neoplasms", "neoplasm"),
            ]
        },
        "counts": (74719, 23467),
        "member_sha256": {
            "codes": "a7e2a77e4627ed55c8afe2b8a7ae22efcbab6b6b162d96cf145213772c1246ba",
            "order": "6dc95c9c7e96c734806e1682f4bf9df76251d60e99199bba0d375ba3dd11026b",
            "tabular": "fbbb7f6ee319eb0259e43d369ec50bc15af9a2c983d4440b936b3d70a53f7624",
            "diseases": "2dc67f728d05e765a9b7ffe7c74a5a2ce11c9492d58db00c72d83778ea6356ec",
            "external_causes": "91555639910deb29c341e538f7b6fd55f9fd39480a6d1656247badb0b9336504",
            "drugs": "c2d34259339f4ec27aa4822316716091568d8f477bc34ccae4946321ebce6524",
            "neoplasms": "2ea9b87e0a71e1da9522af7465b7a165ef47bbc484324a475a2046992a0201e8",
        },
    },
    FY2027_ID: {
        "release": {
            "id": FY2027_ID,
            "system": "ICD-10-CM",
            "fiscal_year": 2027,
            "effective_from": "2026-10-01",
            "effective_through": "2027-09-30",
        },
        "text_archive": "icd10cm-code-descriptions-2027.zip",
        "xml_archive": "icd10cm-table-and-index-2027.zip",
        "codes": "icd10cm-code-descriptions-2027/icd10cm-codes-2027.txt",
        "order": "icd10cm-code-descriptions-2027/icd10cm-order-2027.txt",
        "tabular": "icd10cm-table-and-index-2027/icd10cm-tabular_-2027.xml",
        "indexes": {
            kind: f"icd10cm-table-and-index-2027/icd10cm-{name}-2027.xml"
            for kind, name in [
                ("diseases", "index"),
                ("external_causes", "eindex"),
                ("drugs", "drug"),
                ("neoplasms", "neoplasm"),
            ]
        },
        "counts": (74879, 23524),
        "member_sha256": {
            "codes": "3c0583a38ee0e848f7dc0ac8ce88e8f001bbba8c6385ed825d44d46f6e5297c9",
            "order": "38981fb2c1226e2b92393cef7d921d2293494dd184b5ad039dde08e4b364265f",
            "tabular": "d778c97a5bb9da7d71645610e277f8db3bd302befa3b08d71dd5043715a74b2a",
            "diseases": "248e4a133996f986ba98821a411f0e8afee632a2de1d98f23e02fba8b6fd8a15",
            "external_causes": "3e2079305218ee7b430ee46243e89a1dcebdf361309b9e0ab3cd19fc22e2b87b",
            "drugs": "648f541db8b8c748558020dee59e8abf8c851fff3809a95ab3cee460873d8e31",
            "neoplasms": "c9c7baf1dc94ee433254945f9a69eedee6c0dd71ac86ec79b4d56121314f522e",
        },
    },
}


def get_profile(release_id):
    try:
        return PROFILES[release_id]
    except (KeyError, TypeError):
        raise ValueError("Unsupported release profile") from None
