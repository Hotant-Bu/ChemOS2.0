# Generated by sila2.code_generator; sila2.__version__: 0.10.1
# -----
# This class does not do anything useful at runtime. Its only purpose is to provide type annotations.
# Since sphinx does not support .pyi files (yet?), so this is a .py file.
# -----

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterable, Optional

    from hplcmssimulator_types import (
        BlankRun_IntermediateResponses,
        BlankRun_Responses,
        Status_Responses,
        SubmitJobChemspeed_IntermediateResponses,
        SubmitJobChemspeed_Responses,
        ValveStatus_Responses,
    )
    from sila2.client import ClientMetadataInstance, ClientObservableCommandInstanceWithIntermediateResponses


class HPLCMSsimulatorClient:
    """

    Runs the HPLCMS using a given synthesis procedure

    """

    def Status(self, *, metadata: Optional[Iterable[ClientMetadataInstance]] = None) -> Status_Responses:
        """
        Gets the Status of the HPLC
        """
        ...

    def ValveStatus(
        self, Purpose: str, StatusUpdate: str, *, metadata: Optional[Iterable[ClientMetadataInstance]] = None
    ) -> ValveStatus_Responses:
        """
        Gets the Status of the HPLC
        """
        ...

    def BlankRun(
        self, *, metadata: Optional[Iterable[ClientMetadataInstance]] = None
    ) -> ClientObservableCommandInstanceWithIntermediateResponses[BlankRun_IntermediateResponses, BlankRun_Responses]:
        """
        Cleans the HPLCMS column
        """
        ...

    def SubmitJobChemspeed(
        self, JobFile: str, *, metadata: Optional[Iterable[ClientMetadataInstance]] = None
    ) -> ClientObservableCommandInstanceWithIntermediateResponses[
        SubmitJobChemspeed_IntermediateResponses, SubmitJobChemspeed_Responses
    ]:
        """
        Submits a Job for the HPLCMS to do
        """
        ...