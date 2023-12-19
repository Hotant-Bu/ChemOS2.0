# Generated by sila2.code_generator; sila2.__version__: 0.10.1
from __future__ import annotations

from typing import NamedTuple


class Recommend_Responses(NamedTuple):
    Termination: str
    """
    Termination message
    """


class Recommend_IntermediateResponses(NamedTuple):
    Status: str
    """
    Status of Campaign 
    """

    BinaryPayload: bytes
    """
    BinaryPayload
    """

    StringPayload: str
    """
    StringPayload
    """
