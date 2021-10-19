# Copyright © 2021 Deltares
# SPDX-License-Identifier: GPL-2.0-or-later
#
"""
This module contains the logic for starting, communicating with, and killing a
seperate interpreter.

Modified from: 
https://gitlab.com/deltares/imod/qgis-tim/-/blob/master/plugin/qgistim/server_handler.py
"""
import json
import os
import platform
import signal
import socket
import subprocess
from contextlib import closing
from pathlib import Path

from ..utils.pathing import get_configdir


class Server:
    def __init__(self):
        self.HOST = "127.0.0.1"  # = localhost in IPv4 protocol
        self.PORT = None
        self.socket = None

    def find_free_port(self) -> int:
        """
        Finds a free localhost port number.

        Returns
        -------
        portnumber: int
        """
        # from:
        # https://stackoverflow.com/questions/1365265/on-localhost-how-do-i-pick-a-free-port-number
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.bind(("localhost", 0))
            return sock.getsockname()[1]

    def start_server(self) -> None:
        self.PORT = self.find_free_port()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.HOST, self.PORT))
        self.socket.listen(4)

    def accept_client(self):
        self.client, address = self.socket.accept()

    def start_imod(self, viewer_exe) -> None:
        """
        Starts imod, based on the settings in the
        configuration directory.
        """

        configdir = get_configdir()

        # Overwrite command log
        with open(configdir / "xml_commands.log", "w") as f:
            f.write("")

        with open(configdir / "viewer_exe.txt") as f:
            viewer_exe = f.read().strip()

        # Copy environmental variables
        # These are provided to the Popen, to ensure the right environmental
        # variables are used.
        env_vars = {key: value for key, value in os.environ.items()}

        hostAddress = f"{self.HOST}:{self.PORT}"

        subprocess.Popen([viewer_exe, "--hostAddress", hostAddress], env=env_vars)

    def send(self, data) -> str:
        """
        Send a data package (should be a XML string) to the viewer to command it from Qgis

        Parameters
        ----------
        data: str
            A XML string describing the operation and parameters

        Returns
        -------
        received: str
            Value depends on the requested operation
        """

        configdir = self.get_configdir()
        with open(configdir / "xml_commands.log", "a") as f:
            f.write(data)
            f.write("\n\n")

        self.client.sendall(bytes(data, "utf-8"))
        # Receive data from viewer, serves as a blocking call, so that sent requests are not piled up
        received = str(self.client.recv(1024), "utf-8")
        return received

    def kill(self) -> None:
        """
        Kills the external interpreter.

        This enables shutting down the external window when the plugin is
        closed.
        """
        if self.PORT is not None:
            # Ask the process for its process_ID
            try:
                data = json.dumps({"operation": "process_ID"})
                process_ID = int(self.send(data))
                # Now kill it
                os.kill(process_ID, signal.SIGTERM)
            except ConnectionRefusedError:
                # it's already dead
                pass
