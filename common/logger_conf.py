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
Logging configuration function.
Using:
    if there are no arguments - configure stream handler for logger root
"""

import sys
import logging


def configure_logger(logger_name='root', logs_path=None):
    """
        Preparing logger

        :param logger_name: Name of logger
        :type logger_name: String
        :param logs_path: Path to log file
        :type logs_path: pathlib.Path

        :return: None
    """

    if logger_name == 'root':
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
    else:
        logger = logging.getLogger(logger_name)

    formatter = logging.Formatter('[%(asctime)s] %(name)s %(levelname)s: %(message)s')

    if not logger.hasHandlers():
        stream_handler = logging.StreamHandler(stream=sys.stdout)
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    if logs_path:
        logs_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(logs_path)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
