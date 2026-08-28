from dataclasses import dataclass, field
from typing import List, Optional
import datetime
import random

MIN_SAFE_SPEED_KMPH = 5.0
BETA_CONGESTION = 0.5
ALPHA_SMOOTHING = 0.3


@dataclass
class WeatherCondition:
    visibility_m: float = 1000.0
    precipitation: str = "none"
    wind_kmph: float = 10.0

    def factor(self) -> float:
        if self.visibility_m < 200:
            return 0.6
        if self.precipitation in ("snow", "heavy_rain"):
            return 0.75
        if self.precipitation == "light_rain":
            return 0.9
        if self.wind_kmph > 60:
            return 0.8
        return 1.0


@dataclass
class Signal:
    position_km: float
    hold_probability: float = 0.0
    avg_stop_duration_min: float = 2.0

    def expected_delay_min(self) -> float:
        return self.hold_probability * self.avg_stop_duration_min


@dataclass
class Station:
    name: str
    position_km: float
    scheduled_dwell_min: float = 2.0
    observed_overrun_min: float = 0.5

    def expected_dwell_min(self) -> float:
        return self.scheduled_dwell_min + self.observed_overrun_min


@dataclass
class TrackSegment:
    name: str
    distance_km: float
    speed_limit_kmph: float
    local_speed_restriction_kmph: Optional[float] = None

    def allowed_speed(self) -> float:
        if self.local_speed_restriction_kmph is not None:
            return min(self.speed_limit_kmph, self.local_speed_restriction_kmph)
        return self.speed_limit_kmph


@dataclass
class TrainState:
    train_id: str
    current_time: datetime.datetime
    previous_eta: Optional[datetime.datetime] = None


def congestion_factor(trains_in_block_section: int, beta: float = BETA_CONGESTION) -> float:
    return 1.0 / (1.0 + beta * trains_in_block_section)


class ETAPredictor:
    def __init__(self, alpha: float = ALPHA_SMOOTHING):
        self.alpha = alpha

    def calculate(
        self,
        train_state: TrainState,
        segments: List[TrackSegment],
        weather: WeatherCondition,
        signals: List[Signal],
        stations: List[Station],
        trains_in_block: List[int],
        verbose: bool = True,
    ) -> datetime.datetime:

        total_time_hr = 0.0
        weather_f = weather.factor()

        if verbose:
            print(f"\nCalculating ETA for {train_state.train_id}")
            print(f"Weather factor: {weather_f:.2f}")

        for i, seg in enumerate(segments):
            n_trains = trains_in_block[i] if i < len(trains_in_block) else 0
            cong_f = congestion_factor(n_trains)
            base_speed = seg.allowed_speed()

            effective_speed = base_speed * weather_f * cong_f
            effective_speed = max(effective_speed, MIN_SAFE_SPEED_KMPH)

            seg_time_hr = seg.distance_km / effective_speed
            total_time_hr += seg_time_hr

            if verbose:
                tsr_note = f" (TSR: {seg.local_speed_restriction_kmph} km/h)" if seg.local_speed_restriction_kmph else ""
                print(
                    f"  Segment '{seg.name}': {seg.distance_km} km @ {effective_speed:.1f} km/h (x{cong_f:.2f}){tsr_note} -> {seg_time_hr*60:.1f} min")

        signal_delay_min = sum(s.expected_delay_min() for s in signals)
        dwell_delay_min = sum(st.expected_dwell_min() for st in stations)

        total_time_min = (total_time_hr * 60) + \
            signal_delay_min + dwell_delay_min
        raw_eta = train_state.current_time + \
            datetime.timedelta(minutes=total_time_min)

        if train_state.previous_eta is not None:
            prev_ts = train_state.previous_eta.timestamp()
            new_ts = raw_eta.timestamp()
            smoothed_ts = self.alpha * new_ts + (1 - self.alpha) * prev_ts
            final_eta = datetime.datetime.fromtimestamp(smoothed_ts)
        else:
            final_eta = raw_eta

        if verbose:
            print(f"Raw ETA:      {raw_eta.strftime('%H:%M:%S')}")
            print(f"Smoothed ETA: {final_eta.strftime('%H:%M:%S')}")

        train_state.previous_eta = final_eta
        return final_eta


def run_demo():
    predictor = ETAPredictor(alpha=ALPHA_SMOOTHING)

    segments = [
        TrackSegment("Yard Exit -> Junction A",
                     distance_km=8, speed_limit_kmph=80),
        TrackSegment("Junction A -> Bridge", distance_km=12,
                     speed_limit_kmph=100, local_speed_restriction_kmph=40),
        TrackSegment("Bridge -> Curve Zone",
                     distance_km=6, speed_limit_kmph=90),
        TrackSegment("Curve Zone -> Suburb Junction",
                     distance_km=15, speed_limit_kmph=100),
        TrackSegment("Suburb Junction -> Terminus",
                     distance_km=9, speed_limit_kmph=70),
    ]

    signals = [
        Signal(position_km=10, hold_probability=0.4, avg_stop_duration_min=3),
        Signal(position_km=25, hold_probability=0.2, avg_stop_duration_min=2),
    ]

    stations = [
        Station(name="Suburb Junction", position_km=41,
                scheduled_dwell_min=2, observed_overrun_min=1),
    ]

    train_state = TrainState(
        train_id="Express-4521",
        current_time=datetime.datetime.now(),
    )

    scenarios = [
        {
            "weather": WeatherCondition(visibility_m=1000, precipitation="none"),
            "trains_in_block": [0, 1, 0, 0, 0],
        },
        {
            "weather": WeatherCondition(visibility_m=800, precipitation="light_rain"),
            "trains_in_block": [1, 2, 1, 0, 0],
        },
        {
            "weather": WeatherCondition(visibility_m=150, precipitation="heavy_rain"),
            "trains_in_block": [2, 3, 1, 1, 0],
        },
        {
            "weather": WeatherCondition(visibility_m=900, precipitation="none"),
            "trains_in_block": [1, 1, 0, 0, 0],
        },
    ]

    for step, scenario in enumerate(scenarios, start=1):
        print(
            f"\nUpdate {step} (t={train_state.current_time.strftime('%H:%M:%S')})")
        predictor.calculate(
            train_state=train_state,
            segments=segments,
            weather=scenario["weather"],
            signals=signals,
            stations=stations,
            trains_in_block=scenario["trains_in_block"],
        )

        train_state.current_time += datetime.timedelta(
            minutes=random.randint(3, 6))


if __name__ == "__main__":
    run_demo()
