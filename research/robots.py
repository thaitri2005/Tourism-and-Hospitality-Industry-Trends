"""RobotFileParser with publisher wildcard and end-anchor rule support."""
import re
from urllib.parse import urlsplit, unquote, quote
from urllib.robotparser import RobotFileParser


class PublisherRobots(RobotFileParser):
    def can_fetch(self, useragent, url):
        if self.disallow_all:
            return False
        if self.allow_all:
            return True
        if not self.last_checked:
            return False
        entry = next((e for e in self.entries if e.applies_to(useragent)), self.default_entry)
        if entry is None:
            return True
        parts = urlsplit(url)
        target = quote(unquote(parts.path or '/') + ('?' + parts.query if parts.query else ''),
                       safe='/%?=&:;,+!~*\'()@-$')
        matches = []
        for rule in entry.rulelines:
            path = unquote(rule.path)
            end = path.endswith('$')
            pattern = path[:-1] if end else path
            # Normalize percent encoding consistently for paths and query strings.
            pattern = quote(pattern, safe='/%?=&:;,+!~*\'()@-$')
            regex = '^' + '.*'.join(re.escape(p) for p in pattern.split('*')) + ('$' if end else '')
            if re.search(regex, target):
                matches.append((len(pattern.replace('*', '').encode('utf8')), rule.allowance))
        return max(matches)[1] if matches else True
