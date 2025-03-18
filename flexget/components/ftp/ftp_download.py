import ftplib
import os
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError

logger = logger.bind(name="ftp")


class OutputFtp:
    """Ftp Download plugin.

    input-url: ftp://<user>:<password>@<host>:<port>/<path to file>
    Example: ftp://anonymous:anon@my-ftp-server.com:21/torrent-files-dir

    config:
        ftp_download:
          use-ssl: <True/False>
          ftp_tmp_path: <path>
          delete_origin: <True/False>
          download_empty_dirs: <True/False>

    Todo:
      - Resume downloads
      - create banlists files
      - validate connection parameters

    """

    schema = {
        "type": "object",
        "properties": {
            "use-ssl": {"type": "boolean", "default": False},
            "ftp_tmp_path": {"type": "string", "format": "path"},
            "delete_origin": {"type": "boolean", "default": False},
            "download_empty_dirs": {"type": "boolean", "default": False},
        },
        "additionalProperties": False,
    }

    def prepare_config(self, config, task):
        config.setdefault("use-ssl", False)
        config.setdefault("delete_origin", False)
        config.setdefault("ftp_tmp_path", str(task.manager.config_base / "temp"))
        config.setdefault("download_empty_dirs", False)
        return config

    def ftp_connect(self, config, ftp_url, current_path: Path):
        ftp = ftplib.FTP_TLS() if config["use-ssl"] else ftplib.FTP()

        # ftp.set_debuglevel(2)
        logger.debug("Connecting to {}", ftp_url.hostname)
        ftp.connect(ftp_url.hostname, ftp_url.port)
        ftp.login(ftp_url.username, ftp_url.password)
        if config["use-ssl"]:
            ftp.prot_p()
        ftp.sendcmd("TYPE I")
        ftp.set_pasv(True)
        logger.debug("Changing directory to: {}", current_path)
        ftp.cwd(str(current_path))

        return ftp

    def check_connection(self, ftp, config, ftp_url, current_path: Path):
        try:
            ftp.voidcmd("NOOP")
        except (OSError, ftplib.Error):
            ftp = self.ftp_connect(config, ftp_url, current_path)
        return ftp

    def on_task_download(self, task, config):
        config = self.prepare_config(config, task)
        for entry in task.accepted:
            ftp_url = urlparse(entry.get("url"))
            ftp_url.path = unquote(ftp_url.path)
            current_path = Path(ftp_url.path).parent
            try:
                ftp = self.ftp_connect(config, ftp_url, current_path)
            except ftplib.all_errors as e:
                entry.fail(f"Unable to connect to server : {e}")
                break

            to_path = Path(config["ftp_tmp_path"])

            try:
                to_path = entry.render(str(to_path))
            except RenderError as err:
                raise plugin.PluginError(
                    f"Path value replacement `{to_path}` failed: {err.args[0]}"
                )

            if not to_path.exists():
                logger.debug("Creating base path: {}", to_path)
                to_path.mkdir(parents=True)
            if not to_path.is_dir():
                raise plugin.PluginWarning(f"Destination `{to_path}` is not a directory.")

            file_name = Path(ftp_url.path).name

            try:
                # Directory
                ftp = self.check_connection(ftp, config, ftp_url, current_path)
                ftp.cwd(file_name)
                self.ftp_walk(ftp, to_path / file_name, config, ftp_url, Path(ftp_url.path))
                ftp = self.check_connection(ftp, config, ftp_url, current_path)
                ftp.cwd("..")
                if config["delete_origin"]:
                    ftp.rmd(file_name)
            except ftplib.error_perm:
                # File
                self.ftp_down(ftp, file_name, to_path, config, ftp_url, current_path)

            ftp.close()

    def on_task_output(self, task, config):
        """Count this as an output plugin."""

    def ftp_walk(self, ftp, tmp_path: Path, config, ftp_url, current_path: Path):
        logger.debug("DIR->{}", ftp.pwd())
        logger.debug("FTP tmp_path : {}", tmp_path)
        try:
            ftp = self.check_connection(ftp, config, ftp_url, current_path)
            dirs = ftp.nlst(ftp.pwd())
        except ftplib.error_perm as ex:
            logger.info("Error {}", ex)
            return ftp

        if not dirs:
            if config["download_empty_dirs"]:
                tmp_path.mkdir()
            else:
                logger.debug("Empty directory, skipping.")
            return ftp

        for file_name in (path for path in dirs if path not in (".", "..")):
            file_name = os.path.basename(file_name)
            try:
                ftp = self.check_connection(ftp, config, ftp_url, current_path)
                ftp.cwd(file_name)
                if not tmp_path.is_dir():
                    tmp_path.mkdir()
                    logger.debug("Directory {} created", tmp_path)
                ftp = self.ftp_walk(
                    ftp,
                    tmp_path / os.path.basename(file_name),
                    config,
                    ftp_url,
                    current_path / os.path.basename(file_name),
                )
                ftp = self.check_connection(ftp, config, ftp_url, current_path)
                ftp.cwd("..")
                if config["delete_origin"]:
                    ftp.rmd(os.path.basename(file_name))
            except ftplib.error_perm:
                ftp = self.ftp_down(
                    ftp, os.path.basename(file_name), tmp_path, config, ftp_url, current_path
                )
        return self.check_connection(ftp, config, ftp_url, current_path)

    def ftp_down(self, ftp, file_name, tmp_path: Path, config, ftp_url, current_path: Path):
        logger.debug("Downloading {} into {}", file_name, tmp_path)

        if not tmp_path.exists():
            tmp_path.mkdir(parents=True)

        local_file = (tmp_path / file_name).open("a+b")
        ftp = self.check_connection(ftp, config, ftp_url, current_path)
        try:
            ftp.sendcmd("TYPE I")
            file_size = ftp.size(file_name)
        except Exception:
            file_size = 1

        max_attempts = 5
        size_at_last_err = 0
        logger.info("Starting download of {} into {}", file_name, tmp_path)
        while file_size > local_file.tell():
            try:
                if local_file.tell() != 0:
                    ftp = self.check_connection(ftp, config, ftp_url, current_path)
                    ftp.retrbinary(f"RETR {file_name}", local_file.write, local_file.tell())
                else:
                    ftp = self.check_connection(ftp, config, ftp_url, current_path)
                    ftp.retrbinary(f"RETR {file_name}", local_file.write)
            except Exception as error:
                if max_attempts != 0:
                    if size_at_last_err == local_file.tell():
                        # Nothing new was downloaded so the error is most likely connected to the resume functionality.
                        # Delete the downloaded file and try again from the beginning.
                        local_file.close()
                        (tmp_path / file_name).unlink()
                        local_file = (tmp_path / file_name).open("a+b")
                        max_attempts -= 1

                    size_at_last_err = local_file.tell()
                    logger.debug("Retrying download after error {}", error.args[0])
                    # Short timeout before retry.
                    time.sleep(1)
                else:
                    logger.error("Too many errors downloading {}. Aborting.", file_name)
                    break

        local_file.close()
        if config["delete_origin"]:
            ftp = self.check_connection(ftp, config, ftp_url, current_path)
            ftp.delete(file_name)

        return ftp


@event("plugin.register")
def register_plugin():
    plugin.register(OutputFtp, "ftp_download", api_ver=2)
