"""
Structured version of german_learning_roadmap.md, just the A1 tiers for now
(detailed tiers get added here as you approach them — see the roadmap doc).

This is what gets pulled into the Claude system prompt as "current tier content."
"""

TIERS = {
    "A1.1": {
        "title": "First Contact",
        "grammar_focus": "sein (to be) conjugation, basic word order (Subject-Verb-Object)",
        "vocabulary": ["Hallo", "Guten Tag", "Tschüss", "Ich heiße...", "Wie heißt du?",
                        "Wie geht's?", "ja", "nein", "bitte", "danke"],
        "can_do": "Introduce yourself, greet someone, say how you're doing",
        "pronunciation_focus": []
    },
    "A1.2": {
        "title": "Numbers, Articles, Basic Nouns",
        "grammar_focus": "der/die/das (definite articles), numbers 0-100",
        "vocabulary": ["Tisch", "Haus", "Auto", "Frau", "Mann", "Kind", "eins", "zwei", "drei"],
        "can_do": "Count, state age, identify objects with correct article",
        "pronunciation_focus": ["ch sound (ich, nicht)", "umlauts (ü, ö, ä)"]
    },
    "A1.3": {
        "title": "Present Tense Verbs & Daily Actions",
        "grammar_focus": "Regular verb conjugation (-en endings), common irregular verbs (haben, gehen, machen)",
        "vocabulary": ["machen", "gehen", "haben", "heute", "morgen", "jetzt"],
        "can_do": "Describe a simple daily routine in present tense",
        "pronunciation_focus": []
    },
    "A1.4": {
        "title": "Food, Shopping, Numbers Beyond 100",
        "grammar_focus": "Accusative case (basic direct objects), 'Ich möchte...'",
        "vocabulary": ["Brot", "Wasser", "Apfel", "Was kostet das?", "Ich möchte..."],
        "can_do": "Order food, ask prices, express simple wants",
        "pronunciation_focus": []
    },
    "A1.5": {
        "title": "Family, Possession, Adjectives",
        "grammar_focus": "Possessive pronouns (mein, dein, sein), basic adjective placement",
        "vocabulary": ["Familie", "Mutter", "Vater", "groß", "klein", "schön", "alt", "neu"],
        "can_do": "Describe family members and simple personal details",
        "pronunciation_focus": []
    },
    "A1.6": {
        "title": "Location, Directions, Modal Verbs Intro",
        "grammar_focus": "Prepositions of place (in, auf, unter, neben), intro to können/müssen",
        "vocabulary": ["links", "rechts", "geradeaus", "können", "müssen"],
        "can_do": "Ask for and understand basic directions, say what you can/must do",
        "pronunciation_focus": []
    },
}

TIER_ORDER = list(TIERS.keys())  # extend this list as A2/B1/B2 tiers get detailed


def get_tier_content(tier_code: str) -> dict:
    return TIERS.get(tier_code, TIERS["A1.1"])


def get_next_tier(tier_code: str) -> str:
    """Returns the next tier code, or stays on the last one if at the end of defined tiers."""
    if tier_code not in TIER_ORDER:
        return TIER_ORDER[0]
    idx = TIER_ORDER.index(tier_code)
    if idx + 1 < len(TIER_ORDER):
        return TIER_ORDER[idx + 1]
    return tier_code  # stays put until you add more tiers to this file
