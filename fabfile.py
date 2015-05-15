"""Smile automated deployments using Fabric

.. module:: fabfile
   :platform: Debian or Ubuntu
   :synopsis: Fabric to facilitate deployments

.. moduleauthor:: Corentin POUHET-BRUNERIE <corentin.pouhet-brunerie@smile.fr>
"""

import os
import time

from distutils.version import LooseVersion
import fabric.version

min_version = '1.6.1'
version = fabric.version.get_version()
if LooseVersion(version) < LooseVersion(min_version):
    raise ImportError("Fabric version not supported: %s < %s" % (version, min_version))

from fabric.api import env, local, put, run, settings, sudo, task
from fabric.context_managers import shell_env

from fabdecorator import smile_path, smile_secure, smile_settings


def sudo_or_run(*args, **kwargs):
    if env.use_sudo:
        return sudo(*args, **kwargs)
    return run(*args, **kwargs)


def create_branch(version):
    """Create a SVN branch from trunk

    :param version: name of new SVN branch
    :type version: str
    :returns: None
    """
    sudo_or_run('svn cp %(svn_repository)s/trunk %(svn_repository)s/branches/%(version)s '
         '-m "[ADD] Create new branch %(version)s"'
         % {'svn_repository': env.svn_repository, 'version': version})


@smile_path('sources_dir')
def _clean_sources_dir():
    """Delete sources directory

    :returns: None
    """
    sudo_or_run('rm -Rf */')
    sudo_or_run('rm -Rf .svn')
    sudo_or_run('rm -f *')
    sudo_or_run('ls | grep tar.gz | xargs rm -f')  # INFO: all files except for *.tar.gz


@smile_path('sources_dir')
def checkout_branch(version):
    """Checkout SVN branch

    :param version: name of SVN branch
    :type version: str
    :returns: None
    """
    _clean_sources_dir()
    sudo_or_run('svn co %(svn_repository)s/branches/%(version)s .'
         % {'svn_repository': env.svn_repository, 'version': version})


@smile_path('sources_dir')
def update_branch(version):
    """Update SVN branch

    :param version: name of SVN branch
    :type version: str
    :returns: None
    """
    sudo_or_run('svn up')


@smile_secure([0, 1])
@smile_path('tag_dir', local=True)
def _clean_tag_dir(tag):
    """Delete tag directory in local

    :param tag: name of SVN tag
    :type tag: str
    :returns: None
    """
    local('rm -Rf %s' % tag)


@smile_path('tag_dir', local=True)
def export_tag(tag, force_export_tag=False):
    """Export SVN tag in local

    :param tag: name of SVN tag
    :type tag: str
    :returns: None
    """
    if force_export_tag:
        local('[ -f %(tag)s ] || rm -Rf %(tag)s' % {'tag': tag})
    local('[ -f %(tag)s ] || svn export %(svn_repository)s/tags/%(tag)s %(tag)s'
          % {'svn_repository': env.svn_repository, 'tag': tag})


@smile_path('tag_dir', local=True)
def compress_archive(tag, force_export_tag=False):
    """Compress tag archive

    :param tag: name of SVN tag
    :type tag: str
    :returns: archive filename
    "rtype: str
    """
    archive = "odoo-%s.tag.gz" % tag
    if force_export_tag:
        local('[ -f %(archive)s ] || rm -f %(archive)s' % {'archive': archive})
    local('[ -f %(archive)s ] || tar -zcvf %(archive)s -C %(tag)s . --exclude-vcs'
          % {'archive': archive, 'tag': tag})
    return archive


@smile_path('tag_dir', local=True)
def put_archive(archive):
    """Get tag archive

    :param archive: archive filename
    :type archive: str
    :returns: None
    """
    put(archive, env.backup_dir, use_sudo=env.use_sudo)


@smile_path('sources_dir')
def uncompress_archive(archive):
    """Uncompress tag archive

    :param archive: archive filename
    :type archive: str
    :returns: None
    """
    _clean_sources_dir()
    sudo_or_run('tar -zxvf %s' % os.path.join(env.backup_dir, archive))


@smile_path('backup_dir')
def dump_database(db_name):
    """Dump database

    :param db_name: name of database
    :type db_name: str
    :returns: backup filename
    :rtype: str
    """
    filename = '%s_%s.dump' % (db_name, time.strftime('%Y%m%d_%H%M%S'))
    with shell_env(PGPASSWORD=env.db_password):
        sudo_or_run('pg_dump -f %s -F c -O %s --host=%s --port=%s --username=%s%s'
                    % (filename, db_name, env.db_host, env.db_port, env.db_user,
                       env.db_password and ' -w' or ''))
    return os.path.join(env.backup_dir, filename)


@smile_secure()
@smile_path('backup_dir')
def restore_database(db_name, backup):
    """Restore database

    :param db_name: name of database
    :type db_name: str
    :param backup: backup filename
    :type backup: str
    :returns: None
    """
    with shell_env(PGPASSWORD=env.db_password):
        sudo_or_run('pg_restore -v -c -d %s %s --host=%s --port=%s --username=%s%s'
                    % (db_name, backup, env.db_host, env.db_port, env.db_user,
                       env.db_password and ' -w' or ''))


def dump_or_restore_database(db_name, backup):
    """Restore database

    :param db_name: name of database
    :type db_name: str
    :param backup: backup filename
    :type backup: str
    :returns: None
    """
    if backup:
        restore_database(db_name, backup)
        return backup
    return dump_database(db_name)


@smile_secure()
@smile_path('sources_dir')
def upgrade_database(db_name):
    """Upgrade database

    :param db_name: name of database to upgrade
    :type db_name: str
    :returns: None
    """
    return sudo_or_run('su %(odoo_user)s -c "%(odoo_launcher)s -c %(odoo_conf)s -d %(db_name)s --load=web,smile_upgrade"' %
                       {'odoo_user': env.odoo_user, 'odoo_launcher': env.odoo_launcher, 'odoo_conf': env.odoo_conf, 'db_name': db_name})


def start_service():
    """Start Odoo Service

    :returns: None
    """
    sudo_or_run('service %s start' % env.odoo_service)


@smile_secure([0, 1])
def stop_service():
    """Stop Odoo Service

    :returns: None
    """
    sudo_or_run('service %s stop' % env.odoo_service)


@smile_path('backup_dir')
def create_savepoint():
    """Create savepoint by compressing sources archive

    :returns: archive filename
    "rtype: str
    """
    savepoint = 'savepoint_%s.tag.gz' % time.strftime('%Y%m%d_%H%M%S')
    sudo_or_run('tar -zcvf %s %s --exclude-vcs' % (savepoint, env.sources_dir))
    return savepoint


@smile_path('backup_dir')
def rollback(savepoint, db_name, backup):
    """Rollback by uncompressing savepoint archive and restoring database

    :returns: None
    """
    dump_or_restore_database(db_name, backup)
    _clean_sources_dir()
    uncompress_archive(savepoint)


@smile_path('backup_dir')
def drop_savepoint(savepoint):
    """Drop savepoint archive

    :returns: None
    """
    sudo_or_run('rm -f %s' % savepoint)


@task
@smile_settings('internal_testing')
def deploy_for_internal_testing(version, db_name, backup=None, do_not_create_branch=False):
    """Deploy in internal testing server

    :param version: name of SVN branch
    :type version: str
    :param db_name: database name to upgrade
    :type db_name: str
    :param backup: backup filename to restore instead of dump database if is None
    :type backup: str
    :param do_not_create_branch: do not create branch
    :type do_not_create_branch: bool
    :returns: None
    """
    if not do_not_create_branch:
        create_branch(version)
    stop_service()
    savepoint = create_savepoint()
    backup = dump_or_restore_database(db_name, backup)
    checkout_branch(version)
    result = upgrade_database(db_name)
    if result.return_code:
        rollback(savepoint, db_name, backup)
    drop_savepoint(savepoint)
    start_service()


@task
@smile_settings('customer_testing')
def deploy_for_customer_testing(tag, db_name, backup=None, force_export_tag=False):
    """Deploy in customer testing server

    :param tag: name of new SVN tag
    :type tag: str
    :param db_name: database name to upgrade
    :type db_name: str
    :param backup: backup filename to restore instead of dump database if is None
    :type backup: str
    :param force_export_tag: if True, export again tag even if exists and create a new archive
    :type force_export_tag: bool
    :returns: None
    """
    export_tag(tag, force_export_tag)
    archive = compress_archive(tag, force_export_tag)
    put_archive(archive)
    stop_service()
    savepoint = create_savepoint()
    backup = dump_or_restore_database(db_name, backup)
    uncompress_archive(archive)
    result = upgrade_database(db_name)
    if result.return_code:
        rollback(savepoint, db_name, backup)
    drop_savepoint(savepoint)
    start_service()
