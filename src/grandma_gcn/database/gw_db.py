from sqlalchemy import Column, String
from grandma_gcn.database.base import Base


class GW_alert(Base):
    __tablename__ = "gw_alerts"

    triggerId = Column(String, primary_key=True)
    thread_ts = Column(String, nullable=True)

    def __repr__(self):
        return f"<GW_alert(triggerId='{self.triggerId}', thread_ts='{self.thread_ts}')>"
