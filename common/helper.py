# Copyright (c) 2017 Intel Corporation
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
Common functions for build runner
"""
import logging
import os
import pathlib
import shutil
import stat
import tarfile
import subprocess
from enum import Enum
from shutil import copystat, Error, copy2
from zipfile import ZipFile, ZIP_DEFLATED
import json


class UnsupportedArchiveError(Exception):
    """
    Exception using for unsupported extension of archive
    in function 'extract_archive'
    """

    pass


class ErrorCode(Enum):
    """
    Container for custom error codes
    """

    CRITICAL = 1


class TestReturnCodes(Enum):
    """
    Container for tests return codes
    """

    SUCCESS = 0
    TEST_FAILED = 1
    INFRASTRUCTURE_ERROR = 2


class Stage(Enum):
    """
    Constants for defining stage of build
    """

    CLEAN = "clean"
    EXTRACT = "extract"
    BUILD = "build"
    INSTALL = "install"
    PACK = "pack"
    COPY = "copy"


class Product_type(Enum):
    """
    Constants for defining type of product
    """

    # closed
    CLOSED_WINDOWS = 'closed_windows'
    CLOSED_WINDOWS_HW_LIB = 'closed_windows_hw_lib'
    CLOSED_WINDOWS_TOOLS = 'closed_windows_tools'
    CLOSED_WINDOWS_SW_LIB = 'closed_windows_sw_lib'
    CLOSED_WINDOWS_MFTS = 'closed_windows_mfts'
    CLOSED_WINDOWS_UWP = 'closed_windows_uwp'
    CLOSED_LINUX = 'closed_linux'
    CLOSED_LINUX_OPEN_SOURCE = 'closed_linux_open_source'
    CLOSED_EMBEDDED = 'closed_embedded'
    CLOSED_ANDROID = 'closed_android'

    # Product configuration for this product type is the same as for PRIVATE_ANDROID
    # The duplicate is needed for getting correct link for build artifacts, because
    # builds in private and closed source buildbots with the same product type has the same links
    CLOSED_ANDROID_OPEN_SOURCE = 'closed_android_open_source'

    CLOSED_WINDOWS_TITAN = 'closed_windows_titan'

    # private
    PRIVATE_ANDROID = 'private_android'
    PRIVATE_LINUX_NEXT_GEN = 'private_linux_next_gen'
    PRIVATE_LINUX_NEXT_GEN_API_NEXT = 'private_linux_next_gen_api_next'

    # public
    PUBLIC_LINUX = 'public_linux'
    PUBLIC_LINUX_CLANG = 'public_linux_clang_6.0'
    PUBLIC_LINUX_GCC_LATEST = 'public_linux_gcc_8.2'
    PUBLIC_LINUX_API_NEXT = 'public_linux_api_next'

    # DEFCONFIG means that "enabled all" is not set and
    # build environment doesn't include X11 and Wayland
    PUBLIC_LINUX_API_NEXT_DEFCONFIG = 'public_linux_api_next_defconfig'

    PUBLIC_LINUX_FASTBOOT = 'public_linux_fastboot'
    PUBLIC_LINUX_FASTBOOT_GCC_LATEST = 'public_linux_fastboot_gcc_8.2'


class Build_type(Enum):
    """
    Constants for defining type of build
    """

    RELEASE = 'release'
    DEBUG = 'debug'


class Build_event(Enum):
    """
    Constants for defining type of build event
    """

    PRE_COMMIT = 'pre_commit'
    COMMIT = 'commit'
    NIGHTLY = 'nightly'
    WEEKLY = 'weekly'
    KLOCWORK = 'klocwork'
    CUSTOM_BUILD = 'custom_build'


def make_archive(path, data_to_archive):
    """
    Create archive with certain data

    :param path: Path to archive file (ex: /home/user/archive.tar)
    :type path: pathlib.Path

    :param data_to_archive: list of dirs/files for archiving
    Example:
        data_to_archive = [
            {
                'from_path': '/home/mediasdk/openSource/build_scripts/root_dir/repos/MediaSDK/__cmake/intel64.make.release',
                'relative': [
                    {
                        'path': '__bin',
                        'pack_as': 'bin'
                    },
                    {
                        'path': '__lib',
                        'pack_as': 'lib'
                    }
                ]
            },
            {
                'from_path': '/home/mediasdk/openSource/build_scripts/root_dir/repos/MediaSDK',
                'relative': [
                    {
                        'path': 'tests'
                    },
                    {
                        'path': 'CMakeLists.txt'
                    },
                ]
            }
        ]
    :type data_to_archive: List

    :return: None
    """

    no_errors = True

    log = logging.getLogger('helper.make_archive')

    log.info('-' * 50)
    log.info('create archive %s', path)

    if path.suffix == '.tar':
        pkg = tarfile.open(path, "w")
    elif path.suffix == '.gz':
        pkg = tarfile.open(path, "w:gz", compresslevel=6)
    elif path.suffix == '.bz2':
        pkg = tarfile.open(path, "w:bz2")
    elif path.suffix == '.zip':
        pkg = ZipFile(path, 'w', compression=ZIP_DEFLATED)
    else:
        log.error("Extension %s is not supported", path.suffix)
        no_errors = False

    for info in data_to_archive:
        for relative in info['relative']:
            path_to_archive = info['from_path'] / relative['path']
            pack_as = pathlib.Path(relative.get('pack_as', relative['path']))

            log.info('add to archive %s, pack as "%s"', path_to_archive, pack_as)
            try:
                if path.suffix in ('.tar', '.gz'):
                    pkg.add(path_to_archive, arcname=pack_as)
                elif path.suffix == '.zip':
                    _zip_data(path_to_archive, pack_as, pkg)
            except:
                log.exception("Can not pack results")
                no_errors = False

    pkg.close()

    return no_errors


def _zip_data(root_path, pack_as, archive):
    """
    Create zip archive from files and directories

    :param root_path: Path to file or directory
    :type root_path: pathlib.Path

    :param pack_as: Path to file or directory in archive
    :type pack_as: pathlib.Path

    :param archive: Class of archive
    :type archive: tarfile|ZipFile

    :return: None
    """

    if root_path.is_dir():
        for sub_path in root_path.iterdir():
            arc_name = pack_as / sub_path.relative_to(root_path)
            if not sub_path.is_dir():
                archive.write(sub_path, arcname=arc_name)
            else:
                _zip_data(root_path / sub_path, arc_name, archive)
    else:
        archive.write(root_path, arcname=pack_as)


def extract_archive(archive_path, extract_to):
    """
    Extract archive (.tar, .zip)

    :param archive_path: Path to archive
    :type archive_path: String|pathlib.Path

    :param extract_to: Path to extraction
    :type extract_to: String|pathlib.Path
    """

    archive_path = pathlib.Path(archive_path)
    extract_to = pathlib.Path(extract_to)

    if archive_path.suffix == '.tar':
        package = tarfile.open(str(archive_path), 'r')
    elif archive_path.suffix == '.gz':
        package = tarfile.open(str(archive_path), 'r:gz')
    elif archive_path.suffix == '.zip':
        package = ZipFile(str(archive_path))
    else:
        raise UnsupportedArchiveError(
            f"Unsupported archive extension {archive_path.suffix}")

    package.extractall(extract_to)
    package.close()


# shutil.copytree function with extension
# TODO merge with copytree from test scripts
def copytree(src, dst, symlinks=False, ignore=None, copy_function=copy2,
             ignore_dangling_symlinks=False):
    """Recursively copy a directory tree.

    The destination directory must not already exist.
    If exception(s) occur, an Error is raised with a list of reasons.

    If the optional symlinks flag is true, symbolic links in the
    source tree result in symbolic links in the destination tree; if
    it is false, the contents of the files pointed to by symbolic
    links are copied. If the file pointed by the symlink doesn't
    exist, an exception will be added in the list of errors raised in
    an Error exception at the end of the copy process.

    You can set the optional ignore_dangling_symlinks flag to true if you
    want to silence this exception. Notice that this has no effect on
    platforms that don't support os.symlink.

    The optional ignore argument is a callable. If given, it
    is called with the `src` parameter, which is the directory
    being visited by copytree(), and `names` which is the list of
    `src` contents, as returned by os.listdir():

        callable(src, names) -> ignored_names

    Since copytree() is called recursively, the callable will be
    called once for each directory that is copied. It returns a
    list of names relative to the `src` directory that should
    not be copied.

    The optional copy_function argument is a callable that will be used
    to copy each file. It will be called with the source path and the
    destination path as arguments. By default, copy2() is used, but any
    function that supports the same signature (like copy()) can be used.

    """
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    # Add "exist_ok" in case of copying to existing directory
    os.makedirs(dst, exist_ok=True)
    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if os.path.islink(srcname):
                linkto = os.readlink(srcname)
                if symlinks:
                    # We can't just leave it to `copy_function` because legacy
                    # code with a custom `copy_function` may rely on copytree
                    # doing the right thing.
                    os.symlink(linkto, dstname)
                    copystat(srcname, dstname, follow_symlinks=not symlinks)
                else:
                    # ignore dangling symlink if the flag is on
                    if not os.path.exists(linkto) and ignore_dangling_symlinks:
                        continue
                    # otherwise let the copy occurs. copy2 will raise an error
                    if os.path.isdir(srcname):
                        copytree(srcname, dstname, symlinks, ignore,
                                 copy_function)
                    else:
                        copy_function(srcname, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, ignore, copy_function)
            else:
                # Will raise a SpecialFileError for unsupported file types
                copy_function(srcname, dstname)
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error as err:
            errors.extend(err.args[0])
        except OSError as why:
            errors.append((srcname, dstname, str(why)))
    try:
        copystat(src, dst)
    except OSError as why:
        # Copying file access times may fail on Windows
        if getattr(why, 'winerror', None) is None:
            errors.append((src, dst, str(why)))
    if errors:
        raise Error(errors)
    return dst


# TODO refactor hard code
def copy_win_files(repos_dir, build_dir):
    """
    Copy binaries of Windows build.
    Uses in windows config files

    :param repos_dir: Path to repositories directory
    :type repos_dir: pathlib.Path

    :param build_dir: Path to build directory
    :type build_dir: pathlib.Path

    :return: None | Exception
    """

    ignore_files = shutil.ignore_patterns('*.ipdb', '*.map', '*.list', '*obj*', '*.*log', '*.exp',
                                          '*.bsc', 'mfx_pipeline.lib', 'mfx_trans_pipeline.lib', r'amd64', r'x86')

    win_thm32_bin = repos_dir / 'build\\win_thm32'
    win_thm64_bin = repos_dir / 'build\\win_thm64'
    win_intel64_bin = repos_dir / 'build\\win_intel64'
    win_win32_bin = repos_dir / 'build\\win_Win32'
    win_x64_bin = repos_dir / 'build\\win_x64'
    lib_samples32 = repos_dir / 'mdp_msdk-lib\\samples\\_build\\Win32'
    lib_samples64 = repos_dir / 'mdp_msdk-lib\\samples\\_build\\x64'
    mfts_samples32 = repos_dir / 'mdp_msdk-mfts\\samples\\_build\\Win32'
    mfts_samples64 = repos_dir / 'mdp_msdk-mfts\\samples\\_build\\x64'

    if win_win32_bin.exists():
        copytree(win_win32_bin,
                 build_dir / 'win_Win32',
                 ignore=ignore_files)

    if win_x64_bin.exists():
        copytree(win_x64_bin,
                 build_dir / 'win_x64',
                 ignore=ignore_files)

    if win_thm32_bin.exists():
        copytree(win_thm32_bin,
                 build_dir / 'win_thm32',
                 ignore=ignore_files)

    if win_thm64_bin.exists():
        copytree(win_thm64_bin,
                 build_dir / 'win_thm64',
                 ignore=ignore_files)

    if win_intel64_bin.exists():
        copytree(win_intel64_bin,
                 build_dir / 'win_intel64',
                 ignore=ignore_files)

    if lib_samples32.exists():
        copytree(lib_samples32,
                 build_dir / 'samples' / 'Win32',
                 ignore=ignore_files)

    if lib_samples64.exists():
        copytree(lib_samples64,
                 build_dir / 'samples' / 'x64',
                 ignore=ignore_files)

    if mfts_samples32.exists():
        copytree(mfts_samples32,
                 build_dir / 'mfts_samples' / 'Win32',
                 ignore=ignore_files)

    if mfts_samples64.exists():
        copytree(mfts_samples64,
                 build_dir / 'mfts_samples' / 'x64',
                 ignore=ignore_files)


def _remove_directory(path):
    """
    Removes directory: different from shutil.rmtree() in following aspects:
    * if file or directory does not have write permission - tries to set this permission
       before attempt to delete.
    If there were exceptions during removing tree, first exception occured is raised again

    @param path: directory to remove
    @type path: C{string}

    """
    caught_exception = None
    try:
        this_dir, child_dirs, files = next(os.walk(path))
    except StopIteration:
        raise OSError(2, 'Path does not exist', path)
    for childDir in child_dirs:
        try:
            path_to_remove = os.path.join(this_dir, childDir)
            if os.path.islink(path_to_remove):
                os.unlink(path_to_remove)
            else:
                remove_directory(path_to_remove)
        except Exception as e:
            if not caught_exception:
                caught_exception = e
    for f in files:
        file_path = os.path.join(this_dir, f)
        try:
            os.unlink(file_path)
        except:
            try:
                if not os.access(file_path, os.W_OK) and not os.path.islink(file_path):
                    os.chmod(file_path, stat.S_IWRITE)
                os.unlink(file_path)
            except Exception as e:
                if not caught_exception:
                    caught_exception = e
    try:
        os.rmdir(this_dir)
    except:
        try:
            if not os.access(this_dir, os.W_OK):
                os.chmod(this_dir, stat.S_IWRITE)
            os.rmdir(this_dir)
        except Exception as e:
            if not caught_exception:
                caught_exception = e

    if caught_exception:
        raise caught_exception


if os.name == 'nt':
    def remove_directory(path):
        try:
            return _remove_directory(path)
        except WindowsError as err:
            # err == 206 - Path too long. Try unicode version of the function
            # err == 123 - The filename, directory name, or volume label syntax is incorrect. Try unicode version of the function
            # err == 3   - The system cannot find the path specified
            if err in [3, 206, 123] and (not isinstance(path, str) or not path.startswith(u'\\\\?\\')):
                return _remove_directory(u'\\\\?\\' + os.path.abspath(str(path, errors='ignore')))
            raise
else:
    remove_directory = _remove_directory


def rotate_dir(directory: pathlib.Path) -> bool:
    """
    Renames directory if exists:
    dir -> dir_1
    """

    log = logging.getLogger('helper.rotate_dir')

    dir_parent = directory.parent
    dir_name = directory.name

    if directory.exists():
        redirs = [redir.name for redir in dir_parent.iterdir()
                  if redir.name.startswith(dir_name)]
        duplicate = dir_parent / f'{dir_name}_{len(redirs)}'

        log.info("Move previous directory to %s", duplicate)

        directory.rename(duplicate)
        return True

    return False


def update_json(check_type, success, output, json_path):
    new_data = {
        check_type: {
            "success": success,
            "message": output
        }
    }

    path = pathlib.Path(json_path)
    # Create full path until the file (if not exist)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            data.update(new_data)

            with open(path, "w") as f:
                json.dump(data, f, indent=4, sort_keys=True)
        except Exception:
            return False
    else:
        with open(path, "w") as f:
            json.dump(new_data, f, indent=4, sort_keys=True)
    return True


def cmd_exec(cmd, env=None, cwd=None, shell=True, log=None, verbose=True):
    if log:
        if verbose:
            log_out = log.info
        else:
            log_out = log.debug

        if isinstance(cmd, list):
            log_out(f'cmd: {subprocess.list2cmdline(cmd)}')
        else:
            log_out(f'cmd: {cmd}')

        if not cwd:
            cwd = str(pathlib.Path.cwd())
            log_out(f'working directory: {cwd}')

        if env:
            log_out(f'environment: {env}')

    try:
        completed_process = subprocess.run(cmd,
                                           shell=shell,
                                           env=env,
                                           cwd=cwd,
                                           check=True,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT,
                                           encoding='utf-8',
                                           errors='backslashreplace')

        return completed_process.returncode, completed_process.stdout
    except subprocess.CalledProcessError as failed_process:
        return failed_process.returncode, failed_process.stdout
