"""Path authorization helpers."""

from __future__ import annotations

from pathlib import Path

SENSITIVE_SEGMENTS = {
    ".aws",
    ".azure",
    ".config/gh",
    ".docker",
    ".gnupg",
    ".kube",
    ".ssh",
    ".1password",
    "keychains",
    "login.keychain-db",
}

SENSITIVE_SUFFIXES = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".crt",
    ".cer",
}

SENSITIVE_NAMES = {
    ".env",
    ".envrc",
    ".env.local",
    ".env.production",
    ".pypirc",
    ".netrc",
    ".npmrc",
    "credentials.json",
    "pip.conf",
    "id_rsa",
    "id_ed25519",
    "known_hosts",
}

SENSITIVE_KEYWORDS = {
    "api_key",
    "apikey",
    "auth_token",
    "credential",
    "credentials",
    "oauth",
    "password",
    "private_key",
    "secret",
    "token",
}


def resolve_user_path(raw_path: str) -> Path:
    """Resolve a user-provided path without requiring it to exist."""

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = Path.home() / path
    return path.resolve(strict=False)


def is_relative_to(child: Path, parent: Path) -> bool:
    """Return whether child is inside parent after resolution."""

    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def is_sensitive_path(path: Path) -> bool:
    """Return whether a path looks like a secret-bearing path."""

    resolved = path.resolve(strict=False)
    lowered_parts = [part.lower() for part in resolved.parts]
    joined = "/".join(lowered_parts)
    name = resolved.name.lower()
    suffix = resolved.suffix.lower()
    if name in SENSITIVE_NAMES or name.startswith(".env.") or suffix in SENSITIVE_SUFFIXES:
        return True
    if any(segment in lowered_parts or segment in joined for segment in SENSITIVE_SEGMENTS):
        return True
    return any(keyword in name for keyword in SENSITIVE_KEYWORDS)
