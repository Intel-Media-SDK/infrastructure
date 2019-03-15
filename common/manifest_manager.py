# Copyright (c) 2019 Intel Corporation
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
Manifest file manager
"""

import pathlib
import yaml


class ManifestException(Exception):
    pass


class ManifestDoesNotExist(ManifestException):
    pass


class ManifestSavingError(ManifestException):
    pass


class WrongComponentFormatError(ManifestException):
    pass


class WrongRepositoryFormatError(ManifestException):
    pass


class Manifest:
    """
    Manifest wrapper
    """

    def __init__(self, manifest_path=None):
        """
        :param manifest_path: Path to a manifest file
        :type manifest_path: String
        """

        self._manifest_file = pathlib.Path(manifest_path) if manifest_path else None
        self._version = '0'  # gets from manifest
        self._components = {}  # gets from manifest

        if manifest_path:
            self._prepare_manifest()

    def __repr__(self):
        return str(self._manifest_file) if self._manifest_file else 'manifest.yml'

    def _prepare_manifest(self):
        """
        Read manifest file and convert it's data to objects

        :return: None | Exception
        :rtype: None | ManifestException
        """

        if self._manifest_file.is_file():
            with self._manifest_file.open('r') as manifest:
                manifest_info = yaml.load(manifest, Loader=yaml.FullLoader)

            self._version = manifest_info.get('version', '0')

            for name, info in manifest_info['components'].items():
                self._components[name] = Component.from_dict({
                    'name': name,
                    'version': info['version'],
                    'repository': info['repository']})
        else:
            raise ManifestDoesNotExist(f'Can not find manifest "{self._manifest_file}"')

    @property
    def version(self):
        """
        get manifest version
        """

        return self._version

    @property
    def components(self):
        """
            get components list
        """

        return list(self._components.values())

    def get_component(self, component_name):
        """
        get component by name

        :param component_name: Name of a component
        :type component_name: String

        :return: Component object | None
        :rtype: Component | None
        """

        return self._components.get(component_name, None)

    def add_component(self, component, replace=False):
        """
        add component to manifest

        :param component: Component object
        :type component: Component

        :param replace: Replace component with the same name
        :type replace: Boolean

        :return: Boolean
        :rtype: Boolean
        """

        if not replace and component.name in self._components:
            return False

        self._components[component.name] = component
        return True

    def delete_component(self, component_name):
        """
        delete component to another

        :param component_name: Name of a component
        :type component_name: String

        :return: Boolean
        :rtype: Boolean
        """

        try:
            del self._components[component_name]
        except KeyError:
            return False
        return True

    def save_manifest(self, save_to):
        """
        save manifest to a file

        :param save_to: path to a new manifest file
        :type save_to: String

        :return: None | Exception
        :rtype: None | ManifestException
        """

        path_to_save = pathlib.Path(save_to)
        path_to_save.parent.mkdir(parents=True, exist_ok=True)

        manifest_data = {'components': {},
                         'version': self._version}

        for comp_name, comp_data in self._components.items():
            comp = dict(comp_data)
            manifest_data['components'][comp_name] = {
                'repository': comp['repositories'],
                'version': comp['version']
            }

        try:
            with path_to_save.open('w') as manifest:
                yaml.dump(manifest_data, stream=manifest,
                          default_flow_style=False, sort_keys=False)
        except Exception as ex:
            raise ManifestSavingError(ex)


class Component:
    """
    Component wrapper
    """

    def __init__(self, name, version, repositories):
        """
        :param name: Name of component
        :type name: String

        :param version: Version of component
        :type version: String

        :param repositories: List of Repository objects
        :type repositories: List
        """

        self._name = name
        self._version = version
        self._repositories = {}

        self._prepare_repositories(repositories)

    def __iter__(self):
        yield 'name', self._name
        yield 'version', self._version
        yield 'repositories', [dict(repo) for repo in self._repositories.values()]

    def _prepare_repositories(self, repositories):
        for repo in repositories:
            if isinstance(repo, dict):
                self._repositories[repo['name']] = Repository.from_dict(repo)
            elif isinstance(repo, Repository):
                self._repositories[repo.name] = repo

    @staticmethod
    def from_dict(comp_data):
        """
        Method for converting dictionary to object

        :param comp_data: Component data
        :type comp_data: Dictionary

        :return: Component obj | Exception
        :rtype: Component | ManifestException
        """

        try:
            component = Component(comp_data['name'],
                                  comp_data['version'],
                                  comp_data['repository'])
        except ManifestException:
            raise
        except Exception as ex:
            raise WrongComponentFormatError(ex)
        return component

    @property
    def name(self):
        """
        get component name

        :return: Component name
        :rtype: String
        """

        return self._name

    @property
    def version(self):
        """
        get component version

        :return: Version of component
        :rtype: String
        """

        return self._version

    @property
    def repositories(self):
        """
        get repositories list

        :return: List of Repository objects
        :rtype: List
        """

        return list(self._repositories.values())

    @property
    def trigger_repository(self):
        """
        get triggered repository

        :return: Repository object | None
        :rtype: Repository | None
        """

        for repo in self._repositories.values():
            if repo.is_trigger:
                return repo
        return None

    def get_repository(self, repository_name):
        """
        get repository by name

        :param repository_name: Name of repository
        :type repository_name: String

        :return: Repository object | None
        :rtype: Repository | None
        """

        return self._repositories.get(repository_name, None)

    def add_repository(self, repository, replace=False):
        """
        add repository to component

        :param repository: Repository object
        :type repository: Repository

        :param replace: Replace repository with the same name
        :type replace: Boolean

        :return: Boolean
        :rtype: Boolean
        """

        if not replace and repository.name in self._repositories:
            return False

        self._repositories[repository.name] = repository
        return True

    def delete_repository(self, repository_name):
        """
        delete repository to another

        :param repository_name: Repository name
        :type repository_name: String

        :return: Boolean
        :rtype: Boolean
        """

        try:
            del self._repositories[repository_name]
        except KeyError:
            return False
        return True


class Repository:
    """
    Container for repository information
    """

    def __init__(self, name, url, branch='master', revision='HEAD', source_type='git', trigger=False):
        self._name = name
        self._url = url
        self._branch = branch
        self._revision = revision
        self._type = source_type
        self._trigger = trigger

    def __iter__(self):
        yield 'name', self._name
        yield 'url', self._url
        yield 'branch', self._branch
        yield 'revision', self._revision
        yield 'type', self._type
        yield 'trigger', self._trigger

    @staticmethod
    def from_dict(repo_data):
        """
        Method for converting dictionary to object

        :param repo_data: Repository data
        :type repo_data: Dictionary

        :return: Repository obj | Exception
        :rtype: Repository | ManifestException
        """

        try:
            repo = Repository(repo_data['name'],
                              repo_data['url'],
                              repo_data['branch'],
                              repo_data['revision'],
                              repo_data['type'],
                              repo_data['trigger'])
        except Exception as ex:
            raise WrongRepositoryFormatError(ex)
        return repo

    @property
    def name(self):
        """
        get name of repo

        :return: Name of repository
        :rtype: String
        """

        return self._name

    @property
    def url(self):
        """
        get url of repo

        :return: URL of repository
        :rtype: String
        """

        return self._url

    @property
    def branch(self):
        """
        get branch of repo

        :return: Branch name
        :rtype: String
        """

        return self._branch

    @property
    def revision(self):
        """
        get revision of repo

        :return: Revision of repository
        :rtype: String
        """

        return self._revision

    @property
    def type(self):
        """
        get type of repository

        :return: type of repository
        :rtype: String
        """

        return self._type

    @property
    def is_trigger(self):
        """
        Is triggered repository

        :return: Boolean
        :rtype: Boolean
        """

        return self._trigger


if __name__ == '__main__':
    m = Manifest(pathlib.Path(r'C:\Users\dlobanox\Projects\product-configs\manifest.yml'))
    m.save_manifest('man.yml')
