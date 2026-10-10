"""
Public Git URL validation and SSRF mitigation for DevMind AI.
Implements Step 10 of execution guide and PRD Section 6 (FR-02), Section 10, Section 17.4.
Enforces HTTPS-only, rejects credentials, blocks localhost and private IP addresses.
"""
from dataclasses import dataclass
import ipaddress
import re
import socket
from urllib.parse import urlparse


class GitValidationError(Exception):
    """Base exception for Git URL validation failures."""
    pass


class InvalidGitProtocolError(GitValidationError):
    """Raised when protocol is not public HTTPS."""
    pass


class SSRFBlockedError(GitValidationError):
    """Raised when URL points to loopback, private network, or metadata services."""
    pass


class EmbeddedCredentialsError(GitValidationError):
    """Raised when URL contains embedded user/password/token credentials."""
    pass


class MalformedGitUrlError(GitValidationError):
    """Raised when URL format is malformed or missing repository path."""
    pass


@dataclass(frozen=True)
class GitValidationResult:
    is_valid: bool
    normalized_url: str
    repo_name: str
    host: str


def is_ip_private_or_restricted(ip_str: str) -> bool:
    """Checks whether an IP address is private, loopback, link-local, or cloud metadata."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
            or str(ip) == "169.254.169.254"  # AWS / Cloud Instance Metadata
        )
    except ValueError:
        return True


def validate_git_url(raw_url: str, resolve_dns: bool = True) -> GitValidationResult:
    """
    Validates that raw_url is a safe public HTTPS Git repository.
    Strictly forbids:
      - non-HTTPS protocols (file://, ssh://, git://, http://)
      - embedded credentials (user:pass@)
      - loopback, private RFC1918 IPs, link-local, or cloud metadata targets
    """
    if not raw_url or not isinstance(raw_url, str):
        raise MalformedGitUrlError("Git URL cannot be empty.")

    clean_url = raw_url.strip()
    if not clean_url:
        raise MalformedGitUrlError("Git URL cannot be empty or whitespace.")

    # Reject local filesystem path strings
    if clean_url.startswith("/") or clean_url.startswith("\\") or ":" in clean_url[:2]:
        raise InvalidGitProtocolError("Local filesystem paths are not allowed as Git URLs.")

    try:
        parsed = urlparse(clean_url)
    except Exception as e:
        raise MalformedGitUrlError(f"Malformed URL: {str(e)}") from e

    # 1. Enforce HTTPS protocol
    if parsed.scheme.lower() != "https":
        raise InvalidGitProtocolError(
            f"Unsupported protocol '{parsed.scheme}'. Only public HTTPS repositories (https://) are supported."
        )

    # 2. Reject embedded credentials
    if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
        raise EmbeddedCredentialsError(
            "Embedded credentials (usernames, tokens, or passwords) are strictly prohibited in repository URLs."
        )

    host = (parsed.hostname or "").lower()
    if not host:
        raise MalformedGitUrlError("Invalid repository URL: host is missing.")

    # 3. Fast check for blocked hostnames
    blocked_hostnames = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "metadata.google.internal",
        "instance-data",
    }
    if host in blocked_hostnames or host.endswith(".local") or host.endswith(".internal"):
        raise SSRFBlockedError(f"Access to local or internal network target '{host}' is blocked.")

    # 4. Check if host is direct IP address
    try:
        ip = ipaddress.ip_address(host)
        if is_ip_private_or_restricted(str(ip)):
            raise SSRFBlockedError(f"Access to private or restricted IP address '{host}' is blocked.")
    except ValueError:
        # Not a direct IP literal, validate DNS resolution if enabled
        if resolve_dns:
            try:
                addr_info = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
                for entry in addr_info:
                    resolved_ip = entry[4][0]
                    if is_ip_private_or_restricted(resolved_ip):
                        raise SSRFBlockedError(
                            f"Host '{host}' resolves to restricted IP '{resolved_ip}'. Access blocked."
                        )
            except socket.gaierror as e:
                # If DNS cannot resolve, it cannot be cloned
                raise MalformedGitUrlError(f"Cannot resolve host '{host}': {str(e)}") from e

    # 5. Path and repository name validation
    path = parsed.path.strip("/")
    if not path or "/" not in path:
        raise MalformedGitUrlError(
            "Repository path must include owner and repository name (e.g., https://github.com/owner/repo)."
        )

    parts = path.split("/")
    repo_name = parts[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    if not repo_name or not re.match(r"^[a-zA-Z0-9_\-\.]+$", repo_name):
        raise MalformedGitUrlError(f"Invalid repository name in URL: '{repo_name}'.")

    # Normalized URL: ensure standard https://host/path.git
    normalized_path = "/".join(parts)
    if not normalized_path.endswith(".git"):
        normalized_path = f"{normalized_path}.git"

    normalized_url = f"https://{parsed.netloc}/{normalized_path}"

    return GitValidationResult(
        is_valid=True,
        normalized_url=normalized_url,
        repo_name=repo_name,
        host=host,
    )
