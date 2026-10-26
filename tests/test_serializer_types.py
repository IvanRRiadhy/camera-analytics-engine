import datetime
import pathlib
import pytest
import numpy as np

from camera_analytics.events.models import BaseRuntimeEvent
from camera_analytics.communication.models import AnalyticsEventSerializer, _json_default


class TestSerializerTypeFallback:
    """Tests for AnalyticsEventSerializer._json_default and serialization fallbacks."""

    def test_float32_serialization(self):
        val = np.float32(3.14)
        evt = BaseRuntimeEvent(attributes={"score": val})
        serialized = AnalyticsEventSerializer.serialize(evt)
        assert '"score":3.14' in serialized or '"score":3.140000' in serialized
        data = AnalyticsEventSerializer.deserialize(serialized)
        assert isinstance(data["attributes"]["score"], float)
        assert abs(data["attributes"]["score"] - 3.14) < 1e-4

    def test_int64_serialization(self):
        val = np.int64(42)
        evt = BaseRuntimeEvent(attributes={"count": val})
        serialized = AnalyticsEventSerializer.serialize(evt)
        assert '"count":42' in serialized
        data = AnalyticsEventSerializer.deserialize(serialized)
        assert isinstance(data["attributes"]["count"], int)
        assert data["attributes"]["count"] == 42

    def test_bool_serialization(self):
        val = np.bool_(True)
        evt = BaseRuntimeEvent(attributes={"flag": val})
        serialized = AnalyticsEventSerializer.serialize(evt)
        assert '"flag":true' in serialized
        data = AnalyticsEventSerializer.deserialize(serialized)
        assert data["attributes"]["flag"] is True

    def test_ndarray_serialization(self):
        val = np.array([1, 2, 3], dtype=np.int32)
        evt = BaseRuntimeEvent(attributes={"arr": val})
        serialized = AnalyticsEventSerializer.serialize(evt)
        assert '"arr":[1,2,3]' in serialized
        data = AnalyticsEventSerializer.deserialize(serialized)
        assert data["attributes"]["arr"] == [1, 2, 3]

    def test_pathlib_serialization(self):
        val = pathlib.Path("logs/snapshots/plate.jpg")
        evt = BaseRuntimeEvent(attributes={"path": val})
        serialized = AnalyticsEventSerializer.serialize(evt)
        data = AnalyticsEventSerializer.deserialize(serialized)
        assert "logs" in data["attributes"]["path"]
        assert "plate.jpg" in data["attributes"]["path"]

    def test_datetime_serialization(self):
        dt = datetime.datetime(2026, 10, 26, 12, 0, 0, tzinfo=datetime.timezone.utc)
        evt = BaseRuntimeEvent(attributes={"dt": dt})
        serialized = AnalyticsEventSerializer.serialize(evt)
        data = AnalyticsEventSerializer.deserialize(serialized)
        assert data["attributes"]["dt"].startswith("2026-10-26T12:00:00")

    def test_set_and_tuple_serialization(self):
        evt = BaseRuntimeEvent(attributes={"s": {1, 2}, "t": (3, 4)})
        serialized = AnalyticsEventSerializer.serialize(evt)
        data = AnalyticsEventSerializer.deserialize(serialized)
        assert set(data["attributes"]["s"]) == {1, 2}
        assert data["attributes"]["t"] == [3, 4]

    def test_unsupported_type_raises_type_error(self):
        class CustomObject:
            pass

        evt = BaseRuntimeEvent(attributes={"obj": CustomObject()})
        with pytest.raises(TypeError) as exc_info:
            AnalyticsEventSerializer.serialize(evt)
        assert "is not JSON serializable" in str(exc_info.value)

    def test_plain_attributes_parity(self):
        evt = BaseRuntimeEvent(
            camera_id="cam_01",
            plugin_name="Vehicle LPR",
            event_type="VEHICLE_LPR",
            confidence=0.95,
            attributes={"plate_text": "B1234ABC", "valid": True, "count": 5},
        )
        serialized = AnalyticsEventSerializer.serialize(evt)
        data = AnalyticsEventSerializer.deserialize(serialized)
        assert data["attributes"] == {"plate_text": "B1234ABC", "valid": True, "count": 5}
        assert data["camera_id"] == "cam_01"
        assert data["plugin_name"] == "Vehicle LPR"
