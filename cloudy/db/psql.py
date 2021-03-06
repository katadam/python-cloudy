import os
import re
import sys
from operator import itemgetter
import datetime

from fabric.api import run
from fabric.api import task
from fabric.api import sudo
from fabric.api import put
from fabric.api import env
from fabric.api import settings
from fabric.api import hide
from fabric.contrib import files

from cloudy.sys.etc import sys_etc_git_commit


def db_psql_latest_version():
    """ Get the latest available postgres version - Ex: (cmd)"""
    
    latest_version = ''
    with settings(
        hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            ret = run('apt-cache search postgresql-client')
    
    version_re = re.compile('postgresql-client-([0-9.]*)\s-')
    lines = ret.split('\n')
    versions = []
    for line in lines:
        ver = version_re.search(line.lower())
        if ver:
            versions.append(ver.group(1))
    
    versions.sort(key = itemgetter(2), reverse = False)
    try:
        latest_version = versions[0]
    except:
        pass
    
    print >> sys.stderr, 'Latest available postgresql is: [{0}]'.format(latest_version)
    return latest_version


def db_psql_default_installed_version():
    """ Get the default installed postgres version - Ex: (cmd) """

    default_version = ''
    with settings(
        hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
            ret = run('psql --version | head -1')

    version_re = re.compile('(.*)\s([0-9.]*)')
    ver = version_re.search(ret.lower())
    if ver:
        default_version = ver.group(2)[:3]

    print >> sys.stderr, 'Default installed postgresql is: [{0}]'.format(default_version)
    return default_version
        
def db_psql_install(version=''):
    """ Install postgres of a given version or the latest version - Ex: (cmd:[9.1])"""

    if not version:
        version = db_psql_latest_version()
        
    # requirements
    requirements = '%s' % ' '.join([
        'postgresql-{0}'.format(version),
        'postgresql-client-{0}'.format(version),
        'postgresql-contrib-{0}'.format(version),
        'postgresql-server-dev-{0}'.format(version),
        'postgresql-client-common'
    ])
    
    # install requirements
    sudo('apt-get -y install {0}'.format(requirements))
    sys_etc_git_commit('Installed postgres ({0})'.format(version))


def db_psql_make_data_dir(version='', data_dir='/var/lib/postgresql'):
    """ Make data directory for the postgres cluster - Ex: (cmd:[pgversion],[datadir])"""
    
    if not version:
        version =db_psql_latest_version()

    data_dir = os.path.abspath(os.path.join(data_dir, '{0}'.format(version)))
    sudo('mkdir -p {0}'.format(data_dir))
    return data_dir


def db_psql_remove_cluster(version, cluster):
    """ Remove a clauster if exists - Ex: (cmd:<pgversion><cluster>)"""

    with settings(warn_only=True):
        sudo('pg_dropcluster --stop {0} {1}'.format(version, cluster))

    sys_etc_git_commit('Removed postgres cluster ({0} {1})'.format(version, cluster))


def db_psql_create_cluster(version='', cluster='main', encoding='UTF-8', data_dir='/var/lib/postgresql'):
    """ Make a new postgresql clauster - Ex: (cmd:[pgversion],[cluster],[encoding],[datadir])"""

    if not version:
        version = db_psql_default_installed_version()
    if not version:
        version = db_psql_latest_version()

    db_psql_remove_cluster(version, cluster)
    
    data_dir = db_psql_make_data_dir(version, data_dir)
    sudo('chown -R postgres {0}'.format(data_dir))
    sudo('pg_createcluster --start -e {0} {1} {2} -d {3}'.format(encoding, version, cluster, data_dir))
    sudo('service postgresql start')
    sys_etc_git_commit('Created new postgres cluster ({0} {1})'.format(version, cluster))

def db_psql_set_permission(version='', cluster='main'):
    """ Set default permission for postgresql - Ex: (cmd:<version>,[cluster])"""
    if not version:
        version = db_psql_default_installed_version()

    cfgdir = os.path.join(os.path.dirname( __file__), '../cfg')
    localcfg = os.path.expanduser(os.path.join(cfgdir, 'postgresql/pg_hba.conf'))
    remotecfg = '/etc/postgresql/{0}/{1}/pg_hba.conf'.format(version, cluster)
    sudo('rm -rf ' + remotecfg)
    put(localcfg, remotecfg, use_sudo=True)
    sudo('chown postgres:postgres {0}'.format(remotecfg))
    sudo('chmod 644 {0}'.format(remotecfg))
    sudo('service postgresql start')
    sys_etc_git_commit('Set default postgres access for cluster ({0} {1})'.format(version, cluster))

def db_psql_configure(version='', cluster='main', port='5432', interface='*', restart=False):
    """ Configure postgres - Ex: (cmd:[pgversion],[cluster],[port],[interface])"""
    if not version:
        version = db_psql_default_installed_version()

    """ Configures posgresql configuration files """
    conf_dir = '/etc/postgresql/{0}/{1}'.format(version, cluster)
    postgresql_conf = os.path.abspath(os.path.join(conf_dir, 'postgresql.conf'))
    sudo('sed -i "s/#listen_addresses\s\+=\s\+\'localhost\'/listen_addresses = \'{0}\'/g" {1}'.format(interface, postgresql_conf))
    sudo('sed -i /\s*\unix_socket_directory\s*.*/d {0}'.format(postgresql_conf))
    sudo('sed -i \"1iunix_socket_directory = \'{0}\'\" {1}'.format('/var/run/postgresql', postgresql_conf))
    
    # total_mem = sudo("free -m | head -2 | grep Mem | awk '{print $2}'")
    # shared_buffers = eval(total_mem) / 4    
    # sudo('sed -i "s/shared_buffers\s\+=\s\+[0-9]\+MB/shared_buffers = {0}MB/g" {1}'.format(shared_buffers, postgresql_conf))
    
    sys_etc_git_commit('Configured postgres cluster ({0} {1})'.format(version, cluster))
    if restart:
        sudo('service postgresql start')

def db_psql_create_adminpack():
    """ Install admin pack - Ex: (cmd)"""
    sudo('echo "CREATE EXTENSION adminpack;" | sudo -u postgres psql')


def db_psql_postgres_password(password):
    """ Change password for user: postgres - Ex: (cmd:<password>)"""
    sudo('echo "ALTER USER postgres WITH ENCRYPTED PASSWORD \'{0}\';" | sudo -u postgres psql'.format(password))


def db_psql_create_user(username, password):
    """ Create postgresql user - Ex: (cmd:<dbuser>,<dbname>)"""
    sudo('echo "CREATE ROLE {0} WITH LOGIN ENCRYPTED PASSWORD \'{1}\';" | sudo -u postgres psql'.format(username, password))


def db_psql_delete_user(username):
    """ Delete postgresql user - Ex: (cmd:<dbuser>)"""
    if username != 'postgres':
        sudo('echo "DROP ROLE {0};" | sudo -u postgres psql'.format(username))
    else:
        print >> sys.stderr, "Cannot drop user 'postgres'"


def db_psql_list_users():
    """ List postgresql users - Ex: (cmd)"""
    sudo('sudo -u postgres psql -d template1 -c \"SELECT * from pg_user;\"')


def db_psql_list_databases():
    """ List postgresql databases - Ex: (cmd)"""
    sudo('sudo -u postgres psql -l')


def db_psql_create_database(dbname, dbowner):
    """ Create a postgres database for and existing user - Ex: (cmd:<dbname>,<dbowner>)"""
    sudo('sudo -u postgres createdb -O {0} {1}'.format(dbowner, dbname))


def db_psql_create_gis_database(dbname, dbowner):
    """ Create a postgres GIS database for and existing user - Ex: (cmd:<dbname>,<dbowner>)"""
    sudo('sudo -u postgres createdb -T template_postgis -O {0} {1}'.format(dbowner, dbname))
        

def db_psql_delete_database(dbname):
    """ Delete (drop) a database - Ex: (cmd:<dbname>) """
    sudo('echo "DROP DATABASE {0};" | sudo -u postgres psql'.format(dbname))

def db_psql_dump_database(dump_dir, db_name, dump_name=''):
    """ Backup (dump) a database and save into a given directory - Ex: (cmd:<dumpdir>,<dbname>,[dumpname]) """
    if not files.exists(dump_dir):
        sudo('mkdir -p {0}'.format(dump_dir))
    if not dump_name:
        now = datetime.datetime.now()
        dump_name = "{0}_{1}_{2}_{3}_{4}_{5}.psql.gz".format(db_name, now.year, now.month, now.day, now.hour, now.second)
    dump_name = os.path.join(dump_dir, dump_name)
    pg_dump = '/usr/bin/pg_dump'
    if not files.exists(pg_dump):
        pg_dump = run('which pg_dump')
    if files.exists(pg_dump):
        sudo('sudo -u postgres {0} -h localhost | gzip > {1}'.format(pg_dump, dump_name))



