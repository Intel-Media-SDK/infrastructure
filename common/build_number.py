"""
Module for getting and updating information
about build numbers for weekly validations.
"""

import json
import logging
import pathlib


def get_build_number(repo_path, os_type, branch):
    """
        Get build number from file in repository
        :param repo_path: path to repository with "build_numbers.json" file
        :type repo_path: String | pathlib.Path
        :param os_type: OS type. Need for finding certain build number
        :type os_type: String
        :param branch: Name of branch. Need for finding certain build number
        :type branch: String

        :return: Build number
        :rtype: Integer
    """

    log = logging.getLogger('build_number.get_build_number')

    build_number = 0
    file_name = 'build_numbers.json'
    build_numbers_path = pathlib.Path(repo_path) / file_name

    if build_numbers_path.exists():
        with build_numbers_path.open() as numbers_file:
            numbers = json.load(numbers_file)
            if os_type in numbers:
                if branch in numbers[os_type]:
                    build_number = numbers[os_type][branch]
                else:
                    log.warning(f'Branch {branch} does not exist')
            else:
                log.warning(f'OS {os_type} does not exist')
    else:
        log.warning(f'{file_name} does not exist')

    log.info(f'Returned build number: {build_number}')
    return build_number

# TODO: add function for updating build number in repository
