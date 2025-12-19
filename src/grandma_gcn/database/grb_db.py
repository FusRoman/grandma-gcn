from typing import Self

from sqlalchemy import Column, Integer, Float, String, DateTime, Text, desc
from sqlalchemy.orm import Session

from grandma_gcn.database.base import Base


class GRB_alert(Base):
    """
    Database model for GRB (Gamma-Ray Burst) alerts.
    Stores alert metadata with proper columns for efficient querying.
    """

    __tablename__ = "grb_alerts"

    id_grb = Column(Integer, primary_key=True, autoincrement=True)
    triggerId = Column(String, nullable=False, index=True)
    mission = Column(String, nullable=True)  # "Swift" or "SVOM"
    packet_type = Column(Integer, nullable=True)  # Packet type (61=BAT_POS_ACK, 67=XRT, etc.)
    ra = Column(Float, nullable=True)  # Right ascension in degrees
    dec = Column(Float, nullable=True)  # Declination in degrees
    error_deg = Column(Float, nullable=True)  # Error radius in degrees
    trigger_time = Column(DateTime, nullable=True)  # Event timestamp
    reception_count = Column(Integer, default=1, nullable=False)
    thread_ts = Column(String, nullable=True)
    xml_payload = Column(Text, nullable=True)  # Optional: store full VOEvent XML

    def __repr__(self) -> str:
        excluded_fields = {"xml_payload"}
        values = {
            c.name: getattr(self, c.name)
            for c in self.__table__.columns
            if c.name not in excluded_fields
        }
        formatted = ", ".join(f"{k}={v!r}" for k, v in values.items())
        return f"<GRB_alert({formatted})>"

    def set_thread_ts(self, thread_ts: str | None, session: Session):
        """
        Set the thread timestamp for the alert.
        This method commits the change to the database.

        Parameters
        ----------
        thread_ts : str | None
            The thread timestamp to set, or None to unset.
        session : Session
            SQLAlchemy session to use for the database operation.
        """
        self.thread_ts = thread_ts
        session.commit()

    @classmethod
    def get_last_by_trigger_id(cls, session: Session, trigger_id: str) -> Self | None:
        """
        Retrieve the last alert by its trigger ID.

        Parameters
        ----------
        session : Session
            SQLAlchemy session to use for the database operation.
        trigger_id : str
            Unique identifier for the alert.

        Returns
        -------
        GRB_alert | None
            The GRB_alert database instance if found, otherwise None.
        """
        return (
            session.query(GRB_alert)
            .filter_by(triggerId=trigger_id)
            .order_by(desc(GRB_alert.reception_count))
            .first()
        )

    @classmethod
    def get_by_trigger_id_and_packet_type(
        cls, session: Session, trigger_id: str, packet_type: int, get_first: bool = False
    ) -> Self | None:
        """
        Retrieve an alert by trigger ID and packet type.

        Parameters
        ----------
        session : Session
            SQLAlchemy session to use for the database operation.
        trigger_id : str
            Unique identifier for the alert.
        packet_type : int
            Packet type number (e.g., 61 for BAT_POS_ACK, 67 for XRT).
        get_first : bool
            If True, get the first (oldest) alert. If False, get the most recent. Default False.

        Returns
        -------
        GRB_alert | None
            The GRB_alert database instance if found, otherwise None.
        """
        query = session.query(GRB_alert).filter_by(triggerId=trigger_id, packet_type=packet_type)

        if get_first:
            # Get oldest alert (first arrival)
            return query.order_by(GRB_alert.id_grb).first()
        else:
            # Get most recent alert (last arrival)
            return query.order_by(desc(GRB_alert.id_grb)).first()

    @classmethod
    def get_all_by_trigger_id(
        cls, session: Session, trigger_id: str
    ) -> list[Self]:
        """
        Retrieve all alerts for a given trigger ID, ordered by arrival time.

        Parameters
        ----------
        session : Session
            SQLAlchemy session to use for the database operation.
        trigger_id : str
            Unique identifier for the alert.

        Returns
        -------
        list[GRB_alert]
            List of GRB_alert instances ordered by id_grb (arrival order).
        """
        return (
            session.query(GRB_alert)
            .filter_by(triggerId=trigger_id)
            .order_by(GRB_alert.id_grb)
            .all()
        )

    def increment_reception_count(self, session: Session):
        """
        Increment the reception count of an existing alert.

        Parameters
        ----------
        session : Session
            SQLAlchemy session to use for the database operation.
        """
        self.reception_count += 1
        session.commit()

    @classmethod
    def get_or_create(
        cls,
        session: Session,
        trigger_id: str,
        mission: str | None = None,
        ra: float | None = None,
        dec: float | None = None,
        error_deg: float | None = None,
        trigger_time=None,
        xml_payload: str | None = None,
        thread_ts: str | None = None,
    ) -> Self:
        """
        Get an existing alert or create a new one if it does not exist.

        Parameters
        ----------
        session : Session
            SQLAlchemy session to use for the database operation.
        trigger_id : str
            Unique identifier for the alert.
        mission : str | None
            Mission name ("Swift" or "SVOM").
        ra : float | None
            Right ascension in degrees.
        dec : float | None
            Declination in degrees.
        error_deg : float | None
            Error radius in degrees.
        trigger_time : datetime | None
            Event timestamp.
        xml_payload : str | None
            Full VOEvent XML string.
        thread_ts : str | None
            Thread timestamp for the alert, can be None.

        Returns
        -------
        GRB_alert
            The GRB_alert database instance that was found or created.
        """
        alert = cls.get_last_by_trigger_id(session, trigger_id)
        if not alert:
            alert = cls(
                triggerId=trigger_id,
                mission=mission,
                ra=ra,
                dec=dec,
                error_deg=error_deg,
                trigger_time=trigger_time,
                xml_payload=xml_payload,
                thread_ts=thread_ts,
            )
            session.add(alert)
            session.commit()
        return alert
