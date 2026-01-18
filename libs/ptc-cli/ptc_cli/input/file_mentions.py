"""File mention parsing for sandbox files."""

import re


def parse_file_mentions(text: str) -> tuple[str, list[str]]:
    """Extract @file mentions and return text with path strings.

    Paths are returned as strings for sandbox file access.
    No local filesystem validation is performed.

    Args:
        text: User input text

    Returns:
        Tuple of (original text, list of path strings)
    """
    pattern = r"@((?:[^\s@]|(?<=\\)\s)+)"  # Match @filename, allowing escaped spaces
    matches = re.findall(pattern, text)

    paths = []
    for match in matches:
        # Remove escape characters
        clean_path = match.replace("\\ ", " ")
        paths.append(clean_path)

    return text, paths
