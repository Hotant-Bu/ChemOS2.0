# Generated by sila2.code_generator; sila2.__version__: 0.10.1
from __future__ import annotations

from typing import NamedTuple


class Status_Responses(NamedTuple):
    Termination: str
    """
    Termination message
    """


class ValveStatus_Responses(NamedTuple):
    Termination: str
    """
    Termination message
    """


class BlankRun_Responses(NamedTuple):
    Termination: str
    """
    Termination message
    """


class SubmitJobChemspeed_Responses(NamedTuple):
    Termination: str
    """
    Termination message
    """


class BlankRun_IntermediateResponses(NamedTuple):
    Data: str
    """
    Type of data being returned 
    """

    Payload: bytes
    """
    Type of data being returned 
    """


class SubmitJobChemspeed_IntermediateResponses(NamedTuple):
    Data: str
    """
    Type of data being returned 
    """

    Payload: bytes
    """
    Type of data being returned 
    """