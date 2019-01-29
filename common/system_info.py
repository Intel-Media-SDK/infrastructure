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


class LinuxDistr(Enum):
    """
    Container for supported Linux distributions
    """

    CENTOS = "centos"
    DEBIAN = "ubuntu"


PACK_TYPES = {
    LinuxDistr.CENTOS.value: 'rpm',
    LinuxDistr.DEBIAN.value: 'deb'
}


def get_pkg_type():
    """
    Return the type of package depending on OS

    :return: pack extension
    :rtype: String
    """
    pkg_type = PACK_TYPES.get(get_os_name())
    if pkg_type:
        return pkg_type
    raise UnsupportedOsError(f'No supported Package type for platform "{get_os_name()}"')


def get_os_type():
    """
    Return OS type: Windows, Linux

    :return: OS type
    """

    return platform.system()


def os_type_is_windows():
    return get_os_type() == OsType.WINDOWS.value


def os_type_is_linux():
    return get_os_type() == OsType.LINUX.value


def get_os_name():
    """
    Check OS version and return it

    :return: OS name | Exception if it is not supported
    """

    if os_type_is_linux():
        plt = distro.linux_distribution()[0]
        for item in LinuxDistr:
            if item.value in plt.lower():
                return item.value
        raise UnsupportedOsError(f'The platform {plt} is not currently supported')
    elif os_type_is_windows():
        return OsType.WINDOWS.value
    raise UnsupportedOsError(f'OS type {get_os_type()} is not  currently supported')


def get_linux_distr_version():
    """
    Get Linux distribution version

    :return: major version, minor version
    """
    if os_type_is_linux():
        return distro.major_version(), distro.minor_version()
    raise UnsupportedOsError(f'The platform is not Linux')
