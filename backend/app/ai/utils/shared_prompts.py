# Centralized shared prompt constants to avoid duplication and minimize token usage.
import re

HINDI_FEMININE_RULE = """CRITICAL HINDI SPEECH REQUIREMENTS (VOICE call read by TTS):
1. Write ONLY in Devanagari script (हिंदी). Do NOT mix English/Roman letters in the response.
2. Since the assistant voice is FEMALE, ALWAYS use feminine grammatical structures (use "करूंगी", "सकती हूं", "बताऊंगी" instead of "करूंगा", "सकता हूं", "बताऊंगा").
3. Speak conversationally as a friendly human agent. Keep sentences extremely short (1-2 sentences).
4. Transliterate common conversational English terms into Devanagari script (e.g. write "टिकट", "बुकिंग", "रिफंड", "सीट", "बस") instead of using complex formal Sanskrit words (do NOT use complex Sanskrit words if simpler spoken terms exist).
5. Spell out numbers, times, and prices in Hindi Devanagari words (e.g. write "छह बजकर तीस मिनट", "तीन सौ रुपये")."""

TELUGU_SPEECH_RULE = """CRITICAL TELUGU SPEECH REQUIREMENTS (VOICE call read by TTS):
1. Write ONLY in Telugu script (తెలుగు). Do NOT mix English/Roman letters in the response.
2. Transliterate common conversational English terms into Telugu script (e.g., "సీట్"/"సీటు", "బుకింగ్", "రీఫండ్", "లేట్", "టికెట్", "స్టేటస్") instead of using formal terms (do NOT use "ఆసనము" for seat).
3. Use polite honorifics (the "-అండి" / "andi" suffix and "మీరు" instead of "నువ్వు").
4. Keep replies extremely short (1-2 simple sentences) and breath-friendly. Avoid compound sentences or listing multiple DB fields.
5. Answer ONLY the customer's actual question. Spell out seat numbers, times, and amounts in Telugu words (e.g. "సీటు నెంబరు పన్నెండు ఏ", "ఐదు వందల రూపాయలు")."""

VOICE_TTS_RULE = """Voice & TTS Rules (THIS RESPONSE WILL BE SPOKEN ALOUD ON A PHONE CALL):
- Always respond ONLY in {lang_name} using natural spoken phrasing. Do NOT mix scripts or languages.
- Short & Breath-Friendly: Keep responses extremely short (strictly 1-2 simple sentences). Avoid long or compound sentences. Never use comma-heavy replies or robotic grammar.
- Spoken Formatting: Write in a natural, friendly human call-center tone. Every sentence must flow smoothly when read aloud. Avoid symbols, dashes, bullet lists, or abbreviations.
- Database to Speech: Never repeat raw keys or statuses (e.g., instead of "cancellation status is CANCELLED", say "your ticket has been successfully cancelled").
- Empathetic Acknowledgement: Briefly validate the customer's intent or frustration (e.g., "I understand your concern", "Certainly, let me check that for you") before presenting facts.
- Blending & Directness: Seamlessly integrate policies and booking data into a single smooth spoken sentence. Answer immediately without robotic preambles.
- Conversational Endings: End the response naturally with exactly one simple, clear follow-up question (e.g. "Would you like me to proceed with this?", "Is there anything else I can help you with?").
- Spell out numbers, prices, dates, and times in clear words (e.g. "three hundred rupees", "six thirty in the evening", "seat number twelve A")."""


def select_relevant_history(history: list | None, current_intent: str | None, current_message: str, max_turns: int = 3) -> list:
    if not history:
        return []
    
    # Always include the last turn to preserve direct conversational context
    if len(history) <= 1:
        return history
        
    selected = [history[-1]]
    
    # Define topic keywords based on intent / current message
    current_message_lower = (current_message or "").lower()
    intent_str = str(current_intent or "").lower()
    
    keywords = set()
    if "booking" in intent_str or "status" in intent_str or "ticket" in current_message_lower or "seat" in current_message_lower or "boarding" in current_message_lower:
        keywords.update(["booking", "bk-", "ticket", "seat", "boarding", "drop", "passenger", "confirm"])
    if "delay" in intent_str or "tracking" in intent_str or "bus" in current_message_lower or "late" in current_message_lower or "eta" in current_message_lower:
        keywords.update(["bus", "delay", "late", "eta", "tracking", "location", "arrive", "route"])
    if "refund" in intent_str or "payment" in intent_str or "money" in current_message_lower or "charge" in current_message_lower or "deduct" in current_message_lower or "paisa" in current_message_lower:
        keywords.update(["refund", "payment", "money", "charge", "deduct", "paisa", "fee", "cost"])
    if "cancel" in intent_str or "reschedule" in intent_str:
        keywords.update(["cancel", "reschedule", "change", "date", "time", "fee", "confirm"])
    if "complaint" in intent_str or "rude" in current_message_lower or "clean" in current_message_lower:
        keywords.update(["complaint", "rude", "clean", "dirty", "driver", "ac", "staff"])

    # Extract words from current message as general overlap keywords
    words = [w for w in current_message_lower.split() if len(w) > 3]
    keywords.update(words)

    # Scan previous turns (excluding the last one) in reverse chronological order
    remaining_history = history[:-1]
    
    relevant_turns = []
    for turn in reversed(remaining_history):
        if len(selected) + len(relevant_turns) >= max_turns:
            break
            
        turn_msg = (turn.get("message") or "").lower()
        is_relevant = any(kw in turn_msg for kw in keywords)
        if "bk-" in turn_msg:
            is_relevant = True
            
        if is_relevant:
            relevant_turns.append(turn)
            
    # Combine and sort selected turns chronologically
    combined = relevant_turns + selected
    seen = set()
    final_selected = []
    for turn in history:
        if turn in combined and id(turn) not in seen:
            final_selected.append(turn)
            seen.add(id(turn))
            
    return final_selected


def normalize_multilingual_query(message: str) -> str:
    """Preprocesses input text, normalizing common Hinglish & Telugu-English variations."""
    if not message:
        return ""
        
    normalized = message.lower()
    
    # Mappings from foreign/phonetic terms to canonical English terms
    normalization_rules = {
        "ticket": [
            "tikt", "tikit", "tict", "टिकट", "టికెట్"
        ],
        "booking": [
            "boking", "buking", "बुकिंग", "బుకింగ్", "బుకింగు", "బుకింక్", "బూకింగ్"
        ],
        "seat": [
            "seet", "sheet", "सीट", "సీట్", "సీటు", "సీట్లు"
        ],
        "bus": [
            "gadi", "gaadi", "गाड़ी", "గాడి", "బస్సు", "బస్", "బస్సులు"
        ],
        "cancellation": [
            "cancle", "kancel", "cancele", "कैंसिल", "कैनसिल", 
            "క్యాన్సిలేషన్", "క్యాన్సలేషన్", "కెంచులేషన్", "కెన్సులేషన్", "కన్సిలేషన్"
        ],
        "cancel": [
            "रद्द", "రద్దు", "క్యాన్సిల్", "క్యాన్సల్", "రద్దుచేయడం"
        ],
        "refund": [
            "rifund", "refnd", "रिफंड", "रिपुंड", "रीफंड", "రిఫండ్", "రిపుండ్", "రీఫండు", "రిఫండు", "డబ్బులు తిరిగి", "తిరిగి చెల్లింపు"
        ],
        "money": [
            "paise", "paisa", "पैसे", "पैसा", "డబ్బులు", "డబ్బు"
        ],
        "delay": [
            "delly", "deley", "देरी", "లేట్", "ఆలస్యం", "డిలే"
        ],
        "where": [
            "kahan", "kaha", "कहां", "కహాన్", "ఎక్కడ"
        ],
        "when": [
            "kab", "कब", "కబ్", "ఎప్పుడు"
        ],
        "policy": [
            "పాలసీ", "పొలిసి", "పొలిసీ", "నిబంధనలు", "నిబంధన"
        ],
        "luggage": [
            "लगेज", "लगेजी", "लगेजु", "లగేజ్", "లగేజి", "లగేజు", "సామాను", "సామాన్లు", "సంచులు"
        ],
        "payment": [
            "भुगतान", "पेमेंट", "पैसे", "पे", "कट", "పేమెంట్", "పేమెంటు", "చెల్లింపు", "కట్టడం"
        ],
        "tracking": [
            "ట్రాకింగ్", "ట్రాకింగు", "స్టేటస్", "లొకేషన్", "జాడ"
        ],
        "reschedule": [
            "రీషెడ్యూల్", "మార్పు", "తేదీ మార్పు", "సమయం మార్పు"
        ],
        "complaint": [
            "कंप्लेंट", "కంప్లైంట్", "కంప్లైంటు", "ఫిర్యాదు", "ఫిర్యాదు"
        ]
    }
    
    # Sort all variations by length descending to match longest matches first
    all_rules = []
    for target, variations in normalization_rules.items():
        for var in variations:
            all_rules.append((var, target))
    all_rules.sort(key=lambda x: len(x[0]), reverse=True)
    
    for var, target in all_rules:
        # Match variations that are not parts of larger ASCII alphanumeric words
        pattern = rf'(?<![a-zA-Z0-9_]){re.escape(var)}(?![a-zA-Z0-9_])'
        normalized = re.sub(pattern, target, normalized)
        
    return normalized
