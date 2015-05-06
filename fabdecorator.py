"""Smile fabric decorators

.. module:: fabdecorator
   :platform: Debian or Ubuntu
   :synopsis: Helpers to build Smile fabric script

.. moduleauthor:: Corentin POUHET-BRUNERIE <corentin.pouhet-brunerie@smile.fr>
"""

from functools import wraps

from fabric.api import cd, env, lcd, settings

DEFAULTS = {
    'backup_dir': '/home/postgres',
    'sources_dir': '/opt/openerp',
    'tag_dir': '/tmp',
    'odoo_user': 'openerp',
    'odoo_launcher': 'openerp-server',
    'odoo_conf': '/etc/openerp-server.conf',
    'odoo_service': 'openerp-server',
    'use_sudo': False,
    'db_host': 'localhost',
    'db_port': 5432,
    'db_user': 'openerp',
    'db_password': '',
}

BOOLEAN_SETTINGS = ['use_sudo']


def smile_path(dir, local=False):
    def wrap(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if local:
                with lcd(getattr(env, dir)):
                    return func(*args, **kwargs)
            else:
                with cd(getattr(env, dir)):
                    return func(*args, **kwargs)
        return wrapper
    return wrap


def smile_secure(ok_ret_codes=[]):
    def wrap(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            params = {'warn_only': not ok_ret_codes, 'ok_ret_codes': ok_ret_codes}
            with settings(**params):
                return func(*args, **kwargs)
        return wrapper
    return wrap


def smile_settings(host_type):
    def wrap(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            setattr(env, host_type, {})
            for k, v in env.items():
                if k.startswith(host_type):
                    key = k.replace('%s_' % host_type, '')
                    if key in BOOLEAN_SETTINGS and isinstance(v, basestring):
                        v = eval(v)
                    getattr(env, host_type)[key] = v
            for default in DEFAULTS:
                if not hasattr(env, default):
                    setattr(env, default, DEFAULTS[default])
            with settings(**getattr(env, host_type)):
                return func(*args, **kwargs)
        return wrapper
    return wrap
