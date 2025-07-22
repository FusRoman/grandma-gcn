import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from grandma_gcn.worker.gwemopt_worker import gwemopt_post_task


def test_gwemopt_post_task_merges_and_cleans(monkeypatch):
    # Prepare fake results: (output_path, (ascii_path, owncloud_url_folder))
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()
        ascii_file1 = output_dir / "tiles1.txt"
        ascii_file2 = output_dir / "tiles2.txt"
        ascii_file1.write_text("content1")
        ascii_file2.write_text("content2")
        owncloud_url = "https://owncloud.example.com/fake/obs_strategy_folder"
        results = [
            (str(output_dir), (str(ascii_file1), owncloud_url)),
            (str(output_dir), (str(ascii_file2), owncloud_url)),
        ]
        owncloud_config = {
            "username": "user",
            "password": "pass",
            "base_url": "https://owncloud.example.com",
        }
        path_log = tmpdir

        # Patch merge_galaxy_file and OwncloudClient
        merge_galaxy_file_called = {}

        def fake_merge_galaxy_file(
            owncloud_config, obs_strategy_owncloud_url_folder, ascii_file_path
        ):
            merge_galaxy_file_called["called"] = True
            merge_galaxy_file_called["ascii_file_path"] = ascii_file_path
            merge_galaxy_file_called["obs_strategy_owncloud_url_folder"] = (
                obs_strategy_owncloud_url_folder
            )

        monkeypatch.setattr(
            "grandma_gcn.worker.gwemopt_worker.merge_galaxy_file",
            fake_merge_galaxy_file,
        )

        # Patch setup_task_logger to avoid file logging
        monkeypatch.setattr(
            "grandma_gcn.worker.gwemopt_worker.setup_task_logger",
            lambda *a, **k: (MagicMock(), Path(tmpdir) / "log.txt"),
        )

        # Patch shutil.rmtree to track calls
        removed_dirs = []
        rmtree_call_count = {"count": 0}

        def fake_rmtree(d, *args, **kwargs):
            removed_dirs.append(str(d))
            rmtree_call_count["count"] += 1

        monkeypatch.setattr("shutil.rmtree", fake_rmtree)

        # Patch URL.parent to just return the same string for simplicity
        class DummyURL(str):
            @property
            def parent(self):
                return self

        monkeypatch.setattr(
            "grandma_gcn.worker.gwemopt_worker.URL", lambda s: DummyURL(s)
        )

        # Patch open to avoid real file IO for log
        monkeypatch.setattr(
            "builtins.open",
            lambda *a, **k: MagicMock(
                __enter__=lambda s: s,
                __exit__=lambda s, exc_type, exc_val, exc_tb: None,
            ),
        )

        # Patch current_task.request.id
        monkeypatch.setattr(
            "grandma_gcn.worker.gwemopt_worker.current_task",
            MagicMock(request=MagicMock(id="testid")),
        )

        # Run the task
        gwemopt_post_task(results, owncloud_config, path_log)

        # Check that merge_galaxy_file was called with both ascii files
        assert merge_galaxy_file_called["called"]
        assert set(merge_galaxy_file_called["ascii_file_path"]) == {
            str(ascii_file1),
            str(ascii_file2),
        }
        # Check that output_dir was removed
        assert str(output_dir) in removed_dirs
        # Check the number of calls to shutil.rmtree (should be 2, one per result tuple)
        assert rmtree_call_count["count"] == 2
