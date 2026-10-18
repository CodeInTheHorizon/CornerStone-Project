"""robots.txt parsing and matching per RFC 9309.

The standard library's `urllib.robotparser` does plain prefix matching and
ignores the `*` and `$` wildcards. Marketplace robots files rely on both, so
using it would report disallowed paths as allowed. This module implements the
RFC's rules instead:

* groups are selected by product token (case-insensitive), falling back to
  the `*` group; several matching groups are merged;
* the longest matching rule wins, and `Allow` wins a tie;
* `*` matches any run of characters, a trailing `$` anchors the end.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

#: RFC 9309 section 2.5: crawlers may cap the parsed size at 500 KiB.
MAX_ROBOTS_BYTES = 500 * 1024


@dataclass(frozen=True)
class _Rule:
    allow: bool
    pattern: str
    regex: re.Pattern[str]

    @property
    def specificity(self) -> int:
        return len(self.pattern)


def _compile(pattern: str) -> re.Pattern[str]:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = ".*".join(re.escape(part) for part in body.split("*"))
    return re.compile(regex + ("$" if anchored else ""))


@dataclass
class _Group:
    agents: list[str] = field(default_factory=list)
    rules: list[_Rule] = field(default_factory=list)


@dataclass(frozen=True)
class RobotsRules:
    """Parsed robots.txt. `allow_all()` and `disallow_all()` model the RFC's error cases."""

    groups: tuple[tuple[frozenset[str], tuple[_Rule, ...]], ...] = ()
    default_allow: bool = True

    @classmethod
    def allow_all(cls) -> "RobotsRules":
        return cls()

    @classmethod
    def disallow_all(cls) -> "RobotsRules":
        return cls(default_allow=False)

    @classmethod
    def parse(cls, text: str) -> "RobotsRules":
        groups: list[_Group] = []
        current: _Group | None = None
        last_was_agent = False

        for raw_line in text[:MAX_ROBOTS_BYTES].splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()

            if key == "user-agent":
                if current is None or not last_was_agent:
                    current = _Group()
                    groups.append(current)
                current.agents.append(value.lower())
                last_was_agent = True
                continue

            last_was_agent = False
            if current is None or key not in {"allow", "disallow"}:
                continue
            if not value:
                # An empty Disallow is "no rule", not "disallow nothing explicitly".
                continue
            if not value.startswith("/") and not value.startswith("*"):
                value = "/" + value
            current.rules.append(_Rule(allow=key == "allow", pattern=value, regex=_compile(value)))

        return cls(
            groups=tuple((frozenset(g.agents), tuple(g.rules)) for g in groups),
            default_allow=True,
        )

    def _rules_for(self, agent: str) -> list[_Rule]:
        token = agent.lower()
        specific = [rules for agents, rules in self.groups if token in agents]
        if not specific:
            specific = [rules for agents, rules in self.groups if "*" in agents]
        return [rule for rules in specific for rule in rules]

    def is_allowed(self, url_or_path: str, agent: str) -> bool:
        if not self.groups:
            return self.default_allow

        parts = urlsplit(url_or_path)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        if path == "/robots.txt":
            return True

        best: _Rule | None = None
        for rule in self._rules_for(agent):
            if rule.regex.match(path) is None:
                continue
            if (
                best is None
                or rule.specificity > best.specificity
                or (rule.specificity == best.specificity and rule.allow and not best.allow)
            ):
                best = rule
        return True if best is None else best.allow
