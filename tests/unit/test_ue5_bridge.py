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
        result = connected_bridge.generate_annotations()
        assert result["bounding_boxes"] == [{"id": 1}]
        assert "timestamp" in result

    def test_missing_return_value_defaults_to_empty_annotations(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", return_value={})
        result = connected_bridge.generate_annotations()
        assert result["bounding_boxes"] == []

    def test_exception_returns_empty_bounding_boxes_not_raised(self, connected_bridge, mocker):
        mocker.patch.object(connected_bridge, "call_function", side_effect=RuntimeError("boom"))
        result = connected_bridge.generate_annotations()
        assert result["bounding_boxes"] == []
        assert "timestamp" in result
