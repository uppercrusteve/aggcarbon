"""aggcarbon: soil aggregate stability and carbon pool indices.

The package converts wet-sieving aggregate fraction masses and SOC/POC/MAOC
concentrations into stability indices, equivalent-soil-mass corrected stocks,
and the carbon pool index (CPI) / carbon management index (CMI).
"""

from __future__ import annotations

__version__ = "0.1.0"

from aggcarbon.compute import compute_dataset
from aggcarbon.io import ValidationError, read_dataset, validate_dataset

__all__ = ["ValidationError", "compute_dataset", "read_dataset", "validate_dataset", "__version__"]
