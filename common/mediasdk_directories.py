# Copyright (c) 2018 Intel Corporation
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Module contains static directories and links
which uses in build runner
"""
import os
import pathlib
import platform
from urllib.parse import quote, urljoin

try:
    from static_closed_data import PROXIES, SHARE_PATHS, REPOSITORIES, PRODUCT_CONFIGS_REPO, \
        OPEN_SOURCE_INFRASTRUCTURE_REPO, CLOSED_SOURCE_INFRASTRUCTURE_REPO
except:
    from static_public_data import SHARE_PATHS, REPOSITORIES
    PROXIES = {}
    PRODUCT_CONFIGS_REPO = ''
    OPEN_SOURCE_INFRASTRUCTURE_REPO = ''
    CLOSED_SOURCE_INFRASTRUCTURE_REPO = ''

LOGICAL_DRIVE = 3  # Drive type from MSDN


class OsType:
    windows = 'Windows'
    linux = 'Linux'


# closed
class Proxy:
    # This proxy will be set
    _proxies = PROXIES

    # Temp for existing proxies in environment
    _exist_proxies = {}

    @classmethod
    def get_proxy(cls):
        print(cls._proxies)

    @classmethod
    def set_proxy(cls):
        """If proxies already exist, save them and set proxy from _proxies"""
        for proxy_name, url in cls._proxies.items():
            exist_proxy = os.environ.get(proxy_name)
            if exist_proxy:
                cls._exist_proxies[proxy_name] = exist_proxy
            os.environ[proxy_name] = url

    @classmethod
    def unset_proxy(cls):
        """Unset proxy from _proxies and set saved proxies"""
        for proxy_name in cls._proxies:
            del os.environ[proxy_name]

        for proxy_name, url in cls._exist_proxies.items():
            os.environ[proxy_name] = url

    @classmethod
    def with_proxies(cls, func):
        """
        Check 'proxy' argument in called function and set proxy if it == True
        To use as decorator, add in definition of function 'proxy' argument
        """

        def wrapper(*args, **kwargs):
            if kwargs.get('proxy'):
                cls.set_proxy()
                func(*args, **kwargs)
                cls.unset_proxy()
            else:
                func(*args, **kwargs)

        return wrapper


def get_logical_drives():
    """
    Return list of logical drives in Windows only.
    """
    import wmi

    drives = wmi.WMI().Win32_LogicalDisk(DriveType=LOGICAL_DRIVE)
    return (drive.Caption for drive in drives)


def find_folder_on_disks(folder):
    """
    Trying to find folder on all logical drives.
    Works in Windows only.
    """
    for drive in get_logical_drives():
        root_dir = os.path.join(drive, folder)
        if os.path.isdir(root_dir):
            return root_dir


class MediaSdkDirectories(object):

    """
    Container for static links
    """
    """Base class for all MediaSDK dirs errors"""

    _share_paths = SHARE_PATHS
    _repositories = REPOSITORIES

    _closed_root_url = r'http://bb.msdk.intel.com'
    _public_root_url = r'http://mediasdk.intel.com'

    _public_tests_root_url = urljoin(_public_root_url, 'tests')
    _public_builds_root_url = urljoin(_public_root_url, 'builds')

    _closed_tests_root_url = urljoin(_closed_root_url, 'closed_tests')
    _closed_builds_root_url = urljoin(_closed_root_url, 'closed_builds')

    _private_tests_root_url = urljoin(_closed_root_url, 'private_tests')
    _private_builds_root_url = urljoin(_closed_root_url, 'private_builds')

    _next_gen_tests_root_url = urljoin(_closed_root_url, 'next_gen_tests')
    _next_gen_builds_root_url = urljoin(_closed_root_url, 'next_gen_builds')

    if platform.system() == OsType.windows:
        _tests_root_path = _share_paths['test_windows']
        _builds_root_path = _share_paths['build_windows']
        _mgen = r'\\nnlmdpfls02.inn.intel.com\tools\mgen_run2\mgen.exe'

        _mediasdk_root = os.environ.get('MEDIASDK_ROOT')
        if not _mediasdk_root or not os.path.exists(_mediasdk_root):
            _mediasdk_root = find_folder_on_disks('MEDIASDK_ROOT')

        _mediasdk_streams = os.environ.get('MEDIASDK_STREAMS')
        if not _mediasdk_streams or not os.path.exists(_mediasdk_streams):
            _mediasdk_streams = find_folder_on_disks('MEDIASDK_STREAMS')
    elif platform.system() == OsType.linux:
        _tests_root_path = _share_paths['test_linux']
        _builds_root_path = _share_paths['build_linux']
        _mgen = r'/media/nnlmdpfls02/lab_msdk/mgen_run2/mgen'
        _mediasdk_root = r'/msdk/MEDIASDK_ROOT'
        _mediasdk_streams = r'/msdk/MEDIASDK_STREAMS'
    else:
        raise OSError('Unknown os type %s' % platform.system())

    @property
    def product_configs_repo(self):
        return PRODUCT_CONFIGS_REPO

    @property
    def open_source_infrastructure_repo(self):
        return OPEN_SOURCE_INFRASTRUCTURE_REPO

    @property
    def closed_source_infrastructure_repo(self):
        return CLOSED_SOURCE_INFRASTRUCTURE_REPO




    @classmethod
    def get_root_builds_dir(cls, os_type=None):
        """
        Get root path to artifacts of build

        :param os_type: Type of os (Windows|Linux)
        :type os_type: String

        :return: root path to artifacts of build
        :rtype: String
        """

        if os_type is None:
            return pathlib.Path(cls._builds_root_path)
        elif os_type == OsType.windows:
            return pathlib.PureWindowsPath(cls._share_paths['build_windows'])
        elif os_type == OsType.linux:
            return pathlib.PurePosixPath(cls._share_paths['build_linux'])
        raise OSError('Unknown os type %s' % os_type)

    @classmethod
    def get_commit_dir(cls, branch, build_event, commit_id, os_type=None):
        """
        Get path to artifacts of builds on all OSes

        :param branch: Branch of repo
        :type branch: String

        :param build_event: Event of build (pre_commit|commit|nightly|weekly)
        :type build_event: String

        :param commit_id: SHA sum of commit
        :type commit_id: String

        :param os_type: Type of os (Windows|Linux)
        :type os_type: String

        :return: Path to artifacts of build
        :rtype: String
        """

        # only for Gerrit
        # ex: refs/changes/25/52345/1 -> 52345/1
        if branch.startswith('refs/changes/'):
            branch = branch.split('/', 3)[-1]

        return cls.get_root_builds_dir(os_type) / branch / build_event / commit_id

    @classmethod
    def get_build_dir(cls, branch, build_event, commit_id, product_type, build_type, os_type=None):
        """
        Get path to artifacts of build

        :param branch: Branch of repo
        :type branch: String

        :param build_event: Event of build (pre_commit|commit|nightly|weekly)
        :type build_event: String

        :param commit_id: SHA sum of commit
        :type commit_id: String

        :param product_type: Type of product (linux|windows|embedded|pre_si)
        :type product_type: String

        :param build_type: Type of build (release|debug)
        :type build_type: String

        :param os_type: Type of os (Windows|Linux)
        :type os_type: String

        :return: Path to artifacts of build
        :rtype: String
        """

        return cls.get_commit_dir(branch, build_event, commit_id, os_type) / f'{product_type}_{build_type}'

    @classmethod
    def get_build_root_url(cls, product_type):
        """
        Get root url to artifacts of build

        :param product_type: Type of product (linux|android|embedded_private)
        :type product_type: String

        :return: Root url to artifacts of build
        :rtype: String
        """

        if product_type.startswith("private_linux_next_gen_"):
            return cls._next_gen_builds_root_url
        elif product_type.startswith("private_"):
            return cls._private_builds_root_url
        elif product_type.startswith("public_"):
            return cls._public_builds_root_url
        else:
            return cls._closed_builds_root_url

    @classmethod
    def get_build_url(cls, branch, build_event, commit_id, product_type, build_type):
        """
        Get url to artifacts of build

        :param branch: Branch of repo
        :type branch: String

        :param build_event: Event of build (pre_commit|commit|nightly|weekly)
        :type build_event: String

        :param commit_id: SHA sum of commit
        :type commit_id: String

        :param product_type: Type of product (linux|windows|embedded|pre_si)
        :type product_type: String

        :param build_type: Type of build (release|debug)
        :type build_type: String

        :param os_type: Type of os (Windows|Linux)
        :type os_type: String

        :return: URL to artifacts of build
        :rtype: String
        """

        # only for Gerrit
        # ex: refs/changes/25/52345/1 -> 52345/1
        if branch.startswith('refs/changes/'):
            branch = branch.split('/', 3)[-1]

        return '/'.join(
            (cls.get_build_root_url(product_type), branch, build_event, commit_id, f'{product_type}_{build_type}'))

    @classmethod
    def get_root_test_results_dir(cls, os_type=None):
        """
        Get root path to test results

        :param os_type: Type of os (Windows|Linux)
        :type os_type: String

        :return: root path to artifacts of build
        :rtype: String
        """
        if os_type is None:
            return pathlib.Path(cls._tests_root_path)
        elif os_type == OsType.windows:
            return pathlib.PureWindowsPath(cls._share_paths['test_windows'])
        elif os_type == OsType.linux:
            return pathlib.PurePosixPath(cls._share_paths['test_linux'])
        raise OSError('Unknown os type %s' % os_type)

    @classmethod
    def get_test_dir(cls, branch, build_event, commit_id, build_type, test_platform=None, product_type=None, os_type=None):
        """
        Get path to test results on all OSes

        :param branch: Branch of repo
        :type branch: String

        :param build_event: Event of build (pre_commit|commit|nightly|weekly)
        :type build_event: String

        :param commit_id: SHA sum of commit
        :type commit_id: String

        :param os_type: Type of os (Windows|Linux)
        :type os_type: String

        :param build_type: Type of build (release|debug)
        :type build_type: String

        :param test_platform: Acronym of test platform (w10rs3_skl_64_d3d11|c7.3_skl_64_server)
        :type test_platform: String

        :param product_type: Type of product (linux|windows|embedded|pre_si)
        :type product_type: String

        :return: Path to test result
        :rtype: String

        NOTE: All tests for commit will be stored together to generate one summary.
        """

        # only for Gerrit
        # ex: refs/changes/25/52345/1 -> 52345/1
        if branch.startswith('refs/changes/'):
            branch = branch.split('/', 3)[-1]

        tests_dir = cls.get_root_test_results_dir(os_type) / branch / build_event / commit_id
        if test_platform:
            return tests_dir / build_type / test_platform
        else:
            return tests_dir / f'{product_type}_{build_type}'

    @classmethod
    def get_test_root_url(cls, product_type):
        """
        Get root url to artifacts of build

        :param product_type: Type of product (linux|android|embedded_private)
        :type product_type: String

        :return: Root url to artifacts of build
        :rtype: String
        """

        if product_type.startswith("private_linux_next_gen_"):
            return cls._next_gen_builds_root_url
        elif product_type.startswith("private_"):
            return cls._private_builds_root_url
        elif product_type.startswith("public_"):
            return cls._public_builds_root_url
        else:
            return cls._closed_builds_root_url

    @classmethod
    def get_test_url(cls, branch, build_event, commit_id, build_type, product_type, test_platform=None):
        """
        Get URL to test results

        :param branch: Branch of repo
        :type branch: String

        :param build_event: Event of build (pre_commit|commit|nightly|weekly)
        :type build_event: String

        :param commit_id: SHA sum of commit
        :type commit_id: String

        :param os_type: Type of os (Windows|Linux)
        :type os_type: String

        :param build_type: Type of build (release|debug)
        :type build_type: String

        :param product_type: Type of product (linux|windows|embedded|pre_si)
        :type product_type: String

        :param test_platform: Acronym of test platform (w10rs3_skl_64_d3d11|c7.3_skl_64_server)
        :type test_platform: String

        :return: URL to test result
        :rtype: String

        NOTE: All tests for commit will be stored together to generate one summary.
        """

        # only for Gerrit
        # ex: refs/changes/25/52345/1 -> 52345/1
        if branch.startswith('refs/changes/'):
            branch = branch.split('/', 3)[-1]

        test_url = '/'.join((cls.get_test_root_url(product_type), branch, build_event, commit_id))
        if test_platform:
            return '/'.join((test_url, build_type, test_platform))
        else:
            return '/'.join((test_url, f'{product_type}_{build_type}'))

    @classmethod
    def get_repo_url_by_name(cls, name='MediaSDK'):
        """
        Get url of certain repository

        :param name: Repository name
        :type name: String

        :return: Url of repository if found
        :rtype: String|None
        """

        return cls._repositories.get(name, None)

    @classmethod
    def get_mgen(cls):
        return cls._mgen

    @classmethod
    def get_mediasdk_root(cls):
        folder = cls._mediasdk_root
        if not folder:
            raise MediaSDKFolderNotFound(folder)
        return folder

    @classmethod
    def get_mediasdk_streams(cls):
        folder = cls._mediasdk_streams
        if not folder:
            raise MediaSDKFolderNotFound(folder)
        return folder

    @classmethod
    def get_repo_url_by_name_w_credentials(cls, name, login, password):
        creds = '//{}:{}@'.format(quote(login), quote(password))
        return cls._repositories.get(name, '').replace('//', creds, 1)


class MediaSDKException(Exception):
    """Base class for all MediaSDK dirs errors"""
    pass


class MediaSDKFolderNotFound(MediaSDKException):
    """Raise if MediaSDK folder not found"""
    pass
