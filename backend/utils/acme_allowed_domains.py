"""Validation helpers for internal ACME EAB allowed-domain policy suffixes."""

import re

_DNS_LABEL_RE = re.compile(
    r"^(?=.{1,63}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE
)


def normalize_allowed_domain_suffix(value):
    """Normalize a strict DNS policy suffix, or return ``None`` if invalid."""
    if not isinstance(value, str):
        return None
    suffix = value.strip().lower()
    if (
        not suffix
        or len(suffix) > 253
        or suffix.startswith(".")
        or suffix.endswith(".")
    ):
        return None
    labels = suffix.split(".")
    if any(not _DNS_LABEL_RE.fullmatch(label) for label in labels):
        return None
    return suffix


def is_single_label_suffix(value):
    """Whether a normalized allowed-domain suffix has one DNS label."""
    return "." not in value
