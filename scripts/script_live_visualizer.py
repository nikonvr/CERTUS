"""
Test Live Optimization Visualizer
=================================

Test the live visualization system for real-time optimization monitoring.

Author: CERTUS Suite
Version: 1.0
"""

import sys
from pathlib import Path
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import QTimer

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Import CERTUS components
from certus.utils.certus_live_visualizer import create_live_visualizer


class TestLiveVisualizationWindow(QMainWindow):
    """Test window for live visualization"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CERTUS Live Visualization Test")
        self.setGeometry(100, 100, 1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create live visualizer
        self.visualizer = create_live_visualizer(
            update_interval=500
        )  # Update every 500 evals
        layout.addWidget(self.visualizer.get_widget())

        # Create control buttons
        self.start_button = QPushButton("Start Mock Optimization")
        self.start_button.clicked.connect(self.start_mock_optimization)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Mock Optimization")
        self.stop_button.clicked.connect(self.stop_mock_optimization)
        layout.addWidget(self.stop_button)

        # Mock optimization state
        self.optimization_timer = None
        self.mock_iteration = 0
        self.mock_evaluations = 0
        self.mock_best_rmse = 0.1
        self.mock_params = np.array([100.0, 3.5, 100.0, 4.0, 1.0, 0.5, 2.0])

        # Setup mock data
        self.setup_mock_data()

    def setup_mock_data(self):
        """Setup mock spectral data"""
        # Create mock wavelength range
        self.wavelengths = np.linspace(200, 2000, 200)

        # Create mock target spectra (sapphire-like)
        n_target = 1.76 + 0.01 * (self.wavelengths - 1000) / 1000
        k_target = np.zeros_like(self.wavelengths)
        k_target[self.wavelengths > 1500] = 0.01

        # Calculate mock T,R using simplified Fresnel
        thickness = 100.0
        n_sub = 1.5

        r12 = (n_target - 1.0) / (n_target + 1.0)
        r23 = (n_sub - n_target) / (n_sub + n_target)
        phase = 4 * np.pi * n_target * thickness / self.wavelengths

        self.target_T = (
            (1 - r12**2)
            * (1 - r23**2)
            / (1 + 2 * r12 * r23 * np.cos(phase) + (r12 * r23) ** 2)
        )
        self.target_R = (r12 + r23 * np.cos(phase)) ** 2 / (
            1 + 2 * r12 * r23 * np.cos(phase) + (r12 * r23) ** 2
        )

        # Add noise
        self.target_T += np.random.normal(0, 0.01, self.target_T.shape)
        self.target_R += np.random.normal(0, 0.01, self.target_R.shape)

        # Clip to valid range
        self.target_T = np.clip(self.target_T, 0, 1)
        self.target_R = np.clip(self.target_R, 0, 1)

        # Set target data in visualizer
        self.visualizer.set_target_data(self.wavelengths, self.target_T, self.target_R)

    def start_mock_optimization(self):
        """Start mock optimization for testing"""
        print("Starting mock optimization...")

        # Reset state
        self.mock_iteration = 0
        self.mock_evaluations = 0
        self.mock_best_rmse = 0.1
        self.visualizer.reset()

        # Start timer for mock optimization updates
        self.optimization_timer = QTimer()
        self.optimization_timer.timeout.connect(self.mock_optimization_step)
        self.optimization_timer.start(50)  # Update every 50ms

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_mock_optimization(self):
        """Stop mock optimization"""
        print("Stopping mock optimization...")

        if self.optimization_timer:
            self.optimization_timer.stop()
            self.optimization_timer = None

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def mock_optimization_step(self):
        """Simulate one optimization step"""
        self.mock_iteration += 1
        self.mock_evaluations += np.random.randint(
            1, 10
        )  # Random number of evaluations

        # Simulate convergence (exponential decay)
        target_rmse = 0.001
        self.mock_best_rmse = target_rmse + (0.1 - target_rmse) * np.exp(
            -self.mock_iteration / 50
        )

        # Add some noise
        self.mock_best_rmse += np.random.normal(0, 0.0001)
        self.mock_best_rmse = max(self.mock_best_rmse, target_rmse)

        # Simulate parameter evolution
        noise = np.random.normal(0, 0.01, self.mock_params.shape)
        self.mock_params += noise

        # Keep parameters in reasonable range
        self.mock_params[0] = np.clip(self.mock_params[0], 95, 105)  # thickness
        self.mock_params[1] = np.clip(self.mock_params[1], 3.0, 4.0)  # Eg
        self.mock_params[2:] = np.clip(self.mock_params[2:], 0.1, 10.0)  # other params

        # Request visualizer update
        current_rmse = self.mock_best_rmse + np.random.normal(0, 0.0005)

        self.visualizer.request_update(
            iteration=self.mock_iteration,
            n_evaluations=self.mock_evaluations,
            current_rmse=current_rmse,
            best_rmse=self.mock_best_rmse,
            best_params=self.mock_params,
        )

        # Stop after convergence
        if self.mock_iteration > 200 or self.mock_best_rmse < 0.002:
            self.stop_mock_optimization()
            print(f"Mock optimization completed: RMSE = {self.mock_best_rmse:.6f}")


def main():
    """Main test runner"""
    # Create QApplication
    app = QApplication(sys.argv)

    # Create test window
    window = TestLiveVisualizationWindow()
    window.show()

    print("CERTUS Live Visualization Test")
    print("=" * 40)
    print("1. Click 'Start Mock Optimization' to begin")
    print("2. Watch real-time updates of spectral fit and n,k curves")
    print("3. Updates occur every 500 evaluations")
    print("4. Click 'Stop Mock Optimization' to stop")
    print("=" * 40)

    # Run application
    return app.exec()


if __name__ == "__main__":
    exit(main())
