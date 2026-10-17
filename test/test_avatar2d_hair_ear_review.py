"""Hair/ear registration boxes remain deterministic and non-production."""
from sofia.avatar.vtuber_hair_ear_review import candidate_boxes


def test_fox_ear_registration_uses_independent_sides_and_valid_canvas_bounds():
    boxes = candidate_boxes()
    assert set(boxes) == {
        "hair_back_main.png", "hair_front_bangs.png",
        "ear_pose_01.png", "ear_pose_06.png",
    }
    for x, y, width, height in boxes.values():
        assert 0 <= x < 2048 and 0 <= y < 2560
        assert 0 < width <= 2048 - x
        assert 0 < height <= 2560 - y
    left_x, _, left_width, _ = boxes["ear_pose_01.png"]
    right_x, _, _, _ = boxes["ear_pose_06.png"]
    assert left_x + left_width < right_x


def test_candidate_geometry_changes_cannot_modify_module_constants():
    boxes = candidate_boxes()
    boxes["hair_back_main.png"] = (1, 2, 3, 4)
    assert candidate_boxes()["hair_back_main.png"] != (1, 2, 3, 4)
