from pathlib import Path
import pytest
from unittest import mock
from yarl import URL
from grandma_gcn.worker.owncloud_client import OwncloudClient


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


def test_owncloud_put_file_success(owncloud_client: OwncloudClient):
    mock_file = mock.MagicMock()
    mock_file.read.return_value = b"test content"
    mock_open = mock.MagicMock(return_value=mock_file)
    mock_file.__enter__.return_value = mock_file

    with mock.patch("grandma_gcn.worker.owncloud_client.open", mock_open, create=True):
        with mock.patch("requests.put") as mock_request:
            mock_response = mock.Mock()
            mock_response.status_code = 201
            mock_request.return_value = mock_response

            url = owncloud_client.put_file(
                Path("fake_file.txt"),
                URL("https://owncloud.example.com/folder/"),
                "owncloud_filename.txt",
            )

            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args

            result_url = URL(
                "https://owncloud.example.com/folder/owncloud_filename.txt"
            )
            assert args[0] == result_url
            assert kwargs["data"] == b"test content"
            assert url == result_url


def test_owncloud_put_file_failure(owncloud_client: OwncloudClient):

    mock_file = mock.MagicMock()
    mock_file.read.return_value = b"test content"
    mock_open = mock.MagicMock(return_value=mock_file)
    mock_file.__enter__.return_value = mock_file

    with mock.patch("grandma_gcn.worker.owncloud_client.open", mock_open, create=True):
        with mock.patch("requests.put") as mock_request:
            mock_response = mock.Mock()
            mock_response.status_code = 400
            mock_request.return_value = mock_response
            with pytest.raises(Exception, match="Failed to upload file"):
                owncloud_client.put_file(
                    Path("fake_failed_path/file.txt"),
                    URL("https://owncloud.example.com/folder/"),
                    "owncloud_filename.txt",
                )


def test_owncloud_put_file_url_type(owncloud_client: OwncloudClient):

    mock_file = mock.MagicMock()
    mock_file.read.return_value = b"test content"
    mock_open = mock.MagicMock(return_value=mock_file)
    mock_file.__enter__.return_value = mock_file

    with mock.patch("grandma_gcn.worker.owncloud_client.open", mock_open, create=True):
        with mock.patch("requests.put") as mock_request:
            mock_response = mock.Mock()
            mock_response.status_code = 201
            mock_request.return_value = mock_response
            owncloud_client.put_file(
                Path("fake_file.txt"),
                URL("https://owncloud.example.com/folder/"),
                "owncloud_filename.txt",
            )
            called_url = mock_request.call_args[0][0]
            assert isinstance(called_url, URL)


def test_get_url_subpart_basic(owncloud_client: OwncloudClient):
    url = URL("https://owncloud.example.com/folder/subfolder/file.txt")
    result = owncloud_client.get_url_subpart(url, 2)
    assert result == "subfolder/file.txt"


def test_get_url_subpart_full_url_if_too_many_parts(owncloud_client: OwncloudClient):
    url = URL("https://owncloud.example.com/folder/subfolder/file.txt")
    result = owncloud_client.get_url_subpart(url, 10)
    assert result == str(url)


def test_get_url_subpart_one_part(owncloud_client: OwncloudClient):
    url = URL("https://owncloud.example.com/folder/subfolder/file.txt")
    result = owncloud_client.get_url_subpart(url, 1)
    assert result == "file.txt"


def test_get_url_subpart_zero_part(owncloud_client: OwncloudClient):
    url = URL("https://owncloud.example.com/folder/subfolder/file.txt")
    result = owncloud_client.get_url_subpart(url, 0)
    assert result == ""


def test_get_url_subpart_exact_parts(owncloud_client: OwncloudClient):
    url = URL("https://owncloud.example.com/folder/subfolder/file.txt")
    result = owncloud_client.get_url_subpart(url, len(url.parts))
    assert result == "/".join(url.parts)
