# CERTUS API Documentation

## Overview

CERTUS is a high-performance scientific software suite for the design and characterization of optical thin films. This document provides technical documentation for developers working with the CERTUS codebase.

## Architecture

### Core Modules

#### certus_core.py
Central configuration and system management module.

**Key Classes:**
- `GlobalConfig`: Immutable global configuration
- `SystemConfig`: System-wide settings and logging
- `ConfigManager`: JSON-based configuration persistence

**Key Functions:**
```python
def bootstrap_app(app_file: str, log_name: str | None = None) -> str
    """Initialize application environment and return script directory."""

def setup_logging(log_file: str | None = None, level: int = logging.INFO) -> logging.Logger
    """Configure enhanced logging with file rotation and detailed context."""

def get_logger() -> logging.Logger
    """Get the configured logger instance."""
```

#### certus_ui.py
User interface components and theming system.

**Key Classes:**
- `CertusTheme`: Centralized theme configuration
- `CertusScientificPlot`: Enhanced plotting widget
- `ExcelTableWidget`: Data table with Excel export

**Theme Configuration:**
```python
# Apply theme
CertusTheme.configure(mode="light")  # or "dark"
apply_certus_theme(window, plots)
```

#### certus_physics package
High-performance physics kernels with Numba JIT compilation.

**Main Components:**
- `structures.py`: Data structures (Layer, Target, Sample)
- `materials_data.py`: Material optical constants
- `_certus_physics_impl.py`: JIT-compiled kernels

**Key Functions:**
```python
def compute_TMM_generic(layers: List[Layer], wavelengths: np.ndarray) -> np.ndarray
    """Generic Transfer Matrix Method computation."""

def calculate_RT_vectorized_real(layers: List[Layer], targets: List[Target]) -> Tuple[np.ndarray, np.ndarray]
    """Vectorized reflection and transmission calculation."""
```

### Error Handling

The system uses a hierarchical exception structure:

```python
class CertusError(Exception):
    """Base exception with message, details, and suggestion."""

class CertusValidationError(CertusError):
    """Parameter validation errors."""

class CertusPhysicsError(CertusError):
    """Physics calculation errors."""

class CertusOptimizationError(CertusError):
    """Optimization algorithm errors."""

class CertusConvergenceError(CertusOptimizationError):
    """Optimization convergence failures."""
```

## Usage example

### Basic Calculation

```python
from certus_physics import Layer, Sample, compute_TMM_generic
import numpy as np

# Define layers
layers = [
    Layer(mat="SiO2", qwot=1.0, var=True),
    Layer(mat="TiO2", qwot=0.5, var=True),
]

# Define wavelength range
wavelengths = np.linspace(400, 800, 100)

# Calculate spectrum
spectrum = compute_TMM_generic(layers, wavelengths)
```

### Optimization Setup

```python
from certus_physics import PGlobalConfig, Target
from certus_errors import CertusOptimizationError

try:
    config = PGlobalConfig.for_index(max_feval=80000, max_time=240.0)
    target = Target(lmin=500.0, lmax=600.0, tmin=0.45, tmax=0.55, w=1.0, on=True)
    
    # Run optimization
    # result = optimize_structure(config, targets=[target])  # pseudo-code (depends on app/service)
    
except CertusConvergenceError as e:
    print(f"Optimization failed: {e.full_message}")
```

### Custom UI Component

```python
from certus_ui import CertusTheme, create_styled_button
from PyQt6.QtWidgets import QWidget, QVBoxLayout

class CustomWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Use themed button
        btn = create_styled_button("Calculate", CertusTheme.PRIMARY)
        btn.clicked.connect(self.calculate)
        
        layout.addWidget(btn)
        self.setLayout(layout)
```

## Performance Considerations

### Numba JIT
- All physics kernels are JIT-compiled for maximum performance
- First run includes compilation overhead
- Subsequent runs are native-speed

### Memory Management
- Use `get_float_dtype()` and `get_complex_dtype()` for optimal precision
- Large arrays should use float32 for non-gradient computations
- Gradient computations automatically use float64/c128

### Parallel Processing
```python
from certus_core import get_safe_worker_count

# Get optimal worker count
n_workers = get_safe_worker_count()
```

## Configuration

### System Configuration
Configuration is managed through JSON files in the application directory:

- `certus_export.json`: Export settings
- `certus_theme.json`: Theme preferences

### Logging Configuration
```python
# Setup detailed logging
logger = setup_logging(
    log_file="my_module.log",
    level=logging.DEBUG
)

# Log with context
logger.info("Starting computation", extra={
    'module': 'my_module',
    'operation': 'tmm_calculation'
})
```

## Testing

The suite includes comprehensive tests in the `/tests` directory:

```bash
# Run smoke tests
python tests/smoke_test_suite.py

# Run specific verification
python tests/verify_tmm_consistency.py
```

## Best Practices

1. **Error Handling**: Always use specific Certus exceptions
2. **Logging**: Use the configured logger with appropriate levels
3. **Performance**: Leverage Numba-compiled functions
4. **UI Components**: Use themed components from certus_ui
5. **Configuration**: Use ConfigManager for persistent settings

## Module Dependencies

```
certus_core.py
├── certus_ui.py
├── certus_data.py  
├── certus_errors.py
└── certus_physics/
    ├── structures.py
    ├── materials_data.py
    └── _certus_physics_impl.py
```

## Version Information

Current version: `v26.01` (build 1102)

Version string available as:
```python
from certus_core import __version__
print(__version__)  # "26_01"
```
