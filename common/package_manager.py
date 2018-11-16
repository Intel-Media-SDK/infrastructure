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
Module for working with packages

"""

import platform
import subprocess

from enum import Enum


class OSType(Enum):
    """
    Container for os version
    """

    CENTOS = "centos"
    DEBIAN = "deb"


CMD_PATTERN = {
    "INSTALL": {
        "deb": "dpkg -y install {pkg}",
        "centos": "yum -y install {pkg}"
    },
    "UNINSTALL": {
        "deb": "aptitude -y remove {pkg}",
        "centos": "yum -y remove {pkg}"
    },
    "CHECK_INSTALLED": {
        "deb": "dpkg --list | grep {pkg}",
        "centos": "yum list installed | grep {pkg}"
    }
}


def install_pkg(pkg_path):
    """

    :param pkg_path: path to pkg to install
    :type: pathlib.Path

    :return: Flag whether pkg installed
    :rtype: bool
    """
    returncode = execute_command(get_install_cmd(pkg_path), sudo=True)
    if not returncode:
        return True
    return False


def uninstall_pkg(pkg_name):
    """

    :param pkg_name: name of pkg to uninstall
    :type: String

    :return: Flag whether pkg uninstalled
    :rtype: bool
    """
    returncode = execute_command(get_uninstall_cmd(pkg_name), sudo=True)
    if not returncode:
        return True
    return False


def is_pkg_installed(pkg_name):
    """
    Check whether pkg is installed

    :param pkg_name: pkg name
    :type: String

    :return: Flag whether pkg is installed
    :rtype: bool

    """
    cmd = CMD_PATTERN["CHECK_INSTALLED"].get(get_os_version()).format(pkg=pkg_name)
    returncode = execute_command(cmd)
    if not returncode:
        return True
    return False


def get_install_cmd(pkg_path):
    """
    Return executable cmd for install pkg

    :param pkg_path: path to pkg to install
    :type: pathlib.Path

    :return: command to install
    :rtype: String
    """
    os_version = get_os_version()
    cmd = ""
    if os_version:
        cmd = CMD_PATTERN["INSTALL"].get(os_version).format(pkg=pkg_path)

    return cmd


def get_uninstall_cmd(pkg_name):
    """
    Return executable cmd for uninstall pkg

    :param pkg_name: pkg name
    :type: String

    :return: command to uninstall
    :rtype: String
    """
    os_version = get_os_version()
    cmd = ""
    if os_version:
        cmd = CMD_PATTERN["UNINSTALL"].get(os_version).format(pkg=pkg_name)

    return cmd


def get_os_version():
    """
    Check OS version and return it

    :return: OS version | None if it is not defined
    """

    plt = platform.platform()
    for item in OSType:
        if item.value in plt:
            return item.value
    return None


def execute_command(cmd, sudo=False):
    """
    Run the command

    :param cmd: comand to execute
    :type: String

    :param sudo: flag if execute with root privileges
    :type: bool

    :return: subprocess returncode
    :rtype: Integer
    """
    prefix = "sudo" if sudo else ""
    timeout = 300
    process = subprocess.run(f"{prefix} {cmd}",
                             shell=True,
                             timeout=timeout,
                             encoding='utf-8',
                             errors='backslashreplace')
    return process.returncode
