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
import os
import sys
import tarfile
import pathlib
import logging
from logging.config import dictConfig
from zipfile import ZipFile
import shutil
from shutil import copystat, Error, copy2

from .logger_conf import LOG_CONFIG


class UnsupportedArchiveError(Exception):
    """
    Exception using for unsupported extension of archive
    in function 'extract_archive'
    """

    pass


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

    log = logging.getLogger()

    log.info('-' * 50)
    log.info('create archive %s', path)

    if path.suffix == '.tar':
        pkg = tarfile.open(path, "w")
    elif path.suffix == '.gz':
        pkg = tarfile.open(path, "w:gz")
    elif path.suffix == '.zip':
        pkg = ZipFile(path, 'w')
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
                set_output_stream('err')
                log.exception("Can not pack results")
                set_output_stream()
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


def set_log_file(log_path):
    """
    Set file path for logging

    :param log_path: Path to log file
    :type log_path pathlib.Path

    :return: None
    """

    log_dir = log_path.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    LOG_CONFIG['handlers']['file_handler']['filename'] = str(log_path)
    dictConfig(LOG_CONFIG)


def set_output_stream(stream='out'):
    """
    Set output stream of logging

    :param stream: Type of stream (out|err)
    :type stream: String

    :return: None
    """

    if stream == 'out':
        LOG_CONFIG['handlers']['stream_handler']['stream'] = sys.stdout
    elif stream == 'err':
        LOG_CONFIG['handlers']['stream_handler']['stream'] = sys.stderr
    else:
        pass
    dictConfig(LOG_CONFIG)


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
        package = tarfile.open(archive_path, 'r')
    elif archive_path.suffix == '.gz':
        package = tarfile.open(archive_path, 'r:gz')
    elif archive_path.suffix == '.zip':
        package = ZipFile(archive_path)
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

    ignore_files = shutil.ignore_patterns('*.pdb', '*.map', '*.list', '*.obj', '*.*log', '*.exp',
                                          '*.bsc', 'mfx_pipeline.lib', 'mfx_trans_pipeline.lib')

    win_thm32_bin = repos_dir / 'build\\win_thm32\\bin'
    win_win32_bin = repos_dir / 'build\\win_Win32\\bin'
    win_x64_bin = repos_dir / 'build\\win_x64\\bin'
    lib_samples_release = repos_dir / 'mdp_msdk-lib\\samples\\_build\\x64\\Release'
    mfts_samples_release_int = repos_dir / 'mdp_msdk-mfts\\samples\\_build\\x64\\Release_Internal'
    mfts_samples_release = repos_dir / 'mdp_msdk-mfts\\samples\\_build\\x64\\Release'
    mfts_samples_release_thm = repos_dir / 'mdp_msdk-mfts\\samples\\_build\\Win32\\Release_THM'

    if win_thm32_bin.exists():
        copytree(win_thm32_bin,
                 build_dir / 'win_thm32' / 'bin',
                 ignore=ignore_files)

    if win_win32_bin.exists():
        copytree(win_win32_bin,
                 build_dir / 'win_Win32' / 'bin',
                 ignore=ignore_files)

    if win_x64_bin.exists():
        copytree(win_x64_bin,
                 build_dir / 'win_x64' / 'bin',
                 ignore=ignore_files)

    if lib_samples_release.exists():
        copytree(lib_samples_release,
                 build_dir / 'win_x64' / 'bin',
                 ignore=ignore_files)

    if mfts_samples_release_int.exists():
        copytree(mfts_samples_release_int,
                 build_dir / 'win_x64' / 'Release_Internal',
                 ignore=ignore_files)

    if mfts_samples_release.exists():
        copytree(mfts_samples_release,
                 build_dir / 'win_x64' / 'Release',
                 ignore=ignore_files)

    if mfts_samples_release_thm.exists():
        copytree(mfts_samples_release_thm,
                 build_dir / 'win_Win32' / 'Release_THM',
                 ignore=ignore_files)
