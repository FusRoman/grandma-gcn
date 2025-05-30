import pytest
from unittest import mock
from yarl import URL
from grandma_gcn.worker.owncloud_client import OwncloudClient


@pytest.fixture
def owncloud_config():
    return {
        "OWNCLOUD": {
            "base_url": "https://owncloud.example.com",
            "username": "test_user",
            "password": "test_password",
        }
    }


@pytest.fixture
def owncloud_client(owncloud_config):
    return OwncloudClient(owncloud_config)


def test_owncloud_client_properties(owncloud_client):
    assert owncloud_client.username == "test_user"
    assert owncloud_client.password == "test_password"
    assert owncloud_client.base_url == URL("https://owncloud.example.com")


def test_owncloud_client_missing_config():
    client = OwncloudClient({})
    with pytest.raises(ValueError):
        _ = client.username


def test_owncloud_makedir_success(owncloud_client: OwncloudClient):
    with mock.patch("requests.request") as mock_request:
        mock_response = mock.Mock()
        mock_response.status_code = 201
        mock_request.return_value = mock_response
        url_folder = owncloud_client.mkdir("test_dir/")
        mock_request.assert_called_once()
        _, kwargs = mock_request.call_args
        assert kwargs["method"] == "MKCOL"

        result_url_folder = URL("https://owncloud.example.com/test_dir/")
        assert kwargs["url"] == result_url_folder
        assert url_folder == result_url_folder


def test_owncloud_makedir_failure(owncloud_client: OwncloudClient):
    with mock.patch("requests.request") as mock_request:
        mock_response = mock.Mock()
        mock_response.status_code = 400
        mock_request.return_value = mock_response
        with pytest.raises(Exception, match="Failed to create directory"):
            owncloud_client.mkdir("fail_dir/")


def test_owncloud_makedir_url_type(owncloud_client: OwncloudClient):
    with mock.patch("requests.request") as mock_request:
        mock_response = mock.Mock()
        mock_response.status_code = 201
        mock_request.return_value = mock_response
        owncloud_client.mkdir("another_dir/")
        called_url = mock_request.call_args[1]["url"]
        assert isinstance(called_url, URL)
