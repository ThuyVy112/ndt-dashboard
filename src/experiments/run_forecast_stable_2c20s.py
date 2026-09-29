"""
Mininet -> 2 UDP sinks -> 2 UDP generators -> ForecastDataRunner -> cleanup
"""
#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

from src.experiments.runners.forecast_data_runner import (
    ForecastDataRunner,
    ForecastRunConfig,
)
from src.experiments.workloads.capacity_mapper import (
    CapacityWorkloadMapper,
)
from src.experiments.workloads.stable import StableWorkload