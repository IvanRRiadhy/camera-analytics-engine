"""
Event Router Implementation.

Evaluates declarative routing rules to filter and map `StandardAnalyticsEvent` objects
to specific target publishers based on event_type, severity, or camera_id.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from camera_analytics.communication.models import StandardAnalyticsEvent

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EventRoutingRule:
    """Individual rule defining routing filters to target publishers.

    Attributes:
        event_types: List of event type strings or ['*'] for all.
        severities: List of severity strings (e.g. ['CRITICAL', 'ALERT']) or ['*'] for all.
        publishers: Target publisher names (e.g. ['rabbitmq', 'rest_webhook']).
    """

    event_types: list[str] = field(default_factory=lambda: ["*"])
    severities: list[str] = field(default_factory=lambda: ["*"])
    publishers: list[str] = field(default_factory=list)

    def matches(self, event: StandardAnalyticsEvent) -> bool:
        """Check if event satisfies routing rule criteria."""
        # Event type check
        if "*" not in self.event_types and event.event_type not in self.event_types:
            return False

        # Severity check
        if "*" not in self.severities and event.severity not in self.severities:
            return False

        return True


class EventRouter:
    """Evaluates routing rules and maps events to target publishers."""

    def __init__(self, rules: list[dict[str, Any]] | None = None) -> None:
        self._rules: list[EventRoutingRule] = []
        if rules:
            self.load_rules(rules)

    def load_rules(self, rules: list[dict[str, Any]]) -> None:
        """Load and parse routing rules from configuration list."""
        self._rules.clear()
        for r in rules:
            rule_obj = EventRoutingRule(
                event_types=list(r.get("event_types", ["*"])),
                severities=list(r.get("severities", ["*"])),
                publishers=list(r.get("publishers", [])),
            )
            self._rules.append(rule_obj)
        logger.info("EventRouter loaded %d routing rules", len(self._rules))

    def route(self, event: StandardAnalyticsEvent, all_publisher_names: list[str]) -> list[str]:
        """Determine target publisher names for a given event.

        Args:
            event: StandardAnalyticsEvent dataclass instance.
            all_publisher_names: Fallback list of active publisher names if no rules match.

        Returns:
            List of target publisher names.
        """
        if not self._rules:
            # Broadcast to all active publishers by default
            return all_publisher_names

        targets: set[str] = set()
        for rule in self._rules:
            if rule.matches(event):
                for pub in rule.publishers:
                    if pub == "*":
                        targets.update(all_publisher_names)
                    else:
                        targets.add(pub)

        return list(targets) if targets else all_publisher_names
