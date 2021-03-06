import os
import re
import sys

from fabric.api import run
from fabric.api import task
from fabric.api import sudo
from fabric.api import put
from fabric.api import env
from fabric.api import settings
from fabric.api import hide
from fabric.utils import abort
from fabric.contrib import files
from fabric.utils import abort

from cloudy.sys.etc import sys_etc_git_commit


def sys_mount_device_format(device, mount_point, filesystem='xfs'):
    """ Mount a device which survives a reboot - Ex: (cmd:<device>,<mountpoint>,[filesystem]) """
    
    if util_mount_is_mounted(device):
        abort('Device ({0}) is already mounted'.format(device)) 
    util_mount_validate_vars(device, mount_point, filesystem)
    sudo('mkfs.{0} -f {1}'.format(filesystem, device))
    sys_mount_device(device, mount_point, filesystem)
    sys_mount_fstab_add(device, mount_point, filesystem)
    sys_etc_git_commit('Mounted {0} on {1} using {2}'.format(device, mount_point, filesystem))

def sys_mount_device(device, mount_point, filesystem='xfs'):
    """ Mount a device - Ex: (cmd:<device>,<mountpoint>,[filesystem]) """

    if util_mount_is_mounted(device):
        abort('Device ({0}) is already mounted'.format(device)) 
    util_mount_validate_vars(device, mount_point, filesystem)
    sudo('mount -t {0} {1} {2}'.format(filesystem, device, mount_point))

def sys_mount_fstab_add(device, mount_point, filesystem='xfs'):
    """ Add a mount record into fstab - Ex: (cmd:<device>,<mountpoint>,[filesystem]) """
    util_mount_validate_vars(device, mount_point, filesystem)
    # sudo('sed -i /\s*{0}\s*/d {1}'.format(device.replace('/', '\\\\/'), '/etc/fstab'))
    sudo('echo "{0}  {1}   {2} noatime 0 0" | sudo tee -a /etc/fstab'.format(device, mount_point, filesystem))

def util_mount_validate_vars(device, mount_point, filesystem='xfs'):
    """ Check system for device and mount point and file system"""
    
    if not files.exists(mount_point):
        sudo('mkdir -p {0}'.format(mount_point))
    if not files.exists(device):
        abort('Device ({0}) missing or not attached'.format(device))
    
    if filesystem == 'xfs':
        sudo('apt-get install -y xfsprogs')
    
    sudo('grep -q {0} /proc/filesystems || modprobe {0}'.format(filesystem))

def util_mount_is_mounted(device):
    with settings(
        hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
        ret = run('df')
        if device in ret:
            return True
    return False
    