"""Abstract base class all sensors must implement."""
from abc import ABC, abstractmethod
import numpy as np

class SensorBase(ABC):
    @abstractmethod
    def start(self): pass

    @abstractmethod
    def get_frame(self) -> np.ndarray:
        """Returns a BGR uint8 numpy array, shape (H, W, 3)."""

    @abstractmethod
    def stop(self): pass
