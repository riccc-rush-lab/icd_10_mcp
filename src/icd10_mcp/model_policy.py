"""Dependency-free artifact contract shared by optional staging and admission."""

MODEL_PINS = {
    "ner": (
        "OpenMed/OpenMed-NER-DiseaseDetect-TinyMed-135M",
        "dcb346697f933cea9d9c9cb27b58a1faf8f08f5e",
    ),
    "pii": (
        "OpenMed/OpenMed-PII-ClinicalE5-Small-33M-v1",
        "2ea947130eb28d610ceb96472af0b694fce9c344",
    ),
}
MODEL_LICENSE = "apache-2.0"
ALLOWED_MODEL_FILES = frozenset(
    {
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "vocab.txt",
        "model.safetensors",
        "README.md",
    }
)
REQUIRED_MODEL_FILES = frozenset(
    {
        "config.json",
        "tokenizer_config.json",
        "model.safetensors",
    }
)
