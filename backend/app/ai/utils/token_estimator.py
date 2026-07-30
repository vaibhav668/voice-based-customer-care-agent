def estimate_tokens(text: str) -> int:
    """
    Lightweight, dependency-free token estimator for both English and Indic languages.
    English words: ~1.3 tokens per word, or roughly 4 characters per token.
    Indic words (Hindi, Telugu, etc.): Standard BPE tokenizers split Indic characters
    into multiple tokens. We use Unicode ranges to detect Indic characters and estimate
    ~0.8 tokens per Indic character, and ~0.25 tokens per English/ASCII character.
    """
    if not text:
        return 0
    
    indic_chars = 0
    other_chars = 0
    
    for char in text:
        cp = ord(char)
        # Check Devanagari, Bengali, Gurmukhi, Gujarati, Tamil, Telugu, Kannada, Malayalam ranges (0x0900 to 0x0DFF)
        if 0x0900 <= cp <= 0x0DFF or 0x0A00 <= cp <= 0x0A7F:
            indic_chars += 1
        else:
            other_chars += 1
            
    # Combine estimates: Indic characters tend to translate to approx 0.8 tokens each.
    # English/other characters translate to approx 0.25 tokens each.
    tokens = int(indic_chars * 0.8 + other_chars * 0.25)
    return max(1, tokens)
