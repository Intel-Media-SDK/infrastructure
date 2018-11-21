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
Module for working with Linux rpm and deb packages

"""

import logging
from common.system_info import get_os_name
from common.helper import cmd_exec
from common.logger_conf import configure_logger


_CMD_PATTERN = {
    "INSTALL": {
        "deb": "sudo dpkg -y install {pkg_path}",
        "centos": "sudo yum -y install {pkg_path}"
    },
    "UNINSTALL": {
        "deb": "sudo aptitude -y remove {pkg_name}",
        "centos": "sudo yum -y remove {pkg_name}"
    },
    "CHECK_INSTALLED": {
        "deb": "dpkg --list | grep {pkg_name}",
        "centos": "yum list installed | grep {pkg_name}"
    }
}


def install_pkg(pkg_path, pkg_name):
    """

    :param pkg_path: path to pkg to install
    :type: pathlib.Path

    :return: Flag whether pkg installed
    :rtype: bool
    """
    configure_logger('package_manager.install_pkg')
    log = logging.getLogger()

    if not uninstall_pkg(pkg_name):
        return False
    cmd = _CMD_PATTERN["INSTALL"].get(get_os_name()).format(pkg_path=pkg_path)
    err, out = cmd_exec(cmd)

    if not err:
        log.debug(out)
        return True

    log.info(out)
    return False


def uninstall_pkg(pkg_name):
    """

    :param pkg_name: name of pkg to uninstall
    :type: String

    :return: Flag whether pkg uninstalled
    :rtype: bool
    """

    if not is_pkg_installed(pkg_name):
        return True

    configure_logger('package_manager.uninstall_pkg')
    log = logging.getLogger()
    cmd = _CMD_PATTERN["UNINSTALL"].get(get_os_name()).format(pkg_name=pkg_name)
    err, out = cmd_exec(cmd)

    if not err:
        log.debug(out)
        return True

    log.info(out)
    return False


def is_pkg_installed(pkg_name):
    """
    Check whether pkg is installed

    :param pkg_name: pkg name
    :type: String

    :return: Flag whether pkg is installed
    :rtype: bool

    """

    configure_logger('package_manager.is_pkg_installed')
    log = logging.getLogger()
    cmd = _CMD_PATTERN["CHECK_INSTALLED"].get(get_os_name()).format(pkg_name=pkg_name)
    err, out = cmd_exec(cmd)

    if not err:
        log.debug(out)
        return True

    log.info(out)
    return False
