from sofia.neuro.connectome import (
    CircuitCompetition, SparseAssociativeMemory, selected_circuits,
)


def test_selected_circuits_are_provenance_linked_and_non_authoritative():
    circuits = selected_circuits()
    assert {item.circuit_id for item in circuits} == {
        "central-complex-action-selection", "salience-competition",
        "mushroom-body-association", "central-complex-orientation",
    }
    assert all(item.source_url.startswith("https://doi.org/") for item in circuits)
    assert all(item.simplifications for item in circuits)


def test_competition_is_bounded_stable_and_explainable():
    model = CircuitCompetition()
    first = model.run({"talk": 0.9, "fault": 0.7, "reflection": 0.3})
    second = model.run({"talk": 0.9, "fault": 0.7, "reflection": 0.3})
    assert first == second
    assert first.winner == "talk"
    assert all(0 <= value <= 1 for _, value in first.activations)


def test_association_never_bypasses_mem_eligibility_and_is_resettable():
    model = SparseAssociativeMemory()
    model.reinforce(
        features=("event:docker", "host:artemis"), memory_id="memory:private",
        reinforcement_ref="evidence:reviewed-1", amount=0.08,
    )
    assert model.candidates(
        features=("event:docker", "host:artemis"), eligible=lambda _id: False,
    ) == ()
    allowed = model.candidates(
        features=("event:docker", "host:artemis"), eligible=lambda _id: True,
    )
    assert allowed[0].memory_id == "memory:private"
    assert allowed[0].reinforcement_refs == ("evidence:reviewed-1",)
    assert model.export()["algorithm"] == "mushroom-association-v0.1"
    model.reset()
    assert model.candidates(
        features=("event:docker",), eligible=lambda _id: True,
    ) == ()
