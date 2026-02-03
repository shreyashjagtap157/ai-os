from pydantic import BaseModel
from typing import Optional


class PluginManifest(BaseModel):
    """Schema for plugin permission manifest.

    Fields:
    - network: whether network access is allowed
    - filesystem: whether unrestricted filesystem access is allowed
    - exec: whether subprocess/exec is allowed
    - max_cpu_seconds: maximum execution time in seconds
    - max_memory_mb: maximum memory (RSS) in megabytes
    """

    name: Optional[str] = None
    network: bool = False
    filesystem: bool = False
    exec: bool = False
    max_cpu_seconds: int = 5
    max_memory_mb: int = 256

    class Config:
        extra = "ignore"
