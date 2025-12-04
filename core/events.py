from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Event:
    time: int
    pid: str
    action: str
    result: str
    details: Dict[str, Any] = field(default_factory=dict)
