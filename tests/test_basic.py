def test_import():
    import connects_common_connectivity as ccc
    assert ccc.__version__


def test_model_generation():
    import connects_common_connectivity as ccc
    models = ccc.generate_pydantic_models()
    assert "BrainRegion" in models
    BrainRegion = models["BrainRegion"]
    # Root region without parent (parent_identifier now optional)
    br = BrainRegion(id="X", name="Some Region")
    assert br.id == "X"


def test_required_field_enforcement():
    import pytest
    import connects_common_connectivity as ccc
    models = ccc.generate_pydantic_models()
    DataItem = models["DataItem"]
    # dataset is required; omitting should raise a validation error
    with pytest.raises(Exception):
        DataItem(id="D1", name="Item 1")


def test_enum_validation():
    import pytest
    import connects_common_connectivity as ccc
    models = ccc.generate_pydantic_models()
    Modality = models["Modality"]  # Enum
    assert Modality.TRACER.name == "TRACER"
    DataSet = models["DataSet"]
    ds = DataSet(id="DS1", name="Dataset 1", modality=Modality.TRACER, project_id="P1")
    # Depending on dynamic generation, modality may be stored as enum value or raw string
    assert str(ds.modality) in {Modality.TRACER.value, Modality.TRACER.name, str(Modality.TRACER)}
    # Invalid modality should raise error now that slot has enum range
    with pytest.raises(Exception):
        DataSet(id="DS2", name="Dataset 2", modality="NOT_A_VALID_MODALITY", project_id="P1")


def test_multivalued_slot_list_type():
    import connects_common_connectivity as ccc
    models = ccc.generate_pydantic_models()
    BrainRegion = models["BrainRegion"]
    # parent_identifier and descendants store ids (strings), not inlined objects
    parent = BrainRegion(id="BRP", name="Parent")
    child = BrainRegion(id="BRC", name="Child", parent_identifier="BRP")
    parent2 = BrainRegion(id="BRX", name="Parent2", parent_identifier="BRP", descendants=["BRC"])
    assert isinstance(parent2.descendants, list)


def test_probability_bounds_and_pattern():
    import pytest
    import connects_common_connectivity as ccc
    models = ccc.generate_pydantic_models()
    MappingSet = models["MappingSet"]
    CellToCellMapping = models["CellToCellMapping"]
    DataSet = models["DataSet"]
    DataItem = models["DataItem"]
    ds = DataSet(id="DS1", name="Dataset", modality=models["Modality"].TRACER, project_id="P1")
    cell1 = DataItem(id="C1", name="Cell1", project_id="P1")
    cell2 = DataItem(id="C2", name="Cell2", project_id="P1")
    ms = MappingSet(id="MS1", name="Map1", method_name="Method", source_dataset="DS1", target_dataset="DS1", project_id="P1")
    # Valid probability; object refs stored as ids
    mapping = CellToCellMapping(id="M1", mapping_set="MS1", source_cell="C1", target_cell="C2", probability=0.5, project_id="P1")
    assert 0 <= mapping.probability <= 1
    # Invalid probability > 1
    with pytest.raises(Exception):
        CellToCellMapping(id="M2", mapping_set="MS1", source_cell="C1", target_cell="C2", probability=1.5, project_id="P1")

