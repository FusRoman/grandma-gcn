from typing import Self

from sqlalchemy import JSON, Boolean, Column, Integer, String, desc
from sqlalchemy.orm import Session

from grandma_gcn.database.base import Base


class GW_alert(Base):
    __tablename__ = "gw_alerts"

    id_gw = Column(Integer, primary_key=True, autoincrement=True)
    triggerId = Column(String)
    thread_ts = Column(String, nullable=True)
    reception_count = Column(Integer, default=1, nullable=False)
    payload_json = Column(JSON, nullable=True)
    message_ts = Column(String, nullable=True, unique=True)
    is_process_running = Column(Boolean, default=False, nullable=False)
    owncloud_url = Column(String, nullable=True, unique=True)

    def __repr__(self) -> str:
        excluded_fields = {"payload_json"}
        values = {
            c.name: getattr(self, c.name)
            for c in self.__table__.columns
            if c.name not in excluded_fields
        }
        formatted = ", ".join(f"{k}={v!r}" for k, v in values.items())
        return f"<GW_alert({formatted})>"

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

    def set_message_ts(self, message_ts: str | None, session: Session):
        """
        Set the message timestamp for the alert.
        This method commits the change to the database.

        Parameters
        ----------
        message_ts : str | None
            The message timestamp to set, or None to unset.
        session : Session
            SQLAlchemy session to use for the database operation.
        """
        self.message_ts = message_ts
        session.commit()

    def set_owncloud_url(self, owncloud_url: str | None, session: Session):
        """
        Set the OwnCloud URL for the alert.
        This method commits the change to the database.

        Parameters
        ----------
        owncloud_url : str | None
            The OwnCloud URL to set, or None to unset.
        session : Session
            SQLAlchemy session to use for the database operation.
        """
        self.owncloud_url = owncloud_url
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
        GW_alert | None
            The GW_alert database instance if found, otherwise None.
        """
        return (
            session.query(GW_alert)
            .filter_by(triggerId=trigger_id)
            .order_by(desc(GW_alert.reception_count))
            .first()
        )

    @classmethod
    def get_by_message_ts(cls, session: Session, message_ts: str) -> Self | None:
        """
        Retrieve the alert by its message timestamp.

        Parameters
        ----------
        session : Session
            SQLAlchemy session to use for the database operation.
        message_ts : str
            Message timestamp for the alert.

        Returns
        -------
        GW_alert | None
            The GW_alert database instance if found, otherwise None.
        """
        return (
            session.query(GW_alert)
            .filter_by(message_ts=message_ts)
            .order_by(desc(GW_alert.reception_count))
            .first()
        )

    def increment_reception_count(self, session: Session):
        """
        Increment the reception count of an existing alert.

        Parameters
        ----------
        session : Session
            SQLAlchemy session to use for the database operation.
        trigger_id : str
            Unique identifier for the alert.

        Returns
        -------
        GW_alert | None
            The GW_alert database instance if found and updated, otherwise None.
        """
        self.reception_count += 1
        session.commit()

    @classmethod
    def get_or_create(
        cls,
        session,
        trigger_id: str,
        gw_dict_notice: dict,
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
        thread_ts : str | None
            Thread timestamp for the alert, can be None.

        Returns
        -------
        GW_alert
            The GW_alert database instance that was found or created.
        """
        alert = cls.get_last_by_trigger_id(session, trigger_id)
        if not alert:
            alert = cls(
                triggerId=trigger_id, payload_json=gw_dict_notice, thread_ts=thread_ts
            )
            session.add(alert)
            session.commit()
        return alert

    @classmethod
    def get_or_set_thread_ts(
        cls, session: Session, trigger_id: str, thread_ts: str | None = None
    ) -> Self:
        """
        Get an existing alert and set its thread timestamp if it is not already set.

        Parameters
        ----------
        session : Session
            SQLAlchemy session to use for the database operation.
        trigger_id : str
            Unique identifier for the alert.
        thread_ts : str | None
            Thread timestamp for the alert, can be None.

        Returns
        -------
        GW_alert
            The GW_alert database instance that was found or created.
        """
        alert = cls.get_last_by_trigger_id(session, trigger_id)
        if alert and alert.thread_ts is None:
            alert.set_thread_ts(thread_ts, session)
        return alert

    @classmethod
    def get_or_set_message_ts(
        cls, session: Session, trigger_id: str, message_ts: str | None = None
    ) -> Self:
        """
        Get an existing alert and set its message timestamp if it is not already set.

        Parameters
        ----------
        session : Session
            SQLAlchemy session to use for the database operation.
        trigger_id : str
            Unique identifier for the alert.
        message_ts : str | None
            Message timestamp for the alert, can be None.

        Returns
        -------
        GW_alert
            The GW_alert database instance that was found or created.
        """
        alert = cls.get_last_by_trigger_id(session, trigger_id)
        if alert and alert.message_ts is None:
            alert.message_ts = message_ts
            session.commit()
        return alert

    @classmethod
    def insert_or_increment(
        cls, session: Session, trigger_id: str, thread_ts: str | None = None
    ) -> Self:
        """
        Insert a new alert or increment the reception count if it already exists.

        Parameters
        ----------
        session : Session
            SQLAlchemy session to use for the database operation.
        trigger_id : str
            Unique identifier for the alert.
        thread_ts : str | None
            Thread timestamp for the alert, can be None.

        Returns
        -------
        GW_alert
            The GW_alert database instance that was inserted or updated.
        """
        alert = cls.get_last_by_trigger_id(session, trigger_id)

        if alert:
            alert.increment_reception_count(session)
        else:
            alert = cls(triggerId=trigger_id, thread_ts=thread_ts)
            session.add(alert)
            session.commit()

        return alert

    def set_process_running(self, session: Session):
        """
        Set the is_process_running flag for the alert.
        This method commits the change to the database.

        Parameters
        ----------
        is_running : bool
            The value to set for is_process_running.
        session : Session
            SQLAlchemy session to use for the database operation.
        """
        self.is_process_running = True
        session.commit()

    def set_process_not_running(self, session: Session):
        """
        Set the is_process_running flag for the alert to False.
        This method commits the change to the database.

        Parameters
        ----------
        session : Session
            SQLAlchemy session to use for the database operation.
        """
        self.is_process_running = False
        session.commit()

    def get_process_running(self) -> bool:
        """
        Get the is_process_running flag for the alert.

        Returns
        -------
        bool
            The value of is_process_running.
        """
        return self.is_process_running
