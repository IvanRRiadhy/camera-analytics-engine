
from camera_analytics.sdk import AnalyticsModule, AnalyticsResult, AnalyticsEvent, AnalyticsEventType

class PeopleCounterDynamicPlugin(AnalyticsModule):
    def __init__(self, name: str = "people_counter") -> None:
        super().__init__(name=name, description="Dynamic People Counter Plugin")
        self.count = 0

    def update(self, context) -> AnalyticsResult:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene) -> AnalyticsResult:
        self.count = len(scene.tracks)
        events = []
        if scene.frame.frame_index % 30 == 0:
            events.append(AnalyticsEvent(
                event_id=f"evt_pc_{scene.frame.frame_index}",
                module_name=self.name,
                event_type=AnalyticsEventType.INFO,
                message=f"[PeopleCounterDynamicPlugin] Count: {self.count} people active",
                timestamp=scene.frame.timestamp,
                frame_index=scene.frame.frame_index,
            ))
        return AnalyticsResult(module_name=self.name, events=events, metrics={"people_count": self.count})
