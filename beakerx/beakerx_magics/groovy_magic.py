# Copyright 2017 TWO SIGMA OPEN SOURCE, LLC  #
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from queue import Empty
from IPython import get_ipython
from IPython.core.magic import (Magics, magics_class, cell_magic)
from jupyter_client.manager import KernelManager
import atexit


@magics_class
class GroovyMagics(Magics):
    _execution_count = 1

    def stop_kernel(self):
        self.kc.stop_channels()
        self.km.shutdown_kernel(now=True)

    def __init__(self, shell):
        super(GroovyMagics, self).__init__(shell)
        self.km = None
        self.kc = None
        self.comms = []

    def start(self):
        self.km = KernelManager()
        self.km.kernel_name = 'groovy'
        self.km.start_kernel()
        atexit.register(self.stop_kernel)
        self.kc = self.km.client()
        self.kc.start_channels()
        try:
            self.kc.wait_for_ready()
            print("Groovy started successfully\n")
        except AttributeError:
            self._wait_for_ready_backport()

    def run_cell(self, line, code):
        if not self.km:
            self.start()
        self.kc.execute(code, allow_stdin=True)
        reply = self.kc.get_shell_msg()
        self._handle_iopub_messages()

    def _handle_iopub_messages(self):
        while True:
            try:
                msg = self.kc.get_iopub_msg(timeout=1)
            except Empty:
                break
            comm_id = msg['content'].get('comm_id')
            if comm_id and comm_id not in self.comms:
                self.comms.append(comm_id)
            self.shell.kernel.session.send(self.shell.kernel.iopub_socket, msg['msg_type'],
                                           msg['content'],
                                           metadata=msg['metadata'],
                                           parent=self.shell.kernel._parent_header,
                                           ident=msg.get('comm_id'),
                                           buffers=msg['buffers'],
                                           )

    def pass_message(self, msg_raw):
        comm_id = msg_raw['content'].get('comm_id')
        if comm_id in self.comms:
            content = msg_raw['content']
            msg = self.kc.session.msg(msg_raw['msg_type'], content)
            self.kc.shell_channel.send(msg)
            self._handle_iopub_messages()
        else:
            self.log.warn("No such comm: %s", comm_id)
            if self.log.isEnabledFor(logging.DEBUG):
                # don't create the list of keys if debug messages aren't enabled
                self.log.debug("Current comms: %s", list(self.comms.keys()))

    @cell_magic
    def groovy(self, line, cell):
        return self.run_cell(line, cell)


def load_ipython_extension(ipython):
    ipython.register_magics(GroovyMagics)


if __name__ == '__main__':
    ip = get_ipython()
    ip.register_magics(GroovyMagics)
