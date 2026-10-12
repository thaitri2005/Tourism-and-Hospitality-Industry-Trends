# VADER resource

`vader_lexicon.txt` is the VADER lexicon distributed by NLTK's `vader_lexicon` data package, copied from the installed package for deterministic offline operation. No model download, API credential, or hosted inference is required.

SHA256: `0aabac74cd95def2dbedc04ce55e39698d91113ffadb6d86b87dd337c4d2184d`

Upstream: https://github.com/cjhutto/vaderSentiment
Distribution: https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/sentiment/vader_lexicon.zip
API: https://www.nltk.org/api/nltk.sentiment.vader.html
License: VADER_LICENSE.txt (MIT, C.J. Hutto).

Cite Hutto, C.J. & Gilbert, E.E. (2014). VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text. ICWSM-14.

The audit uses disagreement with TextBlob as a sensitivity diagnostic. The models are both lexical methods; agreement does not establish domain accuracy or sentiment towards a named theme.
