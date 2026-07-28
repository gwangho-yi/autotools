from dataclasses import dataclass, field


@dataclass
class ClickPoint:
    x: int = 0
    y: int = 0
    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    ms: int = 500
    click_type: str = "left"  # "left" | "right" | "double"

    @property
    def delay_ms(self) -> int:
        return (self.hours * 3600 + self.minutes * 60 + self.seconds) * 1000 + self.ms
