"""Tests for the GRB_alert class."""

from grandma_gcn.gcn_stream.grb_alert import GRB_alert, Mission


class TestSwiftAlert:
    """Tests for Swift GRB alerts."""

    def test_swift_bat_trigger_id(self, swift_bat_alert: GRB_alert):
        """Test trigger ID extraction from Swift BAT alert."""
        assert swift_bat_alert.trigger_id == "1423875"

    def test_swift_bat_mission(self, swift_bat_alert: GRB_alert):
        """Test mission is correctly set for Swift."""
        assert swift_bat_alert.mission == Mission.SWIFT

    def test_swift_bat_packet_type(self, swift_bat_alert: GRB_alert):
        """Test packet type extraction (type 61 = BAT_GRB_POS_ACK)."""
        assert swift_bat_alert.packet_type == 61

    def test_swift_bat_position(self, swift_bat_alert: GRB_alert):
        """Test position extraction from Swift BAT alert."""
        assert swift_bat_alert.ra is not None
        assert swift_bat_alert.dec is not None

    def test_swift_bat_error(self, swift_bat_alert: GRB_alert):
        """Test error radius extraction."""
        assert swift_bat_alert.ra_dec_error is not None
        assert swift_bat_alert.ra_dec_error >= 0

    def test_swift_bat_trigger_time(self, swift_bat_alert: GRB_alert):
        """Test trigger time extraction."""
        assert swift_bat_alert.trigger_time is not None

    def test_swift_bat_should_process(self, swift_bat_alert: GRB_alert):
        """Test that BAT alerts should be processed."""
        assert swift_bat_alert.should_process_alert() is True

    def test_swift_xrt_packet_type(self, swift_xrt_alert: GRB_alert):
        """Test XRT packet type (type 67)."""
        assert swift_xrt_alert.packet_type == 67

    def test_swift_xrt_trigger_id(self, swift_xrt_alert: GRB_alert):
        """Test XRT trigger ID matches BAT."""
        assert swift_xrt_alert.trigger_id == "1423875"

    def test_swift_xrt_position(self, swift_xrt_alert: GRB_alert):
        """Test XRT has better position than BAT."""
        assert swift_xrt_alert.ra is not None
        assert swift_xrt_alert.dec is not None

    def test_swift_xrt_should_process(self, swift_xrt_alert: GRB_alert):
        """Test that XRT alerts should be processed."""
        assert swift_xrt_alert.should_process_alert() is True

    def test_swift_uvot_packet_type(self, swift_uvot_alert: GRB_alert):
        """Test UVOT packet type (type 81)."""
        assert swift_uvot_alert.packet_type == 81

    def test_swift_uvot_should_process(self, swift_uvot_alert: GRB_alert):
        """Test that UVOT alerts should be processed."""
        assert swift_uvot_alert.should_process_alert() is True


class TestSvomAlert:
    """Tests for SVOM GRB alerts."""

    def test_svom_eclairs_trigger_id(self, svom_eclairs_alert: GRB_alert):
        """Test trigger ID extraction from SVOM ECLAIRs alert."""
        assert svom_eclairs_alert.trigger_id == "sb25120806"

    def test_svom_eclairs_mission(self, svom_eclairs_alert: GRB_alert):
        """Test mission is correctly set for SVOM."""
        assert svom_eclairs_alert.mission == Mission.SVOM

    def test_svom_eclairs_packet_type(self, svom_eclairs_alert: GRB_alert):
        """Test packet type extraction (type 202 = ECLAIRs wakeup)."""
        assert svom_eclairs_alert.packet_type == 202

    def test_svom_eclairs_position(self, svom_eclairs_alert: GRB_alert):
        """Test position extraction from SVOM alert."""
        assert svom_eclairs_alert.ra is not None
        assert svom_eclairs_alert.dec is not None

    def test_svom_eclairs_error(self, svom_eclairs_alert: GRB_alert):
        """Test error radius extraction."""
        assert svom_eclairs_alert.ra_dec_error is not None

    def test_svom_eclairs_trigger_time(self, svom_eclairs_alert: GRB_alert):
        """Test trigger time extraction."""
        assert svom_eclairs_alert.trigger_time is not None

    def test_svom_eclairs_should_process(self, svom_eclairs_alert: GRB_alert):
        """Test that ECLAIRs alerts should be processed."""
        assert svom_eclairs_alert.should_process_alert() is True

    def test_svom_mxt_packet_type(self, svom_mxt_alert: GRB_alert):
        """Test MXT packet type (type 209)."""
        assert svom_mxt_alert.packet_type == 209


class TestGRBAlertFromDbModel:
    """Tests for creating GRB_alert from database model."""

    def test_from_db_model(self, sqlite_engine_and_session, swift_bat_alert: GRB_alert):
        """Test creating GRB_alert from database model."""
        from grandma_gcn.database.grb_db import GRB_alert as GRB_alert_DB

        _, Session = sqlite_engine_and_session
        session = Session()

        # Create a DB entry
        db_alert = GRB_alert_DB(
            triggerId=swift_bat_alert.trigger_id,
            mission=swift_bat_alert.mission.value,
            packet_type=swift_bat_alert.packet_type,
            ra=swift_bat_alert.ra,
            dec=swift_bat_alert.dec,
            error_deg=swift_bat_alert.ra_dec_error,
            trigger_time=swift_bat_alert.trigger_time_as_datetime,
            xml_payload=swift_bat_alert.xml_string,
        )
        session.add(db_alert)
        session.commit()

        # Recreate from DB model
        recreated = GRB_alert.from_db_model(db_alert)

        assert recreated.trigger_id == swift_bat_alert.trigger_id
        assert recreated.mission == swift_bat_alert.mission
        assert recreated.packet_type == swift_bat_alert.packet_type

        session.close()
