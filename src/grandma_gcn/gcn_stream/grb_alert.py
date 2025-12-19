import logging
from enum import Enum
from typing import Self

import voeventparse as vp

from grandma_gcn.database.grb_db import GRB_alert as DBGRBAlert


class Mission(Enum):
    """
    Enum for different missions that can detect GRBs
    """

    SWIFT = "Swift"
    SVOM = "SVOM"
    UNKNOWN = "Unknown"


class GRB_alert:
    """
    Class to handle GRB (Gamma-Ray Burst) alerts from Swift and SVOM missions.
    Parses VOEvent XML alerts from GCN Kafka streams and extracts relevant information.
    """

    def __init__(self, notice: bytes) -> None:
        """
        Initialize a GRB alert from a bytes notice in VOEvent XML format.

        Parameters
        ----------
        notice : bytes
            The GCN notice in VOEvent XML bytes format
        """
        # Parse VOEvent XML
        self.voevent = vp.loads(notice)
        self.logger = logging.getLogger(f"gcn_stream.grb_alert_{self.trigger_id}")

    @classmethod
    def from_db_model(cls, db_model: DBGRBAlert) -> Self:
        """
        Create a GRB_alert instance from a database model.

        Parameters
        ----------
        db_model : DBGRBAlert
            The database model instance containing the notice.

        Returns
        -------
        GRB_alert
            An instance of GRB_alert initialized with the database model data.
        """
        # Get XML from the xml_payload column
        if db_model.xml_payload:
            return cls(db_model.xml_payload.encode("utf-8"))
        else:
            raise ValueError(f"No XML payload found for GRB alert {db_model.triggerId}")

    @property
    def trigger_id(self) -> str:
        """
        Get the trigger ID of the GRB event.
        For SVOM: Burst_Id parameter (e.g., "sb25120806")
        For Swift: TrigID parameter (e.g., "532871")

        Returns
        -------
        str
            The trigger ID
        """
        try:
            top_params = vp.get_toplevel_params(self.voevent)

            # Try TrigID first (Swift)
            if "TrigID" in top_params:
                return str(top_params["TrigID"]["value"])

            # Try grouped params (SVOM has Burst_Id in Svom_Identifiers group)
            grouped_params = vp.get_grouped_params(self.voevent)
            if "Svom_Identifiers" in grouped_params:
                svom_ids = grouped_params["Svom_Identifiers"]
                if "Burst_Id" in svom_ids:
                    return str(svom_ids["Burst_Id"]["value"])

            # Fallback: try to extract from ivorn
            ivorn = self.voevent.attrib.get("ivorn", "")
            if "#" in ivorn:
                return ivorn.split("#")[1]

            return "UNKNOWN"
        except Exception as e:
            self.logger.warning(f"Error extracting trigger ID: {e}")
            return "UNKNOWN"

    @property
    def ra(self) -> float:
        """
        Get the Right Ascension of the GRB localization.

        Returns
        -------
        float
            RA in degrees
        """
        try:
            position = vp.get_event_position(self.voevent)
            return float(position.ra)
        except Exception:
            return 0.0

    @property
    def dec(self) -> float:
        """
        Get the Declination of the GRB localization.

        Returns
        -------
        float
            Dec in degrees
        """
        try:
            position = vp.get_event_position(self.voevent)
            return float(position.dec)
        except Exception:
            return 0.0

    @property
    def ra_dec_error(self) -> float:
        """
        Get the positional uncertainty (error radius).

        Returns
        -------
        float
            Error radius in degrees
        """
        try:
            position = vp.get_event_position(self.voevent)
            return float(position.err)
        except Exception:
            return 0.0

    @property
    def ra_dec_error_arcmin(self) -> float:
        """
        Get the positional uncertainty in arcminutes.

        Returns
        -------
        float
            Error radius in arcminutes
        """
        return self.ra_dec_error * 60.0

    @property
    def trigger_time(self) -> str:
        """
        Get the trigger time of the GRB.

        Returns
        -------
        str
            Trigger time in ISO 8601 format
        """
        try:
            event_time = vp.get_event_time_as_utc(self.voevent)
            if event_time:
                return event_time.isoformat()
            return ""
        except Exception:
            return ""

    @property
    def trigger_time_as_datetime(self):
        """
        Get trigger time as a datetime object for database storage.

        Returns
        -------
        datetime | None
            Trigger time as datetime object
        """
        try:
            return vp.get_event_time_as_utc(self.voevent)
        except Exception:
            return None

    @property
    def trigger_time_formatted(self) -> str:
        """
        Get formatted trigger time for display.

        Returns
        -------
        str
            Human-readable trigger time
        """
        try:
            event_time = vp.get_event_time_as_utc(self.voevent)
            if event_time:
                return event_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            return ""
        except Exception:
            return ""

    @property
    def xml_string(self) -> str:
        """
        Get the VOEvent as an XML string for database storage.

        Returns
        -------
        str
            VOEvent XML as string
        """
        return vp.dumps(self.voevent).decode("utf-8")

    @property
    def packet_type(self) -> int | None:
        """
        Get the packet type number from the VOEvent.
        For Swift: 60-99 (BAT, XRT, UVOT packet types)
        For SVOM: 200+ (ECLAIRs packet types)

        Returns
        -------
        int | None
            The packet type number, or None if not found
        """
        try:
            top_params = vp.get_toplevel_params(self.voevent)
            if "Packet_Type" in top_params:
                return int(top_params["Packet_Type"]["value"])
            return None
        except Exception as e:
            self.logger.warning(f"Error extracting packet type: {e}")
            return None

    @property
    def mission(self) -> Mission:
        """
        Identify the mission that detected this GRB based on VOEvent metadata.

        Returns
        -------
        Mission
            The mission enum value
        """
        try:
            # Check ivorn
            ivorn = self.voevent.attrib.get("ivorn", "").lower()
            if "svom" in ivorn:
                return Mission.SVOM
            if "swift" in ivorn or "bat" in ivorn:
                return Mission.SWIFT

            # Check instrument parameter
            top_params = vp.get_toplevel_params(self.voevent)
            if "Instrument" in top_params:
                instrument = top_params["Instrument"]["value"].lower()
                if "eclairs" in instrument:
                    return Mission.SVOM
                if "bat" in instrument:
                    return Mission.SWIFT

            # Check author
            if hasattr(self.voevent, "Who") and hasattr(
                self.voevent.Who, "AuthorIVORN"
            ):
                author = str(self.voevent.Who.AuthorIVORN).lower()
                if "svom" in author:
                    return Mission.SVOM
                if "swift" in author or "nasa" in author:
                    return Mission.SWIFT

            return Mission.UNKNOWN
        except Exception:
            return Mission.UNKNOWN

    @property
    def skyportal_link(self) -> str:
        """
        Generate the SkyPortal link for this GRB.

        Returns
        -------
        str
            URL to the SkyPortal source page
        """
        return f"https://skyportal-icare.ijclab.in2p3.fr/source/{self.trigger_id}"

    @property
    def slew_status(self) -> str | None:
        """
        Get the slew status for SVOM alerts.

        Returns
        -------
        str | None
            Slew status ("accepted", "rejected", etc.) or None if not found
        """
        try:
            grouped_params = vp.get_grouped_params(self.voevent)
            if "Satellite_Info" in grouped_params:
                sat_info = grouped_params["Satellite_Info"]
                if "Slew_Status" in sat_info:
                    return str(sat_info["Slew_Status"]["value"])
            return None
        except Exception as e:
            self.logger.warning(f"Error extracting slew status: {e}")
            return None

    def should_process_alert(self) -> bool:
        """
        Determine if this GRB alert should be processed based on mission and packet type.

        Filtering rules:
        - SVOM: Process all alerts
        - Swift: Only process specific packet types:
          * 60: BAT_GRB_ALERT
          * 61: BAT_GRB_POS_ACK
          * 62: BAT_GRB_POS_NACK
          * 63: BAT_GRB_LC
          * 65: FOM_OBS
          * 67: XRT_POSITION
          * 69: XRT_IMAGE (or XRT_LIGHTCURVE)

        Returns
        -------
        bool
            True if the alert should be processed, False otherwise
        """
        mission = self.mission
        packet_type = self.packet_type

        # SVOM: only accept packet types 202 (initial), 204 (slewing accepted), 205 (slewing rejected)
        if mission == Mission.SVOM:
            if packet_type is None:
                self.logger.warning(
                    f"SVOM alert {self.trigger_id} has no packet type, skipping"
                )
                return False

            accepted_types = {202, 204, 205}

            if packet_type in accepted_types:
                self.logger.info(
                    f"SVOM alert {self.trigger_id} with packet type {packet_type} accepted"
                )
                return True
            else:
                self.logger.info(
                    f"SVOM alert {self.trigger_id} with packet type {packet_type} rejected (not in accepted types)"
                )
                return False

        # Swift: BAT_GRB_POS_ACK (61) and XRT_POSITION (67)
        if mission == Mission.SWIFT:
            if packet_type is None:
                self.logger.warning(
                    f"Swift alert {self.trigger_id} has no packet type, skipping"
                )
                return False

            accepted_types = {61, 67}

            if packet_type in accepted_types:
                self.logger.info(
                    f"Swift alert {self.trigger_id} with packet type {packet_type} accepted"
                )
                return True
            else:
                self.logger.info(
                    f"Swift alert {self.trigger_id} with packet type {packet_type} rejected (not in accepted types)"
                )
                return False

        # Unknown mission: accept by default
        self.logger.warning(
            f"Alert {self.trigger_id} has unknown mission, accepting by default"
        )
        return True

    def to_slack_format(self) -> dict:
        """
        Format the GRB alert data for Slack notification.

        Returns
        -------
        dict
            Dictionary with formatted alert information
        """
        data = {
            "trigger_id": self.trigger_id,
            "mission": self.mission.value,
            "trigger_time": self.trigger_time_formatted,
            "ra": f"{self.ra:.2f}",
            "dec": f"{self.dec:.2f}",
            "uncertainty_arcmin": f"{self.ra_dec_error_arcmin:.2f}",
            "skyportal_link": self.skyportal_link,
            "packet_type": self.packet_type,
        }

        if self.mission == Mission.SVOM:
            data["slew_status"] = self.slew_status

        return data
