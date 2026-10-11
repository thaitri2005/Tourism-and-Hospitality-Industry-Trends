"""Exploratory, versioned rules. These are candidate concepts, not validated findings."""
import re

THEMES={
 'Sustainability, climate and nature': [r'sustainab\w+',r'climate\s+(?:change|action|crisis)',r'carbon',r'net.zero',r'biodiversity',r'nature.positive',r'circular\s+economy',r'green\s+transition',r'emissions?'],
 'AI and digital technology': [r'artificial\s+intelligence',r'generative\s+AI',r'\bAI\b',r'machine\s+learning',r'digital\s+transformation',r'digitali[sz]ation',r'blockchain',r'big\s+data',r'robotics?',r'chatbots?',r'automation'],
 'Marketing, social media and branding': [r'marketing',r'social\s+media',r'influencers?',r'brand(?:ing|\s+awareness)',r'advertising',r'promotional\s+campaign',r'digital\s+campaign'],
 'Workforce, skills and education': [r'workforce',r'skills?',r'education',r'training',r'labou?r\s+shortage',r'employment',r'jobs?',r'talent',r'apprentice\w+'],
 'Demand, performance and recovery': [r'arrivals?',r'visitor\s+numbers?',r'GDP',r'economic\s+(?:impact|contribution|growth)',r'travel\s+demand',r'occupancy',r'\brevpar\b',r'visitor\s+spend\w*',r'touris[mt]\s+recovery'],
 'Health, safety and crisis resilience': [r'COVID',r'coronavirus',r'pandemic',r'health\s+(?:and\s+safety|crisis|protocol)',r'safe\s+travels?',r'crisis',r'disaster',r'resilien\w+',r'hurricane',r'terroris\w*',r'geopolitical'],
 'Policy, visas and travel facilitation': [r'visa',r'travel\s+restrictions?',r'borders?',r'regulation',r'legislation',r'public\s+polic\w+',r'tourism\s+polic\w+',r'travel\s+facilitation',r'government\s+polic\w+'],
 'Investment, infrastructure and development': [r'investment',r'infrastructure',r'hotel\s+development',r'financ(?:e|ing)',r'capital\s+expenditure',r'public.private\s+partnership',r'hotel\s+openings?'],
 'Destination management and overtourism': [r'destination\s+management',r'overtourism',r'overcrowding',r'visitor\s+management',r'carrying\s+capacity',r'seasonality',r'dispersal',r'destination\s+stewardship'],
 'Inclusion, accessibility and communities': [r'inclusiv\w+',r'accessib\w+',r'gender',r'women',r'local\s+communit\w+',r'indigenous',r'empower\w+',r'disabilit\w+',r'equality'],
 'Culture, heritage and experiences': [r'cultur\w+',r'heritage',r'gastronom\w+',r'culinary',r'experiential',r'authentic\w+',r'rural\s+tourism',r'adventure\s+tourism',r'wellness\s+tourism'],
 'Transport and connectivity': [r'airlines?',r'aviation',r'airports?',r'connectivity',r'air\s+transport',r'rail(?:way)?',r'cruise',r'flight\w*',r'transportation'],
 'Distribution, booking and business models': [r'online\s+travel\s+agen\w+',r'\bOTAs?\b',r'booking\s+platform',r'direct\s+booking',r'sharing\s+economy',r'short.term\s+rentals?',r'franchis\w+',r'distribution\s+channel',r'loyalty\s+program\w*'],
 'Partnerships, governance and institutions': [r'partnership',r'memorandum\s+of\s+understanding',r'governance',r'general\s+assembly',r'executive\s+council',r'board\s+of\s+directors',r'chair(?:man|person|woman)',r'secretary.general'],
}

# No present-day corporate ownership mapping is applied retrospectively.
# Name families remain unresolved where a bare mention cannot distinguish a
# parent company, consumer brand, or individual property.
BRANDS={
 'Marriott':r'Marriott', 'Hilton':r'Hilton', 'Hyatt':r'Hyatt',
 'IHG':r'IHG|InterContinental\s+Hotels\s+Group', 'Accor':r'Accor(?:Hotels)?',
 'Wyndham':r'Wyndham', 'Choice Hotels':r'Choice\s+Hotels', 'Best Western':r'Best\s+Western',
 'Radisson':r'Radisson', 'Four Seasons':r'Four\s+Seasons', 'Shangri-La':r'Shangri.La',
 'Minor Hotels':r'Minor\s+Hotels', 'Meliá':r'Meli[aá]', 'Riu':r'RIU',
 'Iberostar':r'Iberostar', 'Barceló':r'Barcel[oó]', 'Jin Jiang':r'Jin\s*Jiang',
 'Mandarin Oriental':r'Mandarin\s+Oriental', 'Kempinski':r'Kempinski',
 'Rosewood':r'Rosewood', 'Belmond':r'Belmond', 'Banyan Tree':r'Banyan\s+Tree',
 'Soneva':r'Soneva', 'Six Senses':r'Six\s+Senses', 'Anantara':r'Anantara',
 'Ritz-Carlton':r'Ritz.Carlton', 'Sheraton':r'Sheraton', 'Westin':r'Westin',
 'InterContinental':r'InterContinental(?!\s+Hotels\s+Group)',
 'Holiday Inn':r'Holiday\s+Inn', 'Fairmont':r'Fairmont', 'Sofitel':r'Sofitel',
 'Airbnb':r'Airbnb', 'Booking.com':r'Booking\.com', 'Booking Holdings':r'Booking\s+Holdings',
 'Expedia':r'Expedia', 'Trip.com':r'Trip\.com|Ctrip', 'Tripadvisor':r'Trip\s?advisor',
 'Agoda':r'Agoda', 'Skyscanner':r'Skyscanner', 'Kayak':r'KAYAK',
 'TUI':r'TUI', 'Thomas Cook':r'Thomas\s+Cook', 'Intrepid':r'Intrepid',
 'G Adventures':r'G\s+Adventures', 'Abercrombie & Kent':r'Abercrombie\s*(?:&|and)\s*Kent',
 'Amadeus':r'Amadeus', 'Sabre':r'Sabre', 'Travelport':r'Travelport',
 'Carnival':r'Carnival', 'Royal Caribbean':r'Royal\s+Caribbean',
 'MSC Cruises':r'MSC\s+Cruises', 'Norwegian Cruise Line':r'Norwegian\s+Cruise\s+Line',
 'Disney':r'Disney', 'Sandals':r'Sandals',
 'Emirates':r'Emirates', 'Qatar Airways':r'Qatar\s+Airways',
 'Singapore Airlines':r'Singapore\s+Airlines', 'Delta Air Lines':r'Delta\s+Air\s*Lines',
 'American Airlines':r'American\s+Airlines', 'United Airlines':r'United\s+Airlines',
 'Lufthansa':r'Lufthansa', 'Air France':r'Air\s+France', 'British Airways':r'British\s+Airways',
 'Vietnam Airlines':r'Vietnam\s+Airlines', 'Vietjet':r'Vietjet', 'Vinpearl':r'Vinpearl',
}
ORGANIZATIONS={
 'UN Tourism / UNWTO':r'UN\s+Tourism|UNWTO|World\s+Tourism\s+Organi[sz]ation',
 'WTTC':r'WTTC|World\s+Travel\s*(?:&|and)\s*Tourism\s+Council',
 'PATA':r'PATA|Pacific\s+Asia\s+Travel\s+Association',
 'AHLA':r'AHLA|American\s+Hotel\s*(?:&|and)\s*Lodging\s+Association',
 'European Travel Commission':r'European\s+Travel\s+Commission',
 'Caribbean Tourism Organization':r'Caribbean\s+Tourism\s+Organi[sz]ation',
 'IH&RA':r'IH\s*&\s*RA|International\s+Hotel\s*(?:&|and)\s*Restaurant\s+Association',
 'IATA':r'IATA|International\s+Air\s+Transport\s+Association',
 'ICAO':r'ICAO|International\s+Civil\s+Aviation\s+Organi[sz]ation',
 'HOTREC':r'HOTREC', 'GSTC':r'GSTC|Global\s+Sustainable\s+Tourism\s+Council',
 'HFTP':r'HFTP|Hospitality\s+Financial\s+and\s+Technology\s+Professionals',
}

def compile_rule(pattern):
    # Uppercase abbreviations use case-sensitive matching to prevent false
    # matches such as Spanish "AI" fragments or ordinary "kayak" activities.
    sensitive=pattern in [r'\bAI\b',r'\bOTAs?\b',r'RIU',r'KAYAK',r'TUI',r'Intrepid',r'Four\s+Seasons']
    return re.compile(r'(?<!\w)(?:'+pattern+r')(?!\w)',0 if sensitive else re.I)

COMPILED_THEMES={k:[compile_rule(p) for p in ps] for k,ps in THEMES.items()}

def tag_themes(text):
    result={}
    for theme,patterns in COMPILED_THEMES.items():
        hits=[m for p in patterns for m in p.finditer(text)]
        if hits:result[theme]=hits
    return result

def entity_patterns():
    return [(n,'brand_name_family',compile_rule(p)) for n,p in BRANDS.items()]+[(n,'organization',compile_rule(p)) for n,p in ORGANIZATIONS.items()]


ENTITY_DISAMBIGUATION = {
    'Intrepid / Four Seasons': 'Case-sensitive proper names; lower-case ordinary words excluded. May miss nonstandard capitalization.',
    'Carnival': 'Requires a qualified Carnival Corporation/Corp/Cruise/Asia name in the article, or a nearby cruise-company/operator description. This is a conservative heuristic, not semantic validation.',
    'Emirates': 'Exclude United Arab Emirates and Emirates Council for Balanced Development; other matches remain candidate airline-name mentions.',
}


def entity_matches(name, pattern, text):
    """Filter observed homonyms without claiming general entity disambiguation."""
    matches=list(pattern.finditer(text))
    if name=='Emirates':
        matches=[m for m in matches
                 if not re.search(r'United\s+Arab\s*$',text[max(0,m.start()-20):m.start()],re.I)
                 and not re.match(r'\s+Council\s+for\s+Balanced\s+Development\b',text[m.end():],re.I)]
    if name=='Carnival':
        qualified=re.search(r'\bCarnival\s+(?:Corporation|Corp\.?|Cruise(?:s|\s+Lines?)?|Asia)\b',text,re.I)
        if not qualified:
            matches=[m for m in matches if re.search(
                r'\bcruise\s+(?:compan(?:y|ies)|operators?)\b',
                text[max(0,m.start()-100):m.end()+100],re.I)]
    return matches
