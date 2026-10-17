"""Theme, brand and organisation dictionaries (codebook version 1.0).

Generic institutional activity (partnerships, MoUs, meetings) is deliberately not a
theme: it describes how organisations communicate rather than what the industry
discusses, and it would otherwise rank near the top for every association site.

A theme *mention* is any match of one of its terms. An article *discusses* a
theme when the match is more than incidental (see ``discussed`` in analyze.py).
Patterns are case-insensitive unless listed in CASE_SENSITIVE.
"""
import re

CODEBOOK_VERSION = '1.1'

THEMES = {
 'Sustainability & climate': [
    r'sustainab\w+', r'climate\s+(?:change|action|crisis|emergency|goals?|targets?|neutral\w*|resilience)', r'carbon',
    r'decarboni[sz]\w+', r'net[\s-]?zero', r'emissions?', r'biodiversity', r'nature[\s-]positive', r'circular\s+economy',
    r'green\s+(?:transition|economy|recovery|hotels?|travel|tourism|investment|buildings?)', r'renewable\s+energy',
    r'single[\s-]use\s+plastics?', r'plastic\s+(?:waste|pollution)', r'food\s+waste', r'waste\s+(?:reduction|management)',
    r'eco[\s-]?tourism', r'environmental(?:ly)?\s+(?:impacts?|footprint|friendly|protection|sustainability)',
    r'(?:wildlife|marine|nature)\s+conservation', r'SDGs?', r'sustainable\s+development\s+goals?', r'energy\s+efficien\w+'],
 'Artificial intelligence': [
    r'artificial\s+intelligence', r'[Gg]enerative\s+AI', r'[Gg]en[\s-]?AI', r'AI', r'machine\s+learning', r'ChatGPT',
    r'large\s+language\s+models?', r'LLMs?', r'chatbots?', r'agentic', r'AI[\s-](?:powered|driven|enabled|agents?)'],
 'Digital technology & data': [
    r'digital\s+transformation', r'digiti[sz]ation', r'digitali[sz]ation', r'digital\s+(?:tools?|platforms?|solutions?|innovation|identity|payments?|technolog\w+|channels?)',
    r'(?:hotel|travel|hospitality|tourism)\s+tech(?:nolog\w+)?', r'software', r'cloud[\s-](?:based|platform|computing|solutions?)',
    r'big\s+data', r'data\s+analytics', r'analytics', r'cyber\w*', r'biometrics?', r'blockchain', r'mobile\s+apps?',
    r'property\s+management\s+systems?', r'PMS', r'robot\w*', r'automation', r'contactless', r'virtual\s+reality',
    r'augmented\s+reality', r'metaverse', r'internet\s+of\s+things', r'IoT', r'smart\s+(?:tourism|destinations?|hotels?|rooms?|cities)',
    r'tech\s+start[\s-]?ups?', r'digital\s+nomads?'],
 'Social media & digital marketing': [
    r'social\s+media', r'social\s+networks?', r'influencers?', r'Instagram', r'TikTok', r'Facebook', r'YouTube', r'Twitter',
    r'WeChat', r'Weibo', r'Xiaohongshu', r'user[\s-]generated\s+content', r'content\s+creators?', r'online\s+reviews?',
    r'digital\s+marketing', r'search\s+engines?', r'SEO', r'hashtags?', r'(?:online|digital|social)\s+campaigns?',
    r'live[\s-]?stream\w*', r'(?:travel\s+)?bloggers?', r'vloggers?', r'online\s+reputation'],
 'Marketing & destination promotion': [
    r'marketing\s+(?:campaigns?|strategy|strategies|activities|efforts)', r'destination\s+marketing', r'(?:tourism|destination)\s+promotion',
    r'promotional\s+(?:campaigns?|activities|events?)', r'roadshows?', r'brand(?:ing|\s+awareness|\s+campaign|\s+identity|\s+positioning)',
    r'advertising', r'(?:travel|trade|tourism)\s+(?:fairs?|shows?|marts?)', r'ITB', r'World\s+Travel\s+Market', r'WTM',
    r'Arabian\s+Travel\s+Market', r'fam(?:iliari[sz]ation)?\s+trips?', r'source\s+markets?'],
 'Workforce, skills & education': [
    # Bare "jobs"/"employment" are left out: they mostly appear in economic-impact statements
    # ("supports 1 in 10 jobs"), which belong to Travel demand & economic performance (validation, v1.1).
    r'workforce', r'employees?', r'workers?', r'staffing', r'staff\s+(?:shortages?|retention|training|members|housing)', r'talent',
    r'recruit\w*', r'labou?r\s+(?:shortages?|market|force|costs?|unions?)', r'(?:trade|hotel|workers.?)\s+unions?', r'unioni[sz]\w+', r'wages?', r'minimum\s+wage',
    r'job\s+(?:openings|vacancies|training|fairs?|seekers|losses|creation)', r'skills?', r'training', r'education(?:al)?',
    r'apprentice\w*', r'careers?', r'human\s+capital', r'upskill\w*', r'reskill\w*', r'scholarships?',
    r'(?:hospitality|hotel|tourism)\s+(?:schools?|management\s+schools?)'],
 'Travel demand & economic performance': [
    r'arrivals?', r'(?:visitor|tourist|passenger)\s+numbers?', r'international\s+tourists?', r'occupancy', r'RevPAR',
    r'ADR', r'average\s+daily\s+rates?', r'(?:travel|tourism|hotel|leisure)\s+demand', r'booking\s+(?:momentum|growth|volumes?|trends?)',
    r'GDP', r'economic\s+(?:impact|contribution|growth|recovery|performance)', r'(?:visitor|tourism|tourist|international)\s+(?:spending|spend|receipts|expenditure)',
    r'record\s+(?:year|numbers|levels|highs?)', r'outbound', r'inbound', r'forecasts?', r'outlook', r'pre[\s-]pandemic\s+levels',
    r'year[\s-]on[\s-]year', r'travel\s+intentions?', r'travel\s+sentiment'],
 'COVID-19 pandemic': [
    r'COVID(?:-19)?', r'coronavirus', r'pandemic', r'lockdowns?', r'quarantine', r'vaccin\w+', r'social\s+distancing',
    r'reopen\w*', r'restart(?:ing)?\s+(?:of\s+)?(?:tourism|travel)', r'Safe\s+Travels', r'(?:health|safety|hygiene)\s+protocols?',
    r'post[\s-]pandemic', r'Omicron', r'testing\s+requirements?'],
 'Safety, security & crisis resilience': [
    r'crisis', r'crises', r'disasters?', r'hurricanes?', r'earthquakes?', r'floods?', r'wildfires?', r'tsunami',
    r'terroris\w+', r'security', r'resilien\w+', r'emergency', r'conflicts?', r'war', r'geopolitical', r'risk\s+management',
    r'travel\s+advisor(?:y|ies)', r'(?:natural|climate)\s+hazards?', r'recovery\s+fund', r'safety\s+and\s+security'],
 'Policy, regulation & visas': [
    r'visas?', r'visa[\s-]free', r'e[\s-]?visas?', r'travel\s+restrictions?', r'borders?', r'regulations?', r'regulatory', r'legislation',
    r'legislat(?:ive|ors?)', r'congress(?:ional)?', r'senate', r'lawmakers', r'policy[\s-]?makers', r'(?:public|tourism|government)\s+polic(?:y|ies)',
    r'taxes', r'taxation', r'tourist\s+tax', r'levy', r'levies', r'advocacy', r'lobby\w*', r'travel\s+facilitation', r'deregulation'],
 'Investment & hotel development': [
    r'investments?', r'investors?', r'infrastructure', r'(?:hotel|resort)\s+(?:developments?|openings?|pipeline|projects?)', r'construction',
    r'financing', r'capital\s+(?:expenditure|markets?|investment)', r'real\s+estate', r'acquisitions?', r'acquires?', r'acquired', r'mergers?',
    r'pipeline', r'signings?', r'management\s+agreements?', r'franchise\s+agreements?', r'development\s+projects?', r'new\s+hotels?',
    r'hotel\s+transactions?', r'joint\s+ventures?'],
 'Destination management & overtourism': [
    r'destination\s+management', r'DMOs?', r'over[\s-]?tourism', r'overcrowding', r'crowd\s+management', r'visitor\s+management',
    r'carrying\s+capacity', r'seasonality', r'(?:visitor|tourist)\s+dispersal', r'destination\s+stewardship', r'tourism\s+(?:planning|master\s+plans?|strategy|strategies)',
    r'destination\s+(?:development|strategy|governance|competitiveness|management\s+organi[sz]ations?)', r'local\s+residents', r'residents?\s+(?:and|vs\.?|versus)\s+(?:visitors|tourists)'],
 'Inclusion, community & accessibility': [
    r'inclusi\w+', r'accessib\w+', r'gender', r'women', r'equality', r'diversity\s+(?:and|&)\s+inclusion', r'DEI', r'disabilit\w+',
    r'indigenous', r'local\s+communit\w+', r'community[\s-]based', r'empowerment', r'empower(?:ing)?\s+(?:women|communities|local)', r'poverty', r'rural\s+development', r'livelihoods?',
    r'social\s+impact', r'human\s+rights', r'human\s+trafficking', r'LGBTQ?\+?'],
 'Culture, heritage & gastronomy': [
    # Bare "culture" also means company culture; only cultural-tourism uses count (v1.1).
    r'cultural\s+(?:heritage|tourism|experiences?|events?|sites?|diversity|attractions?|identity|programmes?|programs?|offer\w*|exchanges?|assets?)',
    r'(?:local|national|living|indigenous|rich|vibrant)\s+cultures?', r'culture\s+(?:and|&)\s+(?:heritage|history|arts|tourism)',
    r'heritage', r'UNESCO', r'museums?', r'gastronom\w+', r'culinary', r'food\s+tourism', r'cuisine',
    r'wine\s+tourism', r'festivals?', r'arts\s+and\s+culture', r'handicrafts?', r'historic(?:al)?\s+sites?',
    r'cultural\s+routes?', r'creative\s+(?:industries|economy)'],
 'Guest experience & wellness': [
    r'guest\s+experiences?', r'customer\s+experiences?', r'personali[sz]\w+', r'guest\s+satisfaction', r'service\s+quality',
    r'luxury', r'wellness', r'well[\s-]?being', r'spas?', r'medical\s+tourism', r'experiential', r'authentic\s+experiences?',
    r'amenities', r'guest\s+(?:needs|expectations|journey)', r'traveller\s+experience', r'traveler\s+experience'],
 'Air, cruise & connectivity': [
    r'airlines?', r'aviation', r'airports?', r'air\s+(?:connectivity|routes?|capacity|service|travel|transport|lift)', r'flights?',
    r'cruise\w*', r'rail(?:ways?)?', r'high[\s-]speed\s+rail', r'train\s+(?:travel|services?|stations?|routes?)', r'(?:air|airline|flight|route)\s+connectivity', r'ferr(?:y|ies)'],
 'Distribution, OTAs & loyalty': [
    r'online\s+travel\s+agen\w+', r'OTAs?', r'travel\s+(?:agents?|advisors?|agencies)', r'tour\s+operators?', r'distribution',
    r'direct\s+bookings?', r'booking\s+(?:engines?|platforms?|channels?)', r'GDS', r'global\s+distribution\s+systems?', r'NDC',
    r'metasearch', r'channel\s+manag\w+', r'commission\s+(?:fees?|rates?|levels|costs)', r'loyalty\s+(?:programs?|programmes?|members)', r'rewards\s+programs?',
    r'short[\s-]term\s+rentals?', r'vacation\s+rentals?', r'home[\s-]sharing', r'sharing\s+economy', r'revenue\s+management',
    r'retailing'],
 'Events, MICE & business travel': [
    r'business\s+travel(?:lers?)?', r'corporate\s+travel', r'MICE', r'business\s+events?', r'meetings\s+(?:industry|and\s+events)',
    r'conventions?\s+(?:cent(?:re|er)s?|bureaus?)', r'exhibitions?', r'incentive\s+travel', r'event\s+(?:industry|planners?|venues?)',
    r'bleisure', r'conferences?\s+and\s+events'],
 'Costs, inflation & affordability': [
    r'inflation', r'(?:rising|higher|operating|labou?r|energy|fuel|living)\s+costs?', r'cost\s+of\s+living', r'affordab\w+',
    r'interest\s+rates?', r'recession', r'economic\s+(?:uncertainty|slowdown|downturn|headwinds)', r'exchange\s+rates?',
    r'tariffs?', r'price\s+(?:increases?|rises?|hikes?)', r'higher\s+prices'],
}

# Brands: name -> (portfolio group or '', pattern). Groups follow the Global
# Brands Magazine "Top 10 Tourism Brands in the World (2026)" list supplied in
# the brief, using 2026 ownership. A mention of a sub-brand counts towards its
# own brand and its group; no historical ownership changes are modelled.
GBM_TOP10 = ['Booking Holdings', 'Hilton', 'Marriott International', 'Airbnb', 'Expedia Group',
             'Hyatt', 'IHG Hotels & Resorts', 'Disney', 'Trip.com Group', 'Accor']
GBM_RANK = {'Booking Holdings': 1, 'Hilton': 2, 'Marriott International': 3, 'Airbnb': 4, 'Expedia Group': 5,
            'Hyatt': 6, 'IHG Hotels & Resorts': 7, 'Disney': 8, 'Trip.com Group': 9, 'Accor': 10}

# STR (hotel benchmarking firm) only with context; bare STR often means short-term rental.
STR_PATTERN = r"STR(?=\s*(?:data|reports?|reported|figures|said|says|Global|and\s+Tourism\s+Economics|\)|'s|’s))"

BRANDS = {
 # Booking Holdings
 'Booking.com': ('Booking Holdings', r'Booking\.com'), 'Booking Holdings': ('Booking Holdings', r'Booking\s+Holdings'),
 'Priceline': ('Booking Holdings', r'Priceline'), 'Agoda': ('Booking Holdings', r'Agoda'), 'KAYAK': ('Booking Holdings', r'KAYAK'),
 'OpenTable': ('Booking Holdings', r'OpenTable'),
 # Hilton
 'Hilton': ('Hilton', r'Hilton(?!\s+Head)'), 'Waldorf Astoria': ('Hilton', r'Waldorf[\s-]Astoria'), 'Conrad': ('Hilton', r'Conrad\s+Hotels?'),
 'DoubleTree': ('Hilton', r'Double[Tt]ree'), 'Hampton': ('Hilton', r'Hampton\s+(?:Inn|by\s+Hilton)'), 'Embassy Suites': ('Hilton', r'Embassy\s+Suites'),
 'Curio Collection': ('Hilton', r'Curio\s+Collection'), 'Canopy by Hilton': ('Hilton', r'Canopy\s+by\s+Hilton'), 'LXR': ('Hilton', r'LXR\s+Hotels'),
 # Marriott International
 'Marriott': ('Marriott International', r'Marriott'), 'Ritz-Carlton': ('Marriott International', r'Ritz[\s-]Carlton'),
 'St. Regis': ('Marriott International', r'St\.?\s+Regis'), 'W Hotels': ('Marriott International', r'W\s+Hotels?'),
 'Sheraton': ('Marriott International', r'Sheraton'), 'Westin': ('Marriott International', r'Westin'),
 'Renaissance Hotels': ('Marriott International', r'Renaissance\s+Hotels?'), 'Le Méridien': ('Marriott International', r'Le\s+M[ée]ridien'),
 'Four Points': ('Marriott International', r'Four\s+Points'), 'Aloft': ('Marriott International', r'Aloft'), 'Moxy': ('Marriott International', r'Moxy'),
 'Autograph Collection': ('Marriott International', r'Autograph\s+Collection'), 'Starwood': ('Marriott International', r'Starwood'),
 # Airbnb
 'Airbnb': ('Airbnb', r'Airbnb'),
 # Expedia Group
 'Expedia': ('Expedia Group', r'Expedia'), 'Hotels.com': ('Expedia Group', r'Hotels\.com'), 'Vrbo': ('Expedia Group', r'Vrbo|VRBO|HomeAway'),
 'Egencia': ('Expedia Group', r'Egencia'), 'Orbitz': ('Expedia Group', r'Orbitz'), 'trivago': ('Expedia Group', r'[Tt]rivago'),
 # Hyatt
 'Hyatt': ('Hyatt', r'Hyatt'), 'Andaz': ('Hyatt', r'Andaz'), 'Alila': ('Hyatt', r'Alila'), 'Thompson Hotels': ('Hyatt', r'Thompson\s+Hotels?'),
 # IHG Hotels & Resorts
 'IHG': ('IHG Hotels & Resorts', r'IHG|InterContinental\s+Hotels\s+Group'),
 'InterContinental': ('IHG Hotels & Resorts', r'InterContinental(?!\s+Hotels\s+Group)'), 'Holiday Inn': ('IHG Hotels & Resorts', r'Holiday\s+Inn'),
 'Crowne Plaza': ('IHG Hotels & Resorts', r'Crowne\s+Plaza'), 'Kimpton': ('IHG Hotels & Resorts', r'Kimpton'),
 'Hotel Indigo': ('IHG Hotels & Resorts', r'Hotel\s+Indigo'), 'Six Senses': ('IHG Hotels & Resorts', r'Six\s+Senses'),
 'Regent Hotels': ('IHG Hotels & Resorts', r'Regent\s+Hotels?'), 'voco': ('IHG Hotels & Resorts', r'voco'),
 'Staybridge Suites': ('IHG Hotels & Resorts', r'Staybridge'),
 # Disney
 'Disney': ('Disney', r'Disney(?:land)?|Walt\s+Disney'),
 # Trip.com Group
 'Trip.com': ('Trip.com Group', r'Trip\.com|Ctrip'), 'Skyscanner': ('Trip.com Group', r'Skyscanner'), 'Qunar': ('Trip.com Group', r'Qunar'),
 # Accor
 'Accor': ('Accor', r'Accor(?:Hotels)?|ALL\s+Accor'), 'Raffles': ('Accor', r'Raffles\s+(?:Hotels?|[A-Z][a-z]+)'), 'Fairmont': ('Accor', r'Fairmont'),
 'Sofitel': ('Accor', r'Sofitel'), 'Pullman': ('Accor', r'Pullman'), 'MGallery': ('Accor', r'MGallery'), 'Novotel': ('Accor', r'Novotel'),
 'Mercure': ('Accor', r'Mercure'), 'ibis': ('Accor', r'ibis'), 'Swissôtel': ('Accor', r'Swiss[oô]tel'), 'Mövenpick': ('Accor', r'M[öo]venpick'),
 'Banyan Tree': ('', r'Banyan\s+Tree'),
 # Other hotel companies
 'Wyndham': ('', r'Wyndham'), 'Choice Hotels': ('', r'Choice\s+Hotels'), 'Best Western': ('', r'Best\s+Western'), 'Radisson': ('', r'Radisson'),
 'Four Seasons': ('', r'Four\s+Seasons'), 'Shangri-La': ('', r'Shangri[\s-]La'), 'Minor Hotels': ('', r'Minor\s+(?:Hotels|International)'),
 'Anantara': ('', r'Anantara'), 'Meliá': ('', r'Meli[aá]\s+(?:Hotels|Hotels\s+International)|Meli[aá]'), 'Riu': ('', r'RIU|Riu\s+Hotels'),
 'Iberostar': ('', r'Iberostar'), 'Barceló': ('', r'Barcel[oó]'), 'Jin Jiang': ('', r'Jin\s*Jiang'), 'Mandarin Oriental': ('', r'Mandarin\s+Oriental'),
 'Kempinski': ('', r'Kempinski'), 'Rosewood': ('', r'Rosewood'), 'Belmond': ('', r'Belmond'), 'Soneva': ('', r'Soneva'), 'Dusit': ('', r'Dusit'),
 'Centara': ('', r'Centara'), 'Langham': ('', r'Langham'), 'Ascott': ('', r'Ascott'), 'OYO': ('', r'OYO'), 'Sonder': ('', r'Sonder'),
 'Selina': ('', r'Selina'), 'citizenM': ('', r'citizenM'), 'Club Med': ('', r'Club\s+Med'), 'Sandals': ('', r'Sandals'), 'Vinpearl': ('', r'Vinpearl'),
 # Travel distribution, data and technology
 'Tripadvisor': ('', r'Trip\s?[Aa]dvisor'), 'Google': ('', r'Google'), 'Amadeus': ('', r'Amadeus'), 'Sabre': ('', r'Sabre'),
 'Travelport': ('', r'Travelport'), 'Hotelbeds': ('', r'Hotelbeds'), 'SiteMinder': ('', r'SiteMinder'), 'Oracle Hospitality': ('', r'Oracle\s+Hospitality'),
 'Cloudbeds': ('', r'Cloudbeds'), 'Mews': ('', r'Mews'), 'Duetto': ('', r'Duetto'), 'IDeaS': ('', r'IDeaS'), 'STR': ('', STR_PATTERN),
 'CoStar': ('', r'CoStar'), 'ForwardKeys': ('', r'ForwardKeys'),
 # Tour operators and cruise
 'TUI': ('', r'TUI'), 'Thomas Cook': ('', r'Thomas\s+Cook'), 'Intrepid Travel': ('', r'Intrepid\s+Travel|Intrepid\s+Group'),
 'G Adventures': ('', r'G\s+Adventures'), 'Abercrombie & Kent': ('', r'Abercrombie\s*(?:&|and)\s*Kent'),
 'Carnival': ('', r'Carnival'), 'Royal Caribbean': ('', r'Royal\s+Caribbean'), 'MSC Cruises': ('', r'MSC\s+Cruises'),
 'Norwegian Cruise Line': ('', r'Norwegian\s+Cruise\s+Line'), 'Princess Cruises': ('', r'Princess\s+Cruises'), 'Viking': ('', r'Viking\s+(?:Cruises|River|Ocean)'),
 # Airlines and aircraft makers
 'Emirates': ('', r'Emirates'), 'Qatar Airways': ('', r'Qatar\s+Airways'), 'Singapore Airlines': ('', r'Singapore\s+Airlines'),
 'Delta Air Lines': ('', r'Delta\s+Air\s*Lines|Delta(?=\s+(?:flights?|passengers|CEO|said))'), 'American Airlines': ('', r'American\s+Airlines'),
 'United Airlines': ('', r'United\s+Airlines'), 'Southwest Airlines': ('', r'Southwest\s+Airlines'), 'JetBlue': ('', r'JetBlue'),
 'Lufthansa': ('', r'Lufthansa'), 'Air France-KLM': ('', r'Air\s+France|KLM'), 'British Airways': ('', r'British\s+Airways'),
 'Ryanair': ('', r'Ryanair'), 'easyJet': ('', r'easyJet'), 'Turkish Airlines': ('', r'Turkish\s+Airlines'), 'Etihad': ('', r'Etihad'),
 'Cathay Pacific': ('', r'Cathay\s+Pacific'), 'Qantas': ('', r'Qantas'), 'Air Canada': ('', r'Air\s+Canada'), 'AirAsia': ('', r'AirAsia'),
 'Thai Airways': ('', r'Thai\s+Airways'), 'Vietnam Airlines': ('', r'Vietnam\s+Airlines'), 'Vietjet': ('', r'Viet[Jj]et'),
 'Boeing': ('', r'Boeing'), 'Airbus': ('', r'Airbus'),
 # Car rental and mobility
 'Hertz': ('', r'Hertz'), 'Avis': ('', r'Avis(?:\s+Budget)?'), 'Uber': ('', r'Uber'),
}

ORGANIZATIONS = {
 'UN Tourism / UNWTO': r'UN\s+Tourism|UNWTO|World\s+Tourism\s+Organi[sz]ation',
 'WTTC': r'WTTC|World\s+Travel\s*(?:&|and)\s*Tourism\s+Council',
 'PATA': r'PATA|Pacific\s+Asia\s+Travel\s+Association',
 'AHLA': r'AHLA|AH&LA|American\s+Hotel\s*(?:&|and)\s*Lodging\s+Association',
 'European Travel Commission': r'European\s+Travel\s+Commission',
 'Caribbean Tourism Organization': r'Caribbean\s+Tourism\s+Organi[sz]ation',
 'IH&RA': r'IH\s*&\s*RA|International\s+Hotel\s*(?:&|and)\s*Restaurant\s+Association',
 'IATA': r'IATA|International\s+Air\s+Transport\s+Association',
 'ICAO': r'ICAO|International\s+Civil\s+Aviation\s+Organi[sz]ation',
 'CLIA': r'CLIA|Cruise\s+Lines\s+International\s+Association',
 'U.S. Travel Association': r'U\.?S\.?\s+Travel\s+Association',
 'ASTA': r'ASTA|American\s+Society\s+of\s+Travel\s+Advisors',
 'HOTREC': r'HOTREC', 'GSTC': r'GSTC|Global\s+Sustainable\s+Tourism\s+Council',
 'HFTP': r'HFTP|Hospitality\s+Financial\s+and\s+Technology\s+Professionals',
 'CHTA': r'CHTA|Caribbean\s+Hotel\s*(?:&|and)\s*Tourism\s+Association',
 'UNESCO': r'UNESCO', 'World Health Organization': r'World\s+Health\s+Organi[sz]ation',
 'European Commission / EU': r'European\s+Commission|European\s+Union',
 'ASEAN': r'ASEAN', 'OECD': r'OECD', 'World Bank': r'World\s+Bank', 'Brand USA': r'Brand\s+USA',
}

# Which organisation is the publisher itself (self-mentions are not "associations").
SOURCE_ORGANIZATION = {'untourism': 'UN Tourism / UNWTO', 'wttc': 'WTTC', 'pata': 'PATA', 'ahla': 'AHLA',
                       'etc': 'European Travel Commission', 'cto': 'Caribbean Tourism Organization', 'ihra': 'IH&RA'}

CASE_SENSITIVE = {r'AI', r'[Gg]en[\s-]?AI', r'[Gg]enerative\s+AI', r'LLMs?', r'OTAs?', r'GDS', r'NDC', r'PMS', r'IoT', r'SDGs?', r'ADR',
                  r'RevPAR', r'GDP', r'MICE', r'ITB', r'WTM', r'SEO', r'DMOs?', r'MoUs?', r'RIU|Riu\s+Hotels', r'KAYAK', r'TUI', r'OYO',
                  STR_PATTERN, r'IDeaS', r'Mews', r'Aloft', r'Moxy', r'voco', r'Four\s+Seasons', r'Sonder', r'Selina', r'Sandals', r'Pullman',
                  r'Mercure', r'Carnival', r'Emirates', r'Sabre', r'Amadeus', r'Google', r'Uber', r'Hertz', r'Avis(?:\s+Budget)?',
                  r'Dusit', r'Centara', r'Langham', r'Ascott', r'Rosewood', r'Belmond', r'W\s+Hotels?', r'PATA', r'AHLA|AH&LA|American\s+Hotel\s*(?:&|and)\s*Lodging\s+Association',
                  r'IATA|International\s+Air\s+Transport\s+Association', r'CLIA|Cruise\s+Lines\s+International\s+Association',
                  r'ASTA|American\s+Society\s+of\s+Travel\s+Advisors', r'ASEAN', r'OECD', r'UNESCO', r'HOTREC',
                  r'Disney(?:land)?|Walt\s+Disney', r'war', r'Raffles\s+(?:Hotels?|[A-Z][a-z]+)',
                  r'Viking\s+(?:Cruises|River|Ocean)', r'Delta\s+Air\s*Lines|Delta(?=\s+(?:flights?|passengers|CEO|said))'}


def _part(pattern):
    """Scoped flags keep case-sensitive terms (AI, TUI) exact inside a combined pattern."""
    return pattern if pattern in CASE_SENSITIVE else '(?i:' + pattern + ')'


def _combined(named):
    """One pass per dictionary: an alternation of every term, longest pattern first.

    At each position the first matching alternative wins, so overlapping terms
    are counted once ("generative AI" is one hit, not two).
    """
    order = sorted(named, key=lambda item: -len(item[1]))
    body = '|'.join(f'(?P<g{i}>{_part(p)})' for i, (_, p) in enumerate(order))
    return re.compile(r'(?<![\w.])(?:' + body + r')(?!\w)'), [name for name, _ in order]


THEME_REGEX = {theme: _combined([(p, p) for p in patterns])[0] for theme, patterns in THEMES.items()}
BRAND_REGEX, BRAND_ORDER = _combined([(name, pattern) for name, (_, pattern) in BRANDS.items()])
ORG_REGEX, ORG_ORDER = _combined(list(ORGANIZATIONS.items()))


def theme_hits(text):
    """{theme: [match, ...]} for every theme with at least one term in text."""
    found = {}
    for theme, regex in THEME_REGEX.items():
        hits = list(regex.finditer(text))
        if hits:
            found[theme] = hits
    return found


def _named_hits(regex, names, text):
    found = {}
    for m in regex.finditer(text):
        found.setdefault(names[int(m.lastgroup[1:])], []).append(m)
    return found


def brand_hits(text):
    """{brand: [match, ...]} with homonym filters for a few ambiguous names."""
    found = _named_hits(BRAND_REGEX, BRAND_ORDER, text)
    if 'Emirates' in found:
        found['Emirates'] = [m for m in found['Emirates'] if not re.search(r'United\s+Arab\s*$', text[max(0, m.start()-20):m.start()], re.I)]
    if 'Carnival' in found and not re.search(r'Carnival\s+(?:Corporation|Corp\.?|Cruise|plc|Asia)', text):
        found['Carnival'] = [m for m in found['Carnival'] if re.search(r'cruise', text[max(0, m.start()-120):m.end()+120], re.I)]
    if 'Hilton' in found:
        found['Hilton'] = [m for m in found['Hilton'] if not re.search(r'Paris\s+$', text[max(0, m.start()-7):m.start()])]
    return {name: hits for name, hits in found.items() if hits}


def org_hits(text):
    return _named_hits(ORG_REGEX, ORG_ORDER, text)


BRAND_GROUP = {name: group for name, (group, _) in BRANDS.items()}
