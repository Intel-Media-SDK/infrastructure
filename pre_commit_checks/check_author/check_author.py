import git
import sys
import pathlib
import argparse
import logging

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))
from common import logger_conf
from common.helper import ErrorCode


class Checker:
    def __init__(self, repo_path, revision):
        self.repo = git.Repo(pathlib.Path(repo_path))
        self.revision = revision

    def _get_author_info(self):
        log = logging.getLogger(f'{self.__class__.__name__}._get_author_info')
        log.info(f'Getting author information for {self.revision} revision.')
        commit = self.repo.commit(self.revision)
        log.info('Author name: {commit.author.name}')
        log.info(f'Author email: {commit.author.email}')
        return commit.author.name, commit.author.email

    def check_author(self, author):
        log = logging.getLogger(f'{self.__class__.__name__}.check_author')
        incorrect_author_names = ['root', 'mediasdk']

        if author not in incorrect_author_names:
            log.info('Author name is correct')
            return True
        log.error('Author name is not correct.')
        log.error(f'Author name can not be {", ".join(incorrect_author_names)}.')
        return False

    def check_email(self, email):
        log = logging.getLogger(f'{self.__class__.__name__}.check_email')
        incorrect_email_endswith = '@localhost.localdomain'

        if not email.endswith(incorrect_email_endswith):
            log.info('Author email is correct')
            return True
        log.error(f'Author email is not correct.')
        log.error(f'{incorrect_email_endswith} can not be in email address.')
        return False

    def check(self):
        author, email = self._get_author_info()

        check_author_result = self.check_author(author)
        check_email_result = self.check_email(email)

        return check_author_result and check_email_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--repo-path", metavar="String",
                        help="Path to repository")
    parser.add_argument("-r", "--revision", metavar="String",
                        help="Revision to check")
    args = parser.parse_args()
    logger_conf.configure_logger()
    log = logging.getLogger('pre_build_check.main')

    checker = Checker(repo_path=args.repo_path, revision=args.revision)
    if checker.check():
        log.info("All checks PASSED")
        exit(0)
    log.info("Some checks FAILED")
    exit(ErrorCode.CRITICAL.value)

if __name__ == '__main__':
    main()
