import logging
from pathlib import Path
from typing import Any
from yarl import URL
import requests
from requests.auth import HTTPBasicAuth


class OwncloudClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.owncloud_config: dict[str, Any] = config
        self.logger = logging.getLogger("grandma_gcn.owncloud")

    @property
    def username(self) -> str:
        if "username" not in self.owncloud_config:
            raise ValueError("Username not found in ownCloud configuration.")
        return self.owncloud_config.get("username")

    @property
    def password(self) -> str:
        if "password" not in self.owncloud_config:
            raise ValueError("Password not found in ownCloud configuration.")
        return self.owncloud_config.get("password")

    @property
    def base_url(self) -> str:
        if "base_url" not in self.owncloud_config:
            raise ValueError("Base URL not found in ownCloud configuration.")
        return URL(self.owncloud_config.get("base_url"))

    def mkdir(self, folder_path: str) -> URL:
        """
        Create a new directory in ownCloud.

        Parameters
        ----------
        folder_path : str
            The path of the directory to create, relative to the base URL.

        Returns
        -------
        URL
            The URL of the created directory.

        Raises
        ------
        Exception
            If the directory creation fails.
        """
        folder_path = self.base_url / folder_path
        response = requests.request(
            method="MKCOL",
            url=folder_path,
            auth=HTTPBasicAuth(self.username, self.password),
        )
        if response.status_code not in (201, 204):
            raise Exception(f"Failed to create directory: {response.status_code}")

        self.logger.info(f"Directory {folder_path} created successfully.")
        return folder_path

    def put_data(self, data: bytes, url: URL, owncloud_filename: str) -> URL:
        """
        Upload data to ownCloud.

        Parameters
        ----------
        data : bytes
            The data to upload.
        url : URL
            The URL of the directory in ownCloud where the file will be uploaded.
        owncloud_filename : str
            The name of the file in ownCloud.

        Returns
        -------
        URL
            The URL of the uploaded file in ownCloud.

        Raises
        ------
        Exception
            If the file upload fails.
        """
        url_file = url / owncloud_filename
        response = requests.put(
            url_file,
            data=data,
            auth=HTTPBasicAuth(self.username, self.password),
        )
        if response.status_code not in (201, 204):
            raise Exception(f"Failed to upload file: {response.status_code}")

        self.logger.info(
            f"File {owncloud_filename} uploaded successfully to {url_file}"
        )
        return url_file

    def put_file(self, file_path: Path, url: URL, owncloud_filename: str) -> URL:
        """
        Upload a file to ownCloud.

        Parameters
        ----------
        file_path : Path
            The local path of the file to upload.
        url : URL
            The URL of the directory in ownCloud where the file will be uploaded.
        owncloud_filename : str
            The name of the file in ownCloud.

        Returns
        -------
        URL
            The URL of the uploaded file in ownCloud.
        """
        with open(file_path, "rb") as f:
            data = f.read()
        return self.put_data(data, url, owncloud_filename)

    def get_url_subpart(self, url: URL, nb_part: int) -> str:
        """
        Get a subpart of the URL.

        Parameters
        ----------
        url : URL
            The URL to get the subpart from.
        nb_part : int
            The number of parts to return from the URL.

        Returns
        -------
        str
            The subpart of the URL.
        """
        if nb_part < 1:
            return ""
        segments = url.parts
        return "/".join(segments[-nb_part:]) if nb_part <= len(segments) else str(url)
