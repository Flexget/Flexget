from __future__ import unicode_literals, division, absolute_import

import datetime
import logging
import os
import shutil

from flexget.db_schema import flexget_db_version
from flexget.event import event

log = logging.getLogger('db_backup')


@event('manager.backup_db')
def create_db_backup(manager):
    log.verbose('backup db on upgrade flag detected, trying to backup DB')
    now = datetime.datetime.now()
    date = "{:02d}{:02d}{:02d}_{:02d}{:02d}".format(now.year, now.month, now.day, now.hour, now.minute)
    current_db_version = flexget_db_version()
    db_backup_filename = os.path.join(manager.config_base,
                                      'backup-{}-{}-{}.sqlite'.format(manager.config_name, date, current_db_version))
    log.debug('trying to create a backup DB to %s', db_backup_filename)
    if os.path.exists(manager.db_filename):
        try:
            shutil.copy(manager.db_filename, db_backup_filename)
            log.info('Backup database successfully created at %s', db_backup_filename)
        except Exception as e:
            log.warn('Could not backup DB: %s', e.message)


@event('manager.upgrade')
def no_backup_warning(manager):
    if not manager.options.backup_db:
        log.info('DB is upgrading without a backup, consider using the `--backup-db-on-upgrade` flag')
