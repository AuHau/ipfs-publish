import inspect
import pathlib
import shutil
import subprocess

import git
import ipfsapi
import pytest

from publish import publishing, exceptions, PUBLISH_IGNORE_FILENAME
from .. import factories

IGNORE_FILE_TEST_SET = (
    ('*.a', ('some.a', 'a', 'folder/b.a'), 1, 0),
    ('**/*.b', ('b', 'some.b', 'folder/b', 'folder/some.b', 'some/other/folder/some.b'), 3, 0),
    ('/another_file', (), NotImplementedError, 0),
    ('some_dir', ('some_dir/file',), 0, 1),
    ('non_existing_file', (), 0, 0),
)
"""
/../../outside_file
non_existing_file"""


class TestRepo:
    def test_publish_repo_basic(self, mocker):
        mocker.patch.object(git.Repo, 'clone_from')
        mocker.patch.object(shutil, 'rmtree')

        ipfs_client_mock = mocker.Mock(spec=ipfsapi.Client)
        ipfs_client_mock.add.return_value = [{'Hash': 'some-hash'}]

        mocker.patch.object(ipfsapi, 'connect')
        ipfsapi.connect.return_value = ipfs_client_mock

        repo: publishing.GenericRepo = factories.RepoFactory()
        repo.publish_repo()

        ipfs_client_mock.add.assert_called_once_with(mocker.ANY, recursive=True, pin=True)
        ipfs_client_mock.pin_rm.assert_not_called()
        assert repo.last_ipfs_addr == '/ipfs/some-hash/'

    def test_publish_repo_bins(self, mocker):
        mocker.patch.object(git.Repo, 'clone_from')
        mocker.patch.object(shutil, 'rmtree')

        ipfs_client_mock = mocker.Mock(spec=ipfsapi.Client)
        ipfs_client_mock.add.return_value = [{'Hash': 'some-hash'}]

        mocker.patch.object(ipfsapi, 'connect')
        ipfsapi.connect.return_value = ipfs_client_mock

        mocker.patch.object(subprocess, 'run')
        subprocess.run.return_value = subprocess.CompletedProcess(None, 0)

        repo: publishing.GenericRepo = factories.RepoFactory(build_bin='some_cmd', after_publish_bin='some_other_cmd')
        repo.publish_repo()

        assert subprocess.run.call_count == 2
        subprocess.run.assert_called_with(f'some_other_cmd /ipfs/some-hash/', shell=True, capture_output=True)
        subprocess.run.assert_any_call(f'some_cmd ', shell=True, capture_output=True)

    def test_publish_repo_bins_fails(self, mocker):
        mocker.patch.object(git.Repo, 'clone_from')
        mocker.patch.object(shutil, 'rmtree')

        ipfs_client_mock = mocker.Mock(spec=ipfsapi.Client)
        ipfs_client_mock.add.return_value = [{'Hash': 'some-hash'}]

        mocker.patch.object(ipfsapi, 'connect')
        ipfsapi.connect.return_value = ipfs_client_mock

        mocker.patch.object(subprocess, 'run')
        subprocess.run.return_value = subprocess.CompletedProcess(None, 1)

        repo: publishing.GenericRepo = factories.RepoFactory(build_bin='some_cmd', after_publish_bin='some_other_cmd')

        with pytest.raises(exceptions.RepoException):
            repo.publish_repo()

    def test_publish_rm_old_pin(self, mocker):
        mocker.patch.object(git.Repo, 'clone_from')
        mocker.patch.object(shutil, 'rmtree')

        ipfs_client_mock = mocker.Mock(spec=ipfsapi.Client)
        ipfs_client_mock.add.return_value = [{'Hash': 'some-hash'}]

        mocker.patch.object(ipfsapi, 'connect')
        ipfsapi.connect.return_value = ipfs_client_mock

        repo: publishing.GenericRepo = factories.RepoFactory(last_ipfs_addr='some_hash')
        repo.publish_repo()

        ipfs_client_mock.pin_rm.assert_called_once_with('some_hash')

    @pytest.mark.parametrize(('glob', 'paths_to_make', 'expected_unlink', 'expected_rmtree'), IGNORE_FILE_TEST_SET)
    def test_remove_ignored_files(self, glob, paths_to_make, expected_unlink, expected_rmtree, tmp_path: pathlib.Path, mocker):
        mocker.spy(pathlib.Path, 'unlink')
        mocker.spy(shutil, 'rmtree')

        (tmp_path / PUBLISH_IGNORE_FILENAME).write_text(glob)

        (tmp_path / '.git').mkdir()

        for path in paths_to_make:
            path = tmp_path / path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

        if inspect.isclass(expected_unlink) and issubclass(expected_unlink, Exception):
            with pytest.raises(expected_unlink):
                repo: publishing.GenericRepo = factories.RepoFactory()
                repo._remove_ignored_files(tmp_path)
        else:
            repo: publishing.GenericRepo = factories.RepoFactory()
            repo._remove_ignored_files(tmp_path)

            # -1 because the method removes the ignore file on its own
            assert pathlib.Path.unlink.call_count - 1 == expected_unlink

            # =1 because of removing .git folder
            assert shutil.rmtree.call_count - 1 == expected_rmtree
