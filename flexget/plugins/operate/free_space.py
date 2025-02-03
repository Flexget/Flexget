import shutil
from enum import Enum
from pathlib import Path, PurePath

from datamodel_code_generator.util import field_validator, model_validator
from loguru import logger
from pydantic import BaseModel, ByteSize, ConfigDict

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='free_space')


class AbortMode(str, Enum):
    BELOW = 'below'
    ABOVE = 'above'


class Config(BaseModel):
    space: ByteSize | float
    abort_if: AbortMode = AbortMode.BELOW
    path: PurePath = None
    port: int = 22
    host: str = None
    user: str = None
    ssh_key_filepath: str = None
    allotment: ByteSize | float = None

    @field_validator('space', 'allotment', mode='wrap')
    @classmethod
    def convert_to_mb(cls, v, handler):
        # Original config had these fields as MiB, but using ByteSize returns bytes if the field was a str
        r = handler(v)
        if not isinstance(v, (int, float)):
            return r / 1024 / 1024
        return r

    @model_validator(mode='before')
    @classmethod
    def standardize(cls, data):
        """Converts to the full form of the config from simplified form."""
        if isinstance(data, (float, int)):
            data = {'space': data}
        return data

    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            "type": ["object", "string", "number"],
            "dependentRequired": {"host": ["user", "ssh_key_filepath", "path"]},
        },
    )


def get_free_space(config: Config, task) -> int:
    """Return folder/drive free space (in megabytes)"""
    if 'host' in config:
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                config.host,
                config.port,
                config.user,
                None,
                None,
                config.ssh_key_filepath,
                timeout=5000,
            )
        except Exception as e:
            logger.error("Issue connecting to remote host. {}", e)
            task.abort('Error with remote host.')
        if config.allotment is not None:
            stdin, stdout, stderr = ssh.exec_command(f"du -s {config.path} | cut -f 1")
        else:
            stdin, stdout, stderr = ssh.exec_command(
                f"df -k {config.path} | tail -1 | tr -s ' ' | cut -d' ' -f4"
            )
        outlines = stdout.readlines()
        resp = ''.join(outlines)
        ssh.close()
        try:
            if config.allotment is not None:
                free = int(config.allotment) - int(resp.strip())
            else:
                free = int(resp.strip())
        except ValueError:
            logger.error('Non-integer was returned when calculating disk usage.')
            task.abort('Error with remote host.')
        return free
    path = Path(config.path).expanduser().absolute()
    usage = shutil.disk_usage(path)
    return usage.free


class PluginFreeSpace:
    """Aborts a task if an entry is accepted and there is less than a certain amount of space free on a drive."""

    config_model = Config

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_download(self, task, config: Config):
        # Use config path if none is specified
        if not config.path:
            config.path = task.manager.config_base

        free_space = get_free_space(config, task)
        space = config.space
        path = config.path
        abort_if = config.abort_if

        if free_space < space and abort_if == AbortMode.BELOW:
            logger.error('Less than {} MB of free space in {} aborting task.', space, path)
            # backlog plugin will save and restore the task content, if available
            task.abort(f"Less than {space} MB of free space in {path}")
        elif free_space > space and abort_if == AbortMode.ABOVE:
            logger.error('Over than {} MB of free space in {} aborting task.', space, path)
            # backlog plugin will save and restore the task content, if available
            task.abort(f"Over than {space} MB of free space in {path}")


@event('plugin.register')
def register_plugin():
    plugin.register(PluginFreeSpace, 'free_space', api_ver=3)
