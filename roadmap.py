"""
Language-agnostic CEFR tier structure.
Each tier describes WHAT to teach (theme, grammar concept, can-do goal).
Claude fills in the actual vocabulary and examples for whatever language is being taught.
This means the same roadmap works for German, French, Japanese, Spanish — any language.
"""

TIERS = {
    "A1.1": {
        "title": "First Contact",
        "theme": "Greetings, farewells, introducing yourself, basic courtesy phrases",
        "grammar_concept": "Basic sentence structure, verb 'to be' equivalent, yes/no answers",
        "can_do": "Introduce yourself, greet someone, say how you're doing",
        "pronunciation_note": "Focus on the basic sound system and any notably unusual sounds",
    },
    "A1.2": {
        "title": "Numbers & Nouns",
        "theme": "Numbers 1–100, common everyday nouns, noun classification if applicable",
        "grammar_concept": "Noun gender/class (if applicable), definite/indefinite articles or equivalents, numbers",
        "can_do": "Count, state age, identify common objects correctly",
        "pronunciation_note": "Number pronunciation, any silent letters or tricky vowel sounds",
    },
    "A1.3": {
        "title": "Daily Actions",
        "theme": "Present tense verbs, daily routine, basic time expressions (today, tomorrow, now)",
        "grammar_concept": "Present tense verb conjugation, common irregular verbs, basic word order",
        "can_do": "Describe a simple daily routine in the present tense",
        "pronunciation_note": "Verb ending sounds, any consonant clusters",
    },
    "A1.4": {
        "title": "Food & Shopping",
        "theme": "Food vocabulary, shopping phrases, prices, polite requests",
        "grammar_concept": "Direct object constructions, 'I would like' / polite request form",
        "can_do": "Order food, ask prices, express simple wants politely",
        "pronunciation_note": "Food vocabulary pronunciation, stress patterns",
    },
    "A1.5": {
        "title": "Family & Descriptions",
        "theme": "Family members, basic descriptive adjectives, possessives",
        "grammar_concept": "Possessive pronouns, adjective agreement and placement",
        "can_do": "Describe family members and give simple personal descriptions",
        "pronunciation_note": "Adjective endings, possessive forms",
    },
    "A1.6": {
        "title": "Places & Directions",
        "theme": "Locations in a city, giving and following directions, prepositions of place",
        "grammar_concept": "Prepositions of location and movement, basic modal verbs (can, must, want)",
        "can_do": "Ask for and understand basic directions, say what you can or must do",
        "pronunciation_note": "Place names, preposition sounds",
    },
    "A2.1": {
        "title": "Talking About the Past",
        "theme": "Past tense, recent events, yesterday/last week time expressions",
        "grammar_concept": "Past tense formation (simple past or perfect, whichever is natural for this language)",
        "can_do": "Describe what you did yesterday or last week",
        "pronunciation_note": "Past tense endings, auxiliary verb sounds",
    },
    "A2.2": {
        "title": "Shopping & Services",
        "theme": "Indirect objects, giving and receiving, services vocabulary",
        "grammar_concept": "Indirect object / dative equivalent, verbs of giving and showing",
        "can_do": "Navigate shopping and service situations, express giving/receiving",
        "pronunciation_note": "Service industry common phrases",
    },
    "A2.3": {
        "title": "Weather & Comparisons",
        "theme": "Weather vocabulary, seasons, comparing things",
        "grammar_concept": "Comparative and superlative adjectives, impersonal constructions",
        "can_do": "Talk about weather, make simple comparisons",
        "pronunciation_note": "Weather vocabulary sounds",
    },
    "A2.4": {
        "title": "Health & Body",
        "theme": "Body parts, health complaints, doctor visit vocabulary",
        "grammar_concept": "Reflexive verbs or constructions (where applicable), symptom descriptions",
        "can_do": "Describe health issues, handle a basic doctor's visit conversation",
        "pronunciation_note": "Medical vocabulary pronunciation",
    },
    "A2.5": {
        "title": "Making Plans",
        "theme": "Future expressions, invitations, accepting and declining",
        "grammar_concept": "Future tense or future expressions, conditional politeness forms",
        "can_do": "Make, accept, and decline plans; handle simple scheduling conversations",
        "pronunciation_note": "Future tense markers",
    },
    "A2.6": {
        "title": "Travel & Transport",
        "theme": "Travel vocabulary, transport, booking, navigating transit systems",
        "grammar_concept": "Prepositions of movement, imperative form, transport-specific phrases",
        "can_do": "Book tickets, ask for travel help, navigate transport situations",
        "pronunciation_note": "Transport vocabulary",
    },
    "B1.1": {
        "title": "Opinions & Reasons",
        "theme": "Expressing opinions, agreeing/disagreeing, giving and asking for reasons",
        "grammar_concept": "Subordinate clauses (because, that, when, if), opinion markers",
        "can_do": "Express and defend opinions, give reasons, agree or disagree politely",
        "pronunciation_note": "Intonation for opinions",
    },
    "B1.2": {
        "title": "Work & Study",
        "theme": "Professional and academic vocabulary, describing skills and experience",
        "grammar_concept": "Formal register, relative clauses, professional phrases",
        "can_do": "Discuss work and studies, describe abilities and achievements",
        "pronunciation_note": "Professional vocabulary",
    },
    "B1.3": {
        "title": "Storytelling",
        "theme": "Narrating events, sequence markers, past descriptions in detail",
        "grammar_concept": "Extended past tense usage, narrative connectors, background vs foreground",
        "can_do": "Tell a story or describe a past experience in detail",
        "pronunciation_note": "Narrative rhythm and pacing",
    },
    "B1.4": {
        "title": "Society & Media",
        "theme": "News topics, social issues, media vocabulary",
        "grammar_concept": "Passive voice, abstract nouns, reported speech",
        "can_do": "Discuss news events and social topics at a general level",
        "pronunciation_note": "News register pronunciation",
    },
    "B1.5": {
        "title": "Writing & Formality",
        "theme": "Formal letters, emails, register shifting",
        "grammar_concept": "Formal written conventions, indirect questions, polite forms",
        "can_do": "Write a formal email or letter; shift between formal and informal registers",
        "pronunciation_note": "Formal vocabulary pronunciation",
    },
    "B1.6": {
        "title": "Culture & Identity",
        "theme": "Culture, customs, identity, cultural comparison",
        "grammar_concept": "Cultural vocabulary, subjunctive or conditional where applicable",
        "can_do": "Discuss cultural topics and personal identity in the target language",
        "pronunciation_note": "Cultural vocabulary",
    },
    "B2.1": {
        "title": "Hypotheticals",
        "theme": "Hypothetical situations, wishes, regrets, speculation",
        "grammar_concept": "Conditional/subjunctive mood, hypothetical constructions",
        "can_do": "Discuss hypothetical scenarios, express wishes and regrets fluently",
        "pronunciation_note": "Modal and conditional intonation",
    },
    "B2.2": {
        "title": "Abstract Reasoning",
        "theme": "Abstract and complex topics, nuanced argument",
        "grammar_concept": "Complex sentence structures, discourse markers, abstract nouns",
        "can_do": "Discuss abstract topics and construct logical arguments",
        "pronunciation_note": "Academic register",
    },
    "B2.3": {
        "title": "Idiomatic Language",
        "theme": "Idioms, collocations, fixed expressions, informal register",
        "grammar_concept": "Idiomatic constructions, collocation patterns, informal shortcuts",
        "can_do": "Use and understand common idioms and natural collocations",
        "pronunciation_note": "Idiomatic reduction and fast speech",
    },
    "B2.4": {
        "title": "Debate & Persuasion",
        "theme": "Persuasive language, rhetorical devices, debate vocabulary",
        "grammar_concept": "Rhetorical structures, concession and counterargument patterns",
        "can_do": "Argue persuasively, acknowledge counterarguments, debate fluently",
        "pronunciation_note": "Rhetorical stress and emphasis",
    },
    "B2.5": {
        "title": "Near-Fluency",
        "theme": "Natural flow, register mastery, spontaneous conversation on any topic",
        "grammar_concept": "Full grammar consolidation, nuanced usage, error minimization",
        "can_do": "Converse naturally and spontaneously on a wide range of topics",
        "pronunciation_note": "Natural speech rhythm, reduction, and connected speech",
    },
}

TIER_ORDER = list(TIERS.keys())


def get_tier_content(tier_code: str) -> dict:
    return TIERS.get(tier_code, TIERS["A1.1"])


def get_next_tier(tier_code: str) -> str:
    if tier_code not in TIER_ORDER:
        return TIER_ORDER[0]
    idx = TIER_ORDER.index(tier_code)
    return TIER_ORDER[idx + 1] if idx + 1 < len(TIER_ORDER) else tier_code
