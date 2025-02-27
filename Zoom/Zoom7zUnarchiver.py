#
# Copyright 2010 Per Olofsson
# Updated as draft by Yoann Gini in 2017 to support 7z file format for Zoom
# No longer needed by Zoom but kept here for reference.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""See docstring for Zoom7zUnarchiver class."""

import os
import shutil
import subprocess

from autopkglib import Processor, ProcessorError  # noqa: F401

__all__ = ["Zoom7zUnarchiver"]

EXTNS = {
    "zip": ["zip"],
    "tar_gzip": ["tar.gz", "tgz"],
    "tar_bzip2": ["tar.bz2", "tbz"],
    "tar": ["tar"],
    "gzip": ["gzip"],
    "7z": ["7z"],
}


class Zoom7zUnarchiver(Processor):  # pylint: disable=invalid-name
    """Archive decompressor for zip and common tar-compressed formats."""

    description = __doc__
    input_variables = {
        "archive_path": {
            "required": False,
            "description": "Path to an archive. Defaults to contents of the "
            "'pathname' variable, for example as is set by "
            "URLDownloader.",
        },
        "destination_path": {
            "required": False,
            "description": (
                "Directory where archive will be unpacked, created "
                "if necessary. Defaults to RECIPE_CACHE_DIR/NAME."
            ),
        },
        "purge_destination": {
            "required": False,
            "description": "Whether the contents of the destination directory "
            "will be removed before unpacking.",
        },
        "archive_format": {
            "required": False,
            "description": (
                "The archive format. Currently supported: 'zip', "
                "'tar_gzip', 'tar_bzip2', 'tar', '7z'. If omitted, the "
                "file extension is used to guess the format."
            ),
        },
        "7z_unarchiver_path": {
            "required": False,
            "description": "Path to the p7zip 7zr unarchiver (not macOS standard, need to be provided by another way)",
        },
    }
    output_variables = {}

    def get_archive_format(self, archive_path):
        """Guess archive format based on filename extension."""
        for format_str, extns in EXTNS.items():
            for extn in extns:
                if archive_path.endswith(extn):
                    return format_str
        # We found no known archive file extension if we got this far
        return None

    def main(self):
        """Unarchive a file."""
        # handle some defaults for archive_path and destination_path
        archive_path = self.env.get("archive_path", self.env.get("pathname"))
        if not archive_path:
            raise ProcessorError(
                "Expected an 'archive_path' input variable but none is set!"
            )
        destination_path = self.env.get(
            "destination_path",
            os.path.join(self.env["RECIPE_CACHE_DIR"], self.env["NAME"]),
        )

        # Create the directory if needed.
        if not os.path.exists(destination_path):
            try:
                os.makedirs(destination_path)
            except OSError as err:
                raise ProcessorError(f"Can't create {destination_path}: {err.strerror}")
        elif self.env.get("purge_destination"):
            for entry in os.listdir(destination_path):
                path = os.path.join(destination_path, entry)
                try:
                    if os.path.isdir(path) and not os.path.islink(path):
                        shutil.rmtree(path)
                    else:
                        os.unlink(path)
                except OSError as err:
                    raise ProcessorError(f"Can't remove {path}: {err.strerror}")

        fmt = self.env.get("archive_format")
        if fmt is None:
            fmt = self.get_archive_format(archive_path)
            if not fmt:
                raise ProcessorError(
                    f"Can't guess archive format for filename {os.path.basename(archive_path)}"
                )
            self.output(
                f"Guessed archive format '{fmt}' from filename {os.path.basename(archive_path)}"
            )
        elif fmt not in EXTNS:
            raise ProcessorError(
                f"'{fmt}' is not valid for the 'archive_format' variable. "
                f"Must be one of {', '.join(EXTNS)}."
            )

        if fmt == "zip":
            cmd = [
                "/usr/bin/ditto",
                "--noqtn",
                "-x",
                "-k",
                archive_path,
                destination_path,
            ]
        elif fmt == "gzip":
            cmd = ["/usr/bin/ditto", "--noqtn", "-x", archive_path, destination_path]
        elif fmt == "7z":
            cmd_7z = self.env.get("7z_unarchiver_path")
            if not cmd_7z:
                raise ProcessorError(
                    "Expected an '7z_unarchiver_path' input variable since file format is 7z!"
                )
            cmd = [cmd_7z, "x", archive_path, "-o" + destination_path]
        elif fmt.startswith("tar"):
            cmd = ["/usr/bin/tar", "-x", "-f", archive_path, "-C", destination_path]
            if fmt.endswith("gzip"):
                cmd.append("-z")
            elif fmt.endswith("bzip2"):
                cmd.append("-j")

        # Call the shell command.
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            raise ProcessorError(
                f"Unarchiving {archive_path} with {os.path.basename(cmd[0])} failed: {proc.stderr}"
            )

        self.output(f"Unarchived {archive_path} to {destination_path}")


if __name__ == "__main__":
    PROCESSOR = Zoom7zUnarchiver()
    PROCESSOR.execute_shell()
