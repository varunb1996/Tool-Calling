"""
Shared token-counting helper. tiktoken has no native Llama encoding, but
using it as a standard proxy (cl100k_base) is exactly the practice the
lecture itself established - the point is a consistent, comparable
before/after measurement, not perfect precision for one specific model's
tokenizer.
"""

import json

import tiktoken

_encoding = tiktoken.get_encoding("cl100k_base")


def count_tokens(obj) -> int:
    """obj can be a string or anything JSON-serializable (dict/list)."""
    text = obj if isinstance(obj, str) else json.dumps(obj)
    return len(_encoding.encode(text))
