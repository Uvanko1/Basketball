from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List

from Project.config import THRESHOLD_SCORES


@dataclass
class GameEvent:
    time: float
    event: str
    payload: Dict = field(default_factory=dict)


class SessionRecorder:
    def __init__(self, fs: float, graph_window_sec: float = 1.0):
        self.fs = fs
        self.dt = 1.0 / fs
        self.t_global = 0.0
        self.score = 0
        self.graph_window_sec = graph_window_sec

        max_plot_samples = max(1, int(graph_window_sec * fs))
        self.eeg_plot_buffer: Deque[float] = deque(maxlen=max_plot_samples)
        self.emg_plot_buffer: Deque[float] = deque(maxlen=max_plot_samples)
        self.emg_int_plot_buffer: Deque[float] = deque(maxlen=max_plot_samples)
        self.alpha_plot_buffer: Deque[float] = deque(maxlen=max_plot_samples)
        self.time_plot_buffer: Deque[float] = deque(maxlen=max_plot_samples)

        self.eeg_full: List[float] = []
        self.emg_full: List[float] = []
        self.emg_int_full: List[float] = []
        self.alpha_full: List[float] = []
        self.time_full: List[float] = []

        self.game_events: List[GameEvent] = []

        self._current_alpha = 0.0

    @property
    def max_plot_samples(self) -> int:
        return self.eeg_plot_buffer.maxlen or 0

    def add_sample(self, eeg_val: float, emg_val: float, emg_int_val: float) -> None:
        self.t_global += self.dt

        self.eeg_plot_buffer.append(eeg_val)
        self.emg_plot_buffer.append(emg_val)
        self.emg_int_plot_buffer.append(emg_int_val)
        self.alpha_plot_buffer.append(self._current_alpha)
        self.time_plot_buffer.append(self.t_global)

        self.eeg_full.append(eeg_val)
        self.emg_full.append(emg_val)
        self.emg_int_full.append(emg_int_val)
        self.alpha_full.append(self._current_alpha)
        self.time_full.append(self.t_global)

    def set_current_alpha(self, alpha_val: float) -> None:
        self._current_alpha = alpha_val

    def register_threshold_hit(self, threshold_index: int) -> int:
        self.score += THRESHOLD_SCORES[threshold_index]
        self.game_events.append(
            GameEvent(
                time=self.t_global,
                event=f"THRESHOLD_{threshold_index}",
                payload={"score": self.score},
            )
        )
        return self.score

    def register_thresholds_changed(self, th1: int, th2: int, th3: int) -> None:
        self.game_events.append(
            GameEvent(
                time=self.t_global,
                event="THRESHOLDS",
                payload={"th1": th1, "th2": th2, "th3": th3},
            )
        )

    def register_emg_threshold_changed(self, emg_value: float) -> None:
        self.game_events.append(
            GameEvent(
                time=self.t_global,
                event="EMG_THRESHOLD",
                payload={"value": emg_value},
            )
        )

    def register_alpha_band_changed(self, low: float, high: float) -> None:
        self.game_events.append(
            GameEvent(
                time=self.t_global,
                event="ALPHA_BAND",
                payload={"low": low, "high": high},
            )
        )
