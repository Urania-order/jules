from abc import ABC, abstractmethod
from typing import Dict, Any, List

class Evolvable(ABC):
    @abstractmethod
    def advance_lifecycle(self, entity_id: int) -> Any:
        """Move the entity to the next state in its lifecycle"""
        pass

    @abstractmethod
    def get_lifecycle_state(self, entity_id: int) -> str:
        """Get the current lifecycle state of the entity"""
        pass

class Observable(ABC):
    @abstractmethod
    def get_health_metrics(self) -> Dict[str, Any]:
        """Return health metrics for the subsystem"""
        pass

    @abstractmethod
    def get_evolution_summary(self) -> List[Dict[str, Any]]:
        """Return a summary of evolution events in the subsystem"""
        pass
