import argparse
import logging
import os
import shutil
from pathlib import Path
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def onerror(func, path, _exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file),
    it attempts to add write permissions and retries.

    If the error is for another reason, it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=onerror)``
    """
    import stat
    # Is the error an access error?
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise


def get_blender_executable():
    """Blender 4.2 executable needed to build extensions and repository files."""
    blender_executable = os.environ.get('BLENDER_EXECUTABLE', '')
    if not blender_executable:
        raise EnvironmentError('BLENDER_EXECUTABLE not set')

    return blender_executable


def get_add_ons_dir():
    """Add-on directory where zip files and index files will be stored."""
    return Path(__file__).parent / 'add_ons'


def git_clone(url):
    """Git clones url, returning the new folder name."""
    logger.info('Cloning {}...'.format(url))
    subprocess.run(['git', 'clone', url], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    return url.split('/')[-1]


def build():
    repo_dir = Path(__file__).parent
    blender_executable = get_blender_executable()
    addon_directory = get_add_ons_dir()

    with open(repo_dir / 'env_repos.txt', 'r') as f:
        repositories = f.read().splitlines()
        logger.debug('Found {} repositories'.format(len(repositories)))

    # in packages directory, search for module folders
    updated = False
    to_delete = []
    for url in repositories:
        cloned_folder = git_clone(url)
        full_path = Path(__file__).parent / cloned_folder
        if not full_path.exists():
            raise FileNotFoundError(full_path)

        manifest = full_path / 'blender_manifest.toml'
        if not manifest.exists():
            raise FileNotFoundError(manifest)

        manifest_str = manifest.read_text()
        split_manifest = manifest_str.split('\n')
        id_line = next(line.strip() for line in split_manifest if line.strip().startswith('id'))
        version_line = next(line.strip() for line in split_manifest if line.strip().startswith('version'))

        id = id_line.split('"')[-2]
        version = version_line.split('"')[-2]
        zip_file = addon_directory / '{}-{}.zip'.format(id, version)

        logger.debug('Searching for {}...'.format(zip_file))
        if zip_file.exists():
            logger.info('Skipping {} {}...'.format(cloned_folder, version))
        else:
            cmd = [
                blender_executable,
                '--command', 'extension', 'build',
                '--source-dir={}'.format(full_path),
                '--output-dir={}'.format(addon_directory)
            ]
            logger.info('Running: {}'.format(' '.join(cmd)))
            subprocess.run(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
            updated = True

        to_delete.append(full_path)

    for full_path in to_delete:
        if full_path.exists():
            logger.debug('Deleting temp folder {}...'.format(full_path))
            shutil.rmtree(full_path, onerror=onerror)

    return updated

def build_json():
    """Builds JSON file for all zip files in extensions folder."""
    blender_executable = get_blender_executable()

    cmd = [blender_executable, '--command', 'extension', 'server-generate', '--html', '--repo-dir={}'.format(get_add_ons_dir())]
    logger.info('Running: {}'.format(' '.join(cmd)))
    subprocess.run(cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

    logger.info('Done!')


if __name__ == '__main__':
    args = argparse.ArgumentParser()
    args.add_argument('--clean', action='store_true', help='remove build folder')
    args.add_argument('--json-only', action='store_true', help='Only generate JSON')
    parsed_args = args.parse_args()

    if parsed_args.clean:
        shutil.rmtree(get_add_ons_dir(), ignore_errors=True)
        os.mkdir(get_add_ons_dir())

    if parsed_args.json_only or build():
        build_json()
        subprocess.run(['git', 'add', 'add_ons'], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
