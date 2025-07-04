from sqlalchemy import Column, String, Integer
from grandma_gcn.database.base import Base


class GW_alert(Base):
    __tablename__ = "gw_alerts"

    triggerId = Column(String, primary_key=True)
    thread_ts = Column(String, nullable=True)
    reception_count = Column(Integer, default=1, nullable=False)

    def __repr__(self):
        return f"<GW_alert(triggerId='{self.triggerId}', thread_ts='{self.thread_ts}')>"

    @classmethod
    def insert_or_increment(
        cls, session, trigger_id: str, thread_ts: str | None = None
    ):
        """
        Insère une nouvelle alerte GW ou incrémente son compteur si elle existe déjà.
        """
        alert = session.query(cls).filter_by(triggerId=trigger_id).first()
        if alert:
            alert.reception_count += 1
        else:
            alert = cls(triggerId=trigger_id, thread_ts=thread_ts)
            session.add(alert)
        session.commit()
        return alert
