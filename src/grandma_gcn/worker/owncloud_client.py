import logging
from pathlib import Path
from typing import Any
from yarl import URL
import requests
from requests.auth import HTTPBasicAuth


class OwncloudClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.logger = logging.getLogger("grandma_gcn.owncloud")

    @property
    def owncloud_config(self) -> dict[str, Any]:
        owncloud_config = self.config.get("OWNCLOUD")
        if not owncloud_config:
            raise ValueError(
                "OWNCLOUD configuration not found in the config.toml. Please add a [OWNCLOUD] section with the following keys: 'base_url', 'username', 'password'."
            )
        return owncloud_config

    @property
    def username(self) -> str:
        return self.owncloud_config.get("username")

    @property
    def password(self) -> str:
        return self.owncloud_config.get("password")

    @property
    def base_url(self) -> str:
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

    def put_file(self, file_path: Path, url: URL, owncloud_filename: str) -> None:
        """
        Upload a file to ownCloud.

        Parameters
        ----------
        file_path : Path
            The local path of the file to upload.
        url : URL
            The url of the directory in ownCloud where the file will be uploaded.
        owncloud_filename : str
            The name of the file in ownCloud.

        Raises
        ------
        Exception
            If the file upload fails.
        """
        url_file = url / owncloud_filename
        with open(file_path, "rb") as f:
            data = f.read()

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
