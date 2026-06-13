from CERTUS_HUB import HUB_APP_CATALOG


def test_hub_catalog_declares_module_categories_and_contracts():
    for item in HUB_APP_CATALOG:
        assert item.get("script")
        assert item.get("category") in {"core_workflow", "materials_specialized", "support_tool"}
        assert item.get("contract") in {"scientific_workflow", "material_workflow", "utility_tool", "substrate_utility"}


def test_hub_substrate_tool_is_not_marked_as_core_workflow():
    substrate_items = [item for item in HUB_APP_CATALOG if item.get("script") == "certus_substrate_index.py"]
    assert substrate_items
    item = substrate_items[0]
    assert item.get("category") == "support_tool"
    assert item.get("contract") == "substrate_utility"
