
from camera_analytics.sdk import AnalyticsModule, AnalyticsResult, AnalyticsEvent, AnalyticsEventType

class DwellTimeDynamicPlugin(AnalyticsModule):
    def __init__(self, name: str = "dwell_time") -> None:
        super().__init__(name=name, description="Dynamic Dwell Time Plugin")

    def update(self, context) -> AnalyticsResult:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene) -> AnalyticsResult:
        events = []
        if scene.frame.frame_index % 50 == 0:
            events.append(AnalyticsEvent(
                event_id=f"evt_dt_{scene.frame.frame_index}",
                module_name=self.name,
                event_type=AnalyticsEventType.INFO,
                message=f"[DwellTimeDynamicPlugin] Evaluating dwell times for {len(scene.tracks)} tracks",
                timestamp=scene.frame.timestamp,
                frame_index=scene.frame.frame_index,
            ))
        return AnalyticsResult(module_name=self.name, events=events)
