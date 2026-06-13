import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock

from certus.utils.certus_export import (
    _export_series_label,
    _export_y_values_for_item,
    build_wide_dataframe_for_export,
    iter_plot_data_series,
)

class MockPlotItem:
    def __init__(self, name=None, opts=None):
        self.name_val = name
        self.opts = opts if opts else {}
    
    def name(self):
        return self.name_val

def test_export_series_label():
    item1 = MockPlotItem(name="Curve A")
    assert _export_series_label(item1, 0) == "Curve A"
    
    item2 = MockPlotItem(opts={"name": "Curve B"})
    assert _export_series_label(item2, 1) == "Curve B"
    
    item3 = MagicMock()
    del item3.name
    item3.objectName.return_value = "Curve C"
    assert _export_series_label(item3, 2) == "Curve C"
    
    item4 = MagicMock(spec=[])
    del item4.name # No name methods
    assert _export_series_label(item4, 3) == "Series 4"

def test_export_y_values_for_item():
    item1 = MagicMock()
    item1._certus_export_y_as_exp_k = False
    y = np.array([1.0, 2.0, np.nan])
    y_out = _export_y_values_for_item(item1, y)
    assert np.array_equal(y_out[:2], np.array([1.0, 2.0]))
    
    item2 = MagicMock()
    item2._certus_export_y_as_exp_k = True
    y2 = np.array([0.0, 1.0, 750.0]) # 750 should be clipped to 700
    y_out2 = _export_y_values_for_item(item2, y2)
    assert np.isclose(y_out2[0], 1.0) # exp(0)
    assert np.isclose(y_out2[1], np.exp(1.0))
    assert np.isclose(y_out2[2], np.exp(700.0))

def test_build_wide_dataframe_for_export():
    series = [
        ("A", np.array([1, 2]), np.array([0.1, 0.2])),
        ("B", np.array([1, 2, 3]), np.array([0.5, 0.6, 0.7])),
        ("A", np.array([4]), np.array([0.9])) # Duplicate name
    ]
    df = build_wide_dataframe_for_export(series)
    assert df is not None
    assert "A_x" in df.columns
    assert "A_y" in df.columns
    assert "B_x" in df.columns
    assert "B_y" in df.columns
    assert "A_2_x" in df.columns
    assert "A_2_y" in df.columns
    
    # Check padding (max length is 3)
    assert len(df) == 3
    assert np.isnan(df["A_x"].iloc[2])
    assert np.isnan(df["A_2_x"].iloc[1])

def test_build_wide_dataframe_empty():
    assert build_wide_dataframe_for_export([]) is None

def test_iter_plot_data_series_empty():
    assert iter_plot_data_series(None) == []
    mock_plot = MagicMock()
    mock_plot.listDataItems.return_value = []
    assert iter_plot_data_series(mock_plot) == []

def test_iter_plot_data_series_valid_data():
    mock_plot = MagicMock()
    
    # Create a mock PlotDataItem with getData
    mock_item = MagicMock()
    del mock_item.name
    del mock_item._certus_export_y_as_exp_k
    mock_item.opts = {"name": "Test1"}
    mock_item.getData.return_value = (np.array([1, 2]), np.array([0.1, 0.2]))
    
    mock_plot.listDataItems.return_value = [mock_item]
    
    res = iter_plot_data_series(mock_plot)
    assert len(res) == 1
    assert res[0][0] == "Test1"
    assert np.array_equal(res[0][1], [1, 2])
    assert np.array_equal(res[0][2], [0.1, 0.2])

