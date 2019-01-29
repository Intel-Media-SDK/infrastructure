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
Information about system

"""

import platform
import distro
from enum import Enum


class UnsupportedOsError(Exception):
    """
    Exception for unsupported OS name
    """

    pass


class OsType(Enum):
    """
    Container for supported os types
    """
    WINDOWS = 'Windows'
    LINUX = 'Linux'


PACK_TYPES = {
    'centos': 'rpm',
    'ubuntu': 'deb'
}


def get_pkg_type():
    """
    Return the type of package depending on OS

    :return: pack extension
    :rtype: String
    """
    plt = get_os_name()
    if plt in PACK_TYPES:
        return PACK_TYPES[plt]
    raise UnsupportedOsError(f'No supported Package type for platform "{plt}"')


def os_type_is_windows():
    return platform.system() == OsType.WINDOWS.value


def os_type_is_linux():
    return platform.system() == OsType.LINUX.value


def get_os_name():
    """
    Check OS version and return it

    :return: OS name | Exception if it is not supported
    """

    if os_type_is_linux():
        return distro.id()
    elif os_type_is_windows():
        return OsType.WINDOWS.value
    raise UnsupportedOsError(f'OS type {platform.system()} is not  currently supported')


def get_os_version():
    if os_type_is_linux():
        return distro.major_version(), distro.minor_version()
    raise UnsupportedOsError(f'The platform is not Linux')
