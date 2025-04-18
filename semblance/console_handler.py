from __future__ import annotations
import asyncio
import time

from queue import Queue, Empty
from pathlib import Path
from typing import Optional
from threading import Thread

from loguru import logger

from semblance.control_messages import AbstractControlMessage, DummyMessage, KillMessage
from semblance.game_event_messages import AbstractGameEventMessage, ConsoleEventMessage


def tf2_console_handler(reader: TF2ConsoleReader) -> None:
    logger.info("Console Handler starting...")
    async_el = asyncio.new_event_loop()

    async_el.run_until_complete(reader.start_watching())

    logger.debug(f"Ending async event loop...")
    async_el.stop()
    async_el.close()
    logger.success("Console Handler finishing...")


class TF2ConsoleReader:
    # Path to the console.log file
    file_path: Path = None
    output_queue: Queue[AbstractGameEventMessage] = None
    control_queue: Queue[AbstractControlMessage] = None

    # File watching stuff
    _seek_offset: int = None
    _last_check: float = None

    def __init__(
            self,
            output_queue: Queue[AbstractGameEventMessage],
            control_queue: Queue[AbstractControlMessage],
            file_path: Path
    ) -> None:
        self.file_path = file_path
        self.output_queue = output_queue
        self.control_queue = control_queue

    def _check_control(self) -> Optional[AbstractControlMessage]:
        try:
            _control_msg = self.control_queue.get(block=False)
            return _control_msg  # Remember to use task_done later!!
        except Empty:
            return None  # no control messages right now...

    async def start_watching(self) -> None:
        self._seek_offset = self.file_path.stat().st_size
        _file_handle = open(self.file_path, 'r')
        _file_handle.seek(self._seek_offset)

        while True:
            _data = _file_handle.read().strip()
            if _data:
                for line in _data.splitlines():
                    if len(line.strip()) < 1:
                        continue
                    self.output_queue.put(
                        ConsoleEventMessage(line, self.file_path.name, self.__class__.__name__),
                        block=True
                    )

            _msg = self._check_control()
            if _msg:
                if isinstance(_msg, KillMessage):
                    logger.info(f"KillMessage received, breaking watcher...")
                    self.control_queue.task_done()
                    break
                elif isinstance(_msg, DummyMessage):
                    # DummyMessage, ignore it! (but still make sure to mark task_done)
                    self.control_queue.task_done()
                else:
                    # do nothing
                    self.control_queue.task_done()

            await asyncio.sleep(0.1)

        _file_handle.close()
        logger.info(f"Exiting file watching loop...")


def main():
    _control_queue = Queue()
    _control_queue.put(DummyMessage("MainTestThread-init"))
    _output_queue = Queue()
    _path = Path("G:\\SteamLibrary\\steamapps\\common\\Team Fortress 2\\tf\\console.log")
    _watcher = TF2ConsoleReader(_output_queue, _control_queue, _path)

    _thread = Thread(
        target=tf2_console_handler,
        name="TF2AsyncConsoleWatchingThread",
        args=(_watcher,)
    )
    _thread.start()

    _control_queue.join()
    try:
        while True:
            try:
                _msg = _output_queue.get(block=False)
                print(_msg)
                _output_queue.task_done()
            except Empty:
                # no messages...
                pass

            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info(f"Keyboard interrupt detected, exiting...")

    _control_queue.put(KillMessage("ConsoleHandlerMainTestLoop"), block=True)
    _control_queue.join()
    _thread.join()


if __name__ == "__main__":
    main()
