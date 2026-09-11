"""Unit tests for vantagecv.ue5_bridge.UE5Bridge, using requests-mock.

UE5Bridge.__init__ ALWAYS calls _verify_connection(), which makes a real
PUT to http://{host}:{port}/remote/object/call -- every test that
constructs a UE5Bridge must have that endpoint mocked first, even if the
test is about something else entirely. _verify_connection only cares
whether the request raises (RequestException) or not; it does NOT check
the response status code ("Any response (even error) means server is
alive" -- confirmed from source), so a mocked 500 response still counts
as a successful connection.
"""

import time

import pytest
import requests

from vantagecv.ue5_bridge import UE5Bridge

HOST = "127.0.0.1"
PORT = 30010
CALL_URL = f"http://{HOST}:{PORT}/remote/object/call"
PROPERTY_URL = f"http://{HOST}:{PORT}/remote/object/property"
BATCH_URL = f"http://{HOST}:{PORT}/remote/batch"
EXEC_URL = f"http://{HOST}:{PORT}/remote/exec"


@pytest.fixture
def connected_bridge(requests_mock):
    """A UE5Bridge whose constructor connection check is pre-mocked to succeed."""
    requests_mock.put(CALL_URL, json={}, status_code=200)
    return UE5Bridge(host=HOST, port=PORT)


class TestVerifyConnection:
    def test_constructor_succeeds_on_200(self, requests_mock):
        requests_mock.put(CALL_URL, json={}, status_code=200)
        bridge = UE5Bridge(host=HOST, port=PORT)
        assert bridge.host == HOST
        assert bridge.port == PORT

    def test_constructor_succeeds_even_on_error_status(self, requests_mock):
        """Confirmed from source: _verify_connection doesn't check status_code
        at all -- only whether the request raised. A 500 still "connects"."""
        requests_mock.put(CALL_URL, json={"errorMessage": "boom"}, status_code=500)
        bridge = UE5Bridge(host=HOST, port=PORT)
        assert bridge.host == HOST

    def test_constructor_raises_connection_error_on_request_exception(self, requests_mock):
        requests_mock.put(CALL_URL, exc=requests.exceptions.ConnectionError("refused"))
        with pytest.raises(ConnectionError, match="Failed to connect to UE5"):
            UE5Bridge(host=HOST, port=PORT)

    def test_default_actor_paths_set_when_not_provided(self, requests_mock):
        requests_mock.put(CALL_URL, json={}, status_code=200)
        bridge = UE5Bridge(host=HOST, port=PORT)
        assert bridge.scene_controller_path == (
            "/Game/automobile.automobile:PersistentLevel.SceneController_1"
        )
        assert bridge.data_capture_path == (
            "/Game/automobile.automobile:PersistentLevel.DataCapture_2"
        )

    def test_custom_actor_paths_are_preserved(self, requests_mock):
        requests_mock.put(CALL_URL, json={}, status_code=200)
        bridge = UE5Bridge(
            host=HOST, port=PORT,
            scene_controller_path="/custom/scene", data_capture_path="/custom/capture",
        )
        assert bridge.scene_controller_path == "/custom/scene"
        assert bridge.data_capture_path == "/custom/capture"


class TestTestConnection:
    def test_returns_true_on_success(self, connected_bridge, requests_mock):
        requests_mock.put(CALL_URL, json={}, status_code=200)
        assert connected_bridge.test_connection() is True

    def test_returns_false_on_request_exception(self, connected_bridge, requests_mock):
        requests_mock.put(CALL_URL, exc=requests.exceptions.ConnectionError("refused"))
        assert connected_bridge.test_connection() is False


class TestCallFunction:
    CALL_ENDPOINT = f"http://{HOST}:{PORT}/remote/object/call"

    def test_success_returns_json_body(self, connected_bridge, requests_mock):
        requests_mock.put(self.CALL_ENDPOINT, json={"ReturnValue": 42}, status_code=200)
        result = connected_bridge.call_function("/some/path", "SomeFunction", {"A": 1})
        assert result == {"ReturnValue": 42}

    def test_sends_exact_payload_shape(self, connected_bridge, requests_mock):
        requests_mock.put(self.CALL_ENDPOINT, json={}, status_code=200)
        connected_bridge.call_function("/some/path", "SomeFunction", {"A": 1})
        sent = requests_mock.request_history[-1].json()
        assert sent == {
            "objectPath": "/some/path",
            "functionName": "SomeFunction",
            "parameters": {"A": 1},
            "generateTransaction": False,
        }

    def test_none_parameters_becomes_empty_dict(self, connected_bridge, requests_mock):
        requests_mock.put(self.CALL_ENDPOINT, json={}, status_code=200)
        connected_bridge.call_function("/some/path", "SomeFunction")
        sent = requests_mock.request_history[-1].json()
        assert sent["parameters"] == {}

    def test_non_200_status_raises_runtime_error_with_error_message(self, connected_bridge, requests_mock):
        requests_mock.put(
            self.CALL_ENDPOINT, json={"errorMessage": "Actor not found"}, status_code=404
        )
        with pytest.raises(RuntimeError, match="Actor not found"):
            connected_bridge.call_function("/bad/path", "SomeFunction")

    def test_non_200_without_body_uses_no_response_fallback(self, connected_bridge, requests_mock):
        requests_mock.put(self.CALL_ENDPOINT, text="", status_code=500)
        with pytest.raises(RuntimeError, match="No response"):
            connected_bridge.call_function("/bad/path", "SomeFunction")

    def test_request_exception_wrapped_in_runtime_error(self, connected_bridge, requests_mock):
        requests_mock.put(self.CALL_ENDPOINT, exc=requests.exceptions.Timeout("timed out"))
        with pytest.raises(RuntimeError, match="Network error calling SomeFunction"):
            connected_bridge.call_function("/some/path", "SomeFunction")


class TestSetProperty:
    def test_success_does_not_raise(self, connected_bridge, requests_mock):
        requests_mock.put(PROPERTY_URL, json={}, status_code=200)
        connected_bridge.set_property("/some/path", "Intensity", 5.0)
        sent = requests_mock.request_history[-1].json()
        assert sent == {
            "objectPath": "/some/path",
            "propertyName": "Intensity",
            "propertyValue": 5.0,
            "generateTransaction": True,
        }

    def test_request_exception_raises_runtime_error(self, connected_bridge, requests_mock):
        requests_mock.put(PROPERTY_URL, exc=requests.exceptions.ConnectionError("refused"))
        with pytest.raises(RuntimeError, match="Failed to set Intensity"):
            connected_bridge.set_property("/some/path", "Intensity", 5.0)

    def test_non_200_status_raises_via_raise_for_status(self, connected_bridge, requests_mock):
        requests_mock.put(PROPERTY_URL, status_code=500)
        # The full message also includes requests' own HTTPError text (reason
        # phrase, URL), which is a library implementation detail, not
        # something ue5_bridge.py controls -- match only the code-controlled prefix.
        with pytest.raises(RuntimeError, match="Failed to set Intensity on /some/path"):
            connected_bridge.set_property("/some/path", "Intensity", 5.0)


class TestBatchCommands:
    def test_success_returns_json(self, connected_bridge, requests_mock):
        requests_mock.put(BATCH_URL, json={"Responses": []}, status_code=200)
        result = connected_bridge.batch_commands([{"a": 1}])
        assert result == {"Responses": []}
        sent = requests_mock.request_history[-1].json()
        assert sent == {"Requests": [{"a": 1}]}

    def test_failure_raises_runtime_error(self, connected_bridge, requests_mock):
        requests_mock.put(BATCH_URL, exc=requests.exceptions.ConnectionError("refused"))
        with pytest.raises(RuntimeError, match="Batch command execution failed"):
            connected_bridge.batch_commands([{"a": 1}])


class TestExecuteCommand:
    def test_success_returns_json(self, connected_bridge, requests_mock):
        requests_mock.post(EXEC_URL, json={"ok": True}, status_code=200)
        result = connected_bridge._execute_command("stat fps")
        assert result == {"ok": True}
        sent = requests_mock.request_history[-1].json()
        assert sent == {"Command": "stat fps"}

    def test_failure_returns_empty_dict_not_exception(self, connected_bridge, requests_mock):
        requests_mock.post(EXEC_URL, exc=requests.exceptions.ConnectionError("refused"))
        result = connected_bridge._execute_command("stat fps")
        assert result == {}


class TestHighLevelMethodsRouteThroughCallFunction:
    """Locks in the Python<->UE5 Remote Control contract: exact object_path,
    function_name, and parameters each convenience method sends.
    """

    def test_randomize_lighting(self, connected_bridge, mocker):
        mock_call = mocker.patch.object(connected_bridge, "call_function")
        connected_bridge.randomize_lighting(intensity_range=(10, 20), color_temp_range=(3000, 6500))
        mock_call.assert_called_once_with(
            connected_bridge.scene_controller_path,
            "RandomizeLighting",
            {"MinIntensity": 10, "MaxIntensity": 20, "MinTemperature": 3000, "MaxTemperature": 6500},
        )

    def test_randomize_materials_defaults_to_empty_list(self, connected_bridge, mocker):
        mock_call = mocker.patch.object(connected_bridge, "call_function")
        connected_bridge.randomize_materials()
        mock_call.assert_called_once_with(
            connected_bridge.scene_controller_path, "RandomizeMaterials", {"TargetTags": []}
        )

    def test_randomize_camera_targets_data_capture_not_scene_controller(self, connected_bridge, mocker):
        """This is the specific routing fact that made an earlier C++ dead-code
        audit finding correct: RandomizeCamera goes to data_capture_path, NOT
        scene_controller_path."""
        mock_call = mocker.patch.object(connected_bridge, "call_function")
        connected_bridge.randomize_camera(distance_range=(800, 2000), fov_range=(70, 100))
        mock_call.assert_called_once_with(
            connected_bridge.data_capture_path,
            "RandomizeCamera",
            {"MinDistance": 800, "MaxDistance": 2000, "MinFOV": 70, "MaxFOV": 100},
        )

    def test_spawn_objects_targets_scene_controller(self, connected_bridge, mocker):
        mock_call = mocker.patch.object(connected_bridge, "call_function")
        connected_bridge.spawn_objects(["cube", "sphere"], count=5)
        mock_call.assert_called_once_with(
            connected_bridge.scene_controller_path,
            "SpawnRandomObjects",
            {"NumObjects": 5, "ObjectClasses": ["cube", "sphere"]},
        )

    def test_reset_scene(self, connected_bridge, mocker):
        mock_call = mocker.patch.object(connected_bridge, "call_function")
        connected_bridge.reset_scene()
        mock_call.assert_called_once_with(connected_bridge.scene_controller_path, "ResetScene", {})


class TestSetCaptureCameraSwallowsExceptions:
    def test_success_returns_true(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", return_value={})
        assert connected_bridge.set_capture_camera(1.0, 2.0, 3.0) is True

    def test_call_function_exception_returns_false_not_raised(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", side_effect=RuntimeError("boom"))
        assert connected_bridge.set_capture_camera(1.0, 2.0, 3.0) is False


class TestCaptureFrame:
    def test_success_returns_true_from_return_value(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", return_value={"ReturnValue": True})
        assert connected_bridge.capture_frame("out.png") is True

    def test_false_return_value_propagates(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", return_value={"ReturnValue": False})
        assert connected_bridge.capture_frame("out.png") is False

    def test_exception_returns_false_not_raised(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", side_effect=RuntimeError("boom"))
        assert connected_bridge.capture_frame("out.png") is False


class TestGenerateAnnotations:
    def test_parses_json_string_return_value(self, connected_bridge, mocker):
        mocker.patch.object(
            connected_bridge, "call_function",
            return_value={"ReturnValue": '{"annotations": [{"id": 1}]}'},
        )
        before = time.time()
        result = connected_bridge.generate_annotations()
        after = time.time()
        assert result["bounding_boxes"] == [{"id": 1}]
        assert isinstance(result["timestamp"], float)
        assert before <= result["timestamp"] <= after

    def test_missing_return_value_defaults_to_empty_annotations(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", return_value={})
        result = connected_bridge.generate_annotations()
        assert result["bounding_boxes"] == []

    def test_exception_returns_empty_bounding_boxes_not_raised(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", side_effect=RuntimeError("boom"))
        before = time.time()
        result = connected_bridge.generate_annotations()
        after = time.time()
        assert result["bounding_boxes"] == []
        assert isinstance(result["timestamp"], float)
        assert before <= result["timestamp"] <= after


class TestGetActorPath:
    def test_exact_path_format(self, connected_bridge):
        connected_bridge.level_name = "automobile"
        assert connected_bridge._get_actor_path("Car_1") == (
            "/Game/automobile.automobile:PersistentLevel.Car_1"
        )


class TestSetActorVisibility:
    def test_visible_true_sends_hidden_false(self, connected_bridge, mocker):
        mock_call = mocker.patch.object(connected_bridge, "call_function")
        result = connected_bridge.set_actor_visibility("Car_1", True)
        assert result is True
        mock_call.assert_called_once_with(
            connected_bridge._get_actor_path("Car_1"),
            "SetActorHiddenInGame",
            {"bNewHidden": False},
        )

    def test_visible_false_sends_hidden_true(self, connected_bridge, mocker):
        mock_call = mocker.patch.object(connected_bridge, "call_function")
        result = connected_bridge.set_actor_visibility("Car_1", False)
        assert result is True
        mock_call.assert_called_once_with(
            connected_bridge._get_actor_path("Car_1"),
            "SetActorHiddenInGame",
            {"bNewHidden": True},
        )

    def test_call_function_exception_returns_false_not_raised(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", side_effect=RuntimeError("boom"))
        assert connected_bridge.set_actor_visibility("Car_1", True) is False


class TestSetActorTransform:
    def test_location_only_sends_exact_payload(self, connected_bridge, mocker):
        mock_call = mocker.patch.object(connected_bridge, "call_function")
        result = connected_bridge.set_actor_transform("Car_1", {"x": 1.0, "y": 2.0, "z": 3.0})
        assert result is True
        mock_call.assert_called_once_with(
            connected_bridge._get_actor_path("Car_1"),
            "K2_SetActorLocation",
            {
                "NewLocation": {"X": 1.0, "Y": 2.0, "Z": 3.0},
                "bSweep": False,
                "bTeleport": True,
            },
        )

    def test_no_rotation_means_only_one_call_function_call(self, connected_bridge, mocker):
        """rotation=None must skip K2_SetActorRotation entirely, not send a
        default-zero rotation."""
        mock_call = mocker.patch.object(connected_bridge, "call_function")
        connected_bridge.set_actor_transform("Car_1", {"x": 0, "y": 0, "z": 0})
        assert mock_call.call_count == 1

    def test_rotation_provided_sends_second_call_with_exact_payload(self, connected_bridge, mocker):
        mock_call = mocker.patch.object(connected_bridge, "call_function")
        connected_bridge.set_actor_transform(
            "Car_1", {"x": 0, "y": 0, "z": 0}, rotation={"yaw": 10.0, "pitch": 20.0, "roll": 30.0}
        )
        assert mock_call.call_count == 2
        mock_call.assert_called_with(
            connected_bridge._get_actor_path("Car_1"),
            "K2_SetActorRotation",
            {
                "NewRotation": {"Yaw": 10.0, "Pitch": 20.0, "Roll": 30.0},
                "bTeleportPhysics": True,
            },
        )

    def test_missing_location_keys_default_to_zero(self, connected_bridge, mocker):
        mock_call = mocker.patch.object(connected_bridge, "call_function")
        connected_bridge.set_actor_transform("Car_1", {})
        sent_params = mock_call.call_args[0][2]
        assert sent_params["NewLocation"] == {"X": 0, "Y": 0, "Z": 0}

    def test_call_function_exception_returns_false_not_raised(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", side_effect=RuntimeError("boom"))
        assert connected_bridge.set_actor_transform("Car_1", {"x": 0, "y": 0, "z": 0}) is False


class TestExecuteSpawnCommands:
    def test_mixed_visibility_and_transform_commands_all_succeed(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "set_actor_visibility", return_value=True)
        mocker.patch.object(connected_bridge, "set_actor_transform", return_value=True)
        commands = [
            {"type": "set_visibility", "actor_name": "Car_1", "visible": True},
            {"type": "set_transform", "actor_name": "Car_1", "location": {"x": 1, "y": 2, "z": 3}},
        ]
        count = connected_bridge.execute_spawn_commands(commands)
        assert count == 2

    def test_set_transform_receives_optional_rotation_and_scale(self, connected_bridge, mocker):
        mock_transform = mocker.patch.object(connected_bridge, "set_actor_transform", return_value=True)
        commands = [{
            "type": "set_transform", "actor_name": "Car_1",
            "location": {"x": 1, "y": 2, "z": 3},
            "rotation": {"yaw": 5}, "scale": 2.0,
        }]
        connected_bridge.execute_spawn_commands(commands)
        mock_transform.assert_called_once_with("Car_1", {"x": 1, "y": 2, "z": 3}, {"yaw": 5}, 2.0)

    def test_set_transform_defaults_rotation_none_scale_one(self, connected_bridge, mocker):
        mock_transform = mocker.patch.object(connected_bridge, "set_actor_transform", return_value=True)
        commands = [{"type": "set_transform", "actor_name": "Car_1", "location": {"x": 0, "y": 0, "z": 0}}]
        connected_bridge.execute_spawn_commands(commands)
        mock_transform.assert_called_once_with("Car_1", {"x": 0, "y": 0, "z": 0}, None, 1.0)

    def test_a_failed_command_is_not_counted_toward_success(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "set_actor_visibility", return_value=False)
        commands = [{"type": "set_visibility", "actor_name": "Car_1", "visible": True}]
        assert connected_bridge.execute_spawn_commands(commands) == 0

    def test_unknown_command_type_is_silently_skipped_not_counted(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "set_actor_visibility", return_value=True)
        commands = [{"type": "totally_unknown_type", "actor_name": "Car_1"}]
        assert connected_bridge.execute_spawn_commands(commands) == 0

    def test_exception_in_one_command_does_not_abort_the_rest(self, connected_bridge, mocker):
        """A command missing a required key (e.g. no "actor_name") raises a
        KeyError internally, caught by the broad except -- subsequent
        commands must still run."""
        mocker.patch.object(connected_bridge, "set_actor_visibility", return_value=True)
        commands = [
            {"type": "set_visibility"},  # missing actor_name/visible -> KeyError, caught
            {"type": "set_visibility", "actor_name": "Car_2", "visible": True},
        ]
        assert connected_bridge.execute_spawn_commands(commands) == 1

    def test_empty_command_list_returns_zero(self, connected_bridge):
        assert connected_bridge.execute_spawn_commands([]) == 0


class TestHideAllVehicles:
    def test_counts_successfully_hidden_actors_across_classes(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "set_actor_visibility", return_value=True)
        vehicle_actors = {"car": ["Car_1", "Car_2"], "truck": ["Truck_1"]}
        assert connected_bridge.hide_all_vehicles(vehicle_actors) == 3

    def test_failed_hides_are_not_counted(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "set_actor_visibility", return_value=False)
        vehicle_actors = {"car": ["Car_1", "Car_2"]}
        assert connected_bridge.hide_all_vehicles(vehicle_actors) == 0

    def test_empty_dict_returns_zero(self, connected_bridge):
        assert connected_bridge.hide_all_vehicles({}) == 0

    def test_calls_set_actor_visibility_false_for_every_actor(self, connected_bridge, mocker):
        mock_vis = mocker.patch.object(connected_bridge, "set_actor_visibility", return_value=True)
        connected_bridge.hide_all_vehicles({"car": ["Car_1"], "bike": ["Bike_1"]})
        mock_vis.assert_any_call("Car_1", False)
        mock_vis.assert_any_call("Bike_1", False)


class TestAuthoritativeVehicleCleanup:
    def test_no_leak_returns_hidden_and_zero_visible(self, connected_bridge, mocker):
        mocker.patch.object(
            connected_bridge, "call_function",
            side_effect=[{"ReturnValue": 5}, {"ReturnValue": 0}],
        )
        hidden, visible = connected_bridge.authoritative_vehicle_cleanup()
        assert (hidden, visible) == (5, 0)

    def test_leak_detected_returns_positive_still_visible(self, connected_bridge, mocker):
        mocker.patch.object(
            connected_bridge, "call_function",
            side_effect=[{"ReturnValue": 5}, {"ReturnValue": 2}],
        )
        hidden, visible = connected_bridge.authoritative_vehicle_cleanup()
        assert (hidden, visible) == (5, 2)

    def test_uses_default_domain_randomization_path_when_none_given(self, connected_bridge, mocker):
        mock_call = mocker.patch.object(
            connected_bridge, "call_function",
            side_effect=[{"ReturnValue": 0}, {"ReturnValue": 0}],
        )
        connected_bridge.authoritative_vehicle_cleanup()
        first_call_path = mock_call.call_args_list[0][0][0]
        assert first_call_path == "/Game/automobile.automobile:PersistentLevel.DomainRandomization_1"

    def test_custom_domain_randomization_path_is_used(self, connected_bridge, mocker):
        mock_call = mocker.patch.object(
            connected_bridge, "call_function",
            side_effect=[{"ReturnValue": 0}, {"ReturnValue": 0}],
        )
        connected_bridge.authoritative_vehicle_cleanup(domain_randomization_path="/custom/path")
        first_call_path = mock_call.call_args_list[0][0][0]
        assert first_call_path == "/custom/path"

    def test_exception_falls_back_to_zero_and_negative_one(self, connected_bridge, mocker):
        """This is the fallback that signals "cleanup status unknown" --
        distinct from (N, 0) which means "confirmed zero leaks"."""
        mocker.patch.object(connected_bridge, "call_function", side_effect=RuntimeError("boom"))
        hidden, visible = connected_bridge.authoritative_vehicle_cleanup()
        assert (hidden, visible) == (0, -1)

    def test_missing_return_value_keys_default_sensibly(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", side_effect=[{}, {}])
        hidden, visible = connected_bridge.authoritative_vehicle_cleanup()
        assert hidden == 0  # ReturnValue missing -> default 0
        assert visible == -1  # ReturnValue missing -> default -1


class TestGetActorBounds:
    def test_success_converts_half_extent_to_full_dimensions(self, connected_bridge, mocker):
        mocker.patch.object(
            connected_bridge, "call_function",
            return_value={"BoxExtent": {"X": 2.0, "Y": 1.0, "Z": 0.5}},
        )
        bounds = connected_bridge.get_actor_bounds("Car_1")
        assert bounds == {"length": 4.0, "width": 2.0, "height": 1.0}

    def test_missing_box_extent_defaults_to_zero_dimensions(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", return_value={})
        bounds = connected_bridge.get_actor_bounds("Car_1")
        assert bounds == {"length": 0, "width": 0, "height": 0}

    def test_exception_returns_none(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", side_effect=RuntimeError("boom"))
        assert connected_bridge.get_actor_bounds("Car_1") is None


class TestClose:
    def test_close_does_not_raise(self, connected_bridge):
        """close() only logs -- no connection object to actually release --
        this just confirms it's safe to call and returns None."""
        assert connected_bridge.close() is None
