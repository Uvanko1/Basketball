from dataclasses import dataclass
from typing import Optional


@dataclass
class ThresholdState:
    prev_above_th1: bool = False
    prev_above_th2: bool = False
    prev_above_th3: bool = False
    last_trigger_time: Optional[float] = None

    def reset_edges(self) -> None:
        self.prev_above_th1 = False
        self.prev_above_th2 = False
        self.prev_above_th3 = False

    def reset(self) -> None:
        self.reset_edges()
        self.last_trigger_time = None


def evaluate(
    state: ThresholdState,
    percent_increase: float,
    current_emg_int: float,
    emg_int_threshold: float,
    th1: float,
    th2: float,
    th3: float,
    current_time: float,
    min_trigger_interval: float,
    reset_edges_on_emg_block: bool,
) -> Optional[int]:
    if state.last_trigger_time is not None:
        if (current_time - state.last_trigger_time) < min_trigger_interval:
            return None

    if current_emg_int > emg_int_threshold:
        if reset_edges_on_emg_block:
            state.reset_edges()
        return None

    above_th3 = percent_increase >= th3
    above_th2 = percent_increase >= th2
    above_th1 = percent_increase >= th1

    triggered: Optional[int] = None
    if above_th3 and not state.prev_above_th3:
        triggered = 3
    elif above_th2 and not state.prev_above_th2:
        triggered = 2
    elif above_th1 and not state.prev_above_th1:
        triggered = 1

    if triggered is not None:
        state.last_trigger_time = current_time

    state.prev_above_th1 = above_th1
    state.prev_above_th2 = above_th2
    state.prev_above_th3 = above_th3

    return triggered
