"""
Module for getting and updating information
about build numbers for weekly validations.
"""

import json
import logging
import pathlib

from common.helper import cmd_exec, remove_directory
from common.extract_repo import extract_repo


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

    log.info(f'Getting build number from {repo_path} repository')
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
        log.warning(f'{build_numbers_path} does not exist')

    log.info(f'Returned build number: {build_number}')
    return build_number


def increase_build_number(origin_repo_path, os_type, branch):
    """
        Increase build number by 1 in remote repository, if it is the same for local and remote repositories
        This condition needed to avoid increasing build number while rebuilds
        Function extracts mdp_msdk-product-configs repo in following layout to push change to remote repository

        ../tmp/mdp_msdk-product-configs
        ../origin_repo_path

        :param origin_repo_path: path to local repository with "build_numbers.json" file
        :type origin_repo_path: String | pathlib.Path
        :param os_type: OS type. Need for finding certain build number
        :type os_type: String
        :param branch: Name of branch. Need for finding certain build number
        :type branch: String
    """

    log = logging.getLogger('build_number.increase_build_number')

    build_numbers_file = 'build_numbers.json'

    log.info(f'Get build number from local repository')
    origin_build_number = get_build_number(repo_path=pathlib.Path(origin_repo_path),
                                           os_type=os_type, branch=branch)
    if origin_build_number == 0:
        log.error(f'Build number should be not 0'
                  f'Maybe {pathlib.Path(origin_repo_path) / build_numbers_file} do not contains {branch} branch for {os_type} platform')
        return False

    temporary_dir = pathlib.Path(origin_repo_path) / '..' / 'tmp'
    temporary_repo_path = temporary_dir / 'mdp_msdk-product-configs'
    temporary_build_number_path = temporary_repo_path / build_numbers_file

    if temporary_dir.exists():
        log.info(f"Remove old repository in {temporary_dir}")
        remove_directory(str(temporary_dir))

    temporary_dir.mkdir(exist_ok=True)
    extract_repo(root_repo_dir=temporary_dir, repo_name='mdp_msdk-product-configs',
                 branch=branch, commit_id='HEAD')

    log.info(f'Getting build number from HEAD of {branch} branch for repo in {temporary_repo_path}')
    temporary_build_number = get_build_number(repo_path=temporary_repo_path,
                                              os_type=os_type, branch=branch)

    if origin_build_number != temporary_build_number:
        log.warning(f'Build numbers in remote ({temporary_build_number}) and local ({origin_build_number}) repositories are not equal'
                    f'It maybe because this is rebuild of old build for which build number already has been increased'
                    f'Stop operation')
        return False

    log.info('Increasing build number')
    if temporary_build_number_path.exists():
        try:
            log.info(f'\tChanging build numbers file')
            with temporary_build_number_path.open('r+') as build_number_file:
                build_numbers = json.load(build_number_file)

                new_build_number = build_numbers[os_type][branch] + 1
                build_numbers[os_type][branch] = new_build_number

                build_number_file.seek(0)
                build_number_file.write(json.dumps(build_numbers, indent=4, sort_keys=True))
                build_number_file.truncate()

            log.info(f'\tPush changes')

            push_change_commands = ['git add -A',
                                    f'git commit -m "Increase build number to {new_build_number}"'
                                    f'git push origin {branch}']
            for command in push_change_commands:
                return_code, output = cmd_exec(command, cwd=temporary_repo_path)
                if return_code:
                    log.error(output)

        except Exception:
            log.exception('Exception occurred')
            return False
    else:
        log.error(
            f'Increasing build number failed, because {temporary_build_number_path} does not exist')
        return False
    log.info(f'Build number successfully increased. New build number is {new_build_number}')
    return True
