from typing import Self
from sqlalchemy import Column, String, Integer
from grandma_gcn.database.base import Base
from sqlalchemy.orm import sessionmaker


class GW_alert(Base):
    __tablename__ = "gw_alerts"

    triggerId = Column(String, primary_key=True)
    thread_ts = Column(String, nullable=True)
    reception_count = Column(Integer, default=1, nullable=False)

    def __repr__(self):
        return f"<GW_alert(triggerId='{self.triggerId}', thread_ts='{self.thread_ts}')>"

    def set_thread_ts(self, thread_ts: str | None, session: sessionmaker):
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
    def get_by_trigger_id(cls, session: sessionmaker, trigger_id: str) -> Self | None:
        """
        Retrieve a GW_alert instance by its triggerId.

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
        return session.query(cls).filter_by(triggerId=trigger_id).first()

    def increment_reception_count(self, session: sessionmaker):
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
        cls, session, trigger_id: str, thread_ts: str | None = None
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
        alert = cls.get_by_trigger_id(session, trigger_id)
        if not alert:
            alert = cls(triggerId=trigger_id, thread_ts=thread_ts)
            session.add(alert)
            session.commit()
        return alert

    @classmethod
    def get_or_set_thread_ts(
        cls, session: sessionmaker, trigger_id: str, thread_ts: str | None = None
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
        alert = cls.get_by_trigger_id(session, trigger_id)
        if alert and alert.thread_ts is None:
            alert.set_thread_ts(thread_ts, session)
        return alert

    @classmethod
    def insert_or_increment(
        cls, session: sessionmaker, trigger_id: str, thread_ts: str | None = None
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
        alert = cls.get_by_trigger_id(session, trigger_id)

        if alert:
            alert.increment_reception_count(session)
        else:
            alert = cls(triggerId=trigger_id, thread_ts=thread_ts)
            session.add(alert)
            session.commit()

        return alert
