import time
from queue import Queue, Empty
from threading import Thread
from asyncio import sleep, wait_for, TimeoutError, new_event_loop, set_event_loop
from typing import Awaitable, Any

# noinspection PyPackageRequirements
from buttplug import Client, ProtocolSpec, WebsocketConnector, Device
# noinspection PyPackageRequirements
from buttplug.errors.client import WebsocketTimeoutError
# noinspection PyPackageRequirements
from buttplug.client.client import Actuator, LinearActuator, RotatoryActuator
from loguru import logger

from semblance.control_messages import KillMessage, AbstractControlMessage, DummyMessage
from semblance.device_messages import NormalActuatorSetIntensityMessage, ActuatorTypes, AbstractDeviceMessage


async def await_with_timeout(awaitable_element: Awaitable, timeout: float, msg: str = "<anonymous>") -> Any:
    try:
        result = await wait_for(awaitable_element, timeout)
        return result
    except TimeoutError as e:
        logger.debug(f"Task '{msg}' timed out - {e}")
        return None


def handle_toy_client(
        client_addr: str,
        client_port: int,
        message_queue: Queue[AbstractDeviceMessage],
        control_queue: Queue[AbstractControlMessage]
) -> None:
    # Setup asyncio loops for this Thread
    _async_el = new_event_loop()
    set_event_loop(_async_el)

    _client = ToyClientManager(client_addr, client_port)
    _async_el.run_until_complete(_client.handshake())
    while len(_client.client.devices) < 1:
        logger.error(f"No connected devices were found... scanning...")
        _async_el.run_until_complete(_client.scan_devices())

    logger.success(f"Connected with {len(_client.client.devices)} devices.")
    _active_dev = _client.target_device
    if len(_client.client.devices) > 1:
        logger.warning(f"Note that we do not support choosing device in-app - disconnect the other devices. "
                       f"Defaulting to the first device...")

    logger.success(f"Proceeding with '{_active_dev.name}' with:\n"
                   f"  - {len(_active_dev.actuators)} regular actuators\n"
                   f"  - {len(_active_dev.rotatory_actuators)} rotary actuators\n"
                   f"  - {len(_active_dev.linear_actuators)} linear actuators\n"
                   f"  - and {len(_active_dev.sensors)} sensors.")

    _last_connection_check = time.time()
    while True:
        # ================================================
        # Control the handler...
        # ------------------------------------------------
        try:
            _control_msg = control_queue.get(block=False)
            if isinstance(_control_msg, KillMessage):
                logger.info(f"Received kill signal from {_control_msg.generator}. Ending...")
                break
            elif isinstance(_control_msg, DummyMessage):
                pass  # DummyMessage, ignore it! (but still make sure to mark task_done)
            else:
                logger.warning(f"handle_toy_client loop received control message '{_control_msg.name}' but cannot "
                               f"handle it. Ignoring...")

            control_queue.task_done()
        except Empty:
            pass  # no control messages right now...
        # ================================================
        try:
            _message = message_queue.get(block=False)
            if isinstance(_message, NormalActuatorSetIntensityMessage):
                logger.debug(f"Received a regular actuator set command: {_message.name}")
                match _message.target:
                    case ActuatorTypes.NORMAL:
                        _async_el.run_until_complete(_client.apply_normal_intensity(_active_dev, _message.value))
                        _last_connection_check = time.time()
                    case _:
                        logger.error(f"Received a NormalActuatorSetIntensity message, but the target was not a NORMAL "
                                     f"actuator. target={_message.target}, name={_message.name}.")

            message_queue.task_done()
        except Empty:
            _time_now = time.time()
            if _time_now - _last_connection_check > 5:
                logger.info(f"running scheduled connection check.")
                _async_el.run_until_complete(_client.ensure_connected())
                _last_connection_check = _time_now

    logger.info(f"Exiting the ToyClientHandler loop...")

    logger.debug(f"Killing the Intiface Client connection...")
    _async_el.run_until_complete(_client.client.stop_all())
    _async_el.run_until_complete(_client.client.disconnect())

    logger.debug(f"Killing the Async Event loop...")
    _async_el.stop()
    _async_el.close()

    logger.info(f"ToyClientHandler is closed! Goodbye.")
    return


class ToyClientManager:
    client: Client = None
    _address: str = None
    connector: WebsocketConnector = None
    devices: list[Device] = None
    target_device: Device = None

    def __init__(self, websocket_address: str = "127.0.0.1", websocket_port: int = 12345) -> None:
        self.devices = []
        self.client = Client("Semblance Client", ProtocolSpec.v3)
        self._address = f"ws://{websocket_address}:{websocket_port}"
        self.connector = WebsocketConnector(self._address)

    async def scan_devices(self) -> None:
        if self.client is None or not self.client.connected:
            logger.error(f"Cannot scan for devices with a null client/unconnected client.")
            raise ValueError(f"Client not in valid state for scanning.")

        logger.info(f"Scanning for devices...")
        await self.client.start_scanning()
        await sleep(3.0)
        await self.client.stop_scanning()
        logger.success(f"Finished scan. Found {len(self.client.devices)} devices.")
        self.target_device = list(self.client.devices.values())[0]

    async def handshake(self) -> None:
        if self.connector is None:
            logger.error(f"Cannot perform handshake connect because connector is not defined.")
            raise ValueError(f"Connector is None.")

        if self.connector.connected:
            logger.info(f"Existing connection found - resetting connection.")
            await await_with_timeout(self.client.stop_all(), 5.0, "Client StopAll")
            await self.client.disconnect()

        try:
            await self.client.connect(self.connector)
        except Exception as e:
            logger.error(f"Could not connect to WS server at {self.connector} because '{e}'. Aborting.")
            raise WebsocketTimeoutError(self._address)

        await self.scan_devices()
        self.devices = list(self.client.devices.values())

    async def ensure_connected(self) -> bool:
        if not self.client.connected:
            logger.warning(f"Client is in a disconnected state. Issuing reconnect")
            try:
                await await_with_timeout(self.client.reconnect(), 1.0, "Client Reconnect")
                return True
            except TimeoutError:
                logger.error(f"Client failed to reconnect (timed out).")
                return False
        return True

    async def apply_normal_intensity(self, device: Device, intensity: float) -> None:
        """
        Wraps self.apply_intensity, providing a tuple for the regular argument, and no others.

        :param device: The device to apply this intensity to.
        :param intensity: a float between 0 and 1 inclusive for the intensity value
        :return: None
        """
        await self.apply_intensity(device, regular=(intensity,))

    async def apply_intensity(
            self,
            device: Device,
            regular: tuple | None = None,
            rotary: tuple | None = None,
            linear: tuple | None = None
    ) -> None:
        """
        Apply a command ('intensity') to a set of actuators on the given device. If the device disconnects or the
        commands fully time out, this method will abort attempting to apply the commands to any other actuator in the
        same group. If the device disconnects, there are 3 reconnect attempts before the command is aborted. If a
        command times out, the device is checked for its connection status. If a command times out 3 times, the command
        is aborted.

        :param device: The device to run commands against.
        :param regular: If not None, will use this argument as an arg tuple for applying intensity to all regular
                        actuators on this device. If None, no regular actuators are commanded.
        :param rotary: If not None, will use this argument as an arg tuple for applying intensity to all rotary
                        actuators on this device. If None, no rotary actuators are commanded.
        :param linear: If not None, will use this argument as an arg tuple for applying intensity to all linear
                        actuators on this device. If None, no linear actuators are commanded.
        :return: None
        """
        logger.debug(f"Applying intensity for {device.name}.")
        if regular:
            for act in device.actuators:
                _val = await self._apply_intensity(act, *regular)
                if not _val:
                    logger.error(f"Could not send command for a 'regular' actuator - aborted.")
                    break  # Abort - something went wrong, and we really couldn't run the commands...
        if rotary:
            for rotact in device.rotatory_actuators:
                _val = await self._apply_intensity(rotact, *rotary)
                if not _val:
                    logger.error(f"Could not send command for a rotary actuator - aborted.")
                    break  # Abort - something went wrong, and we really couldn't run the commands...
        if linear:
            for linact in device.linear_actuators:
                _val = await self._apply_intensity(linact, *linear)
                if not _val:
                    logger.error(f"Could not send command for a linear actuator - aborted.")
                    break  # Abort - something went wrong, and we really couldn't run the commands...

    async def _apply_intensity(self, actuator: Actuator | LinearActuator | RotatoryActuator, *args) -> bool:
        """
        Applies the given args to the provided actuator, dynamically picking the applicator function based on Actuator
        type.

        If the given actuator is not normal, linear or rotary, nothing is done.

        If the command times out, it will retry it up to 3 times. If the client detects a disconnected state,
        it will attempt a reconnect up to 3 times.

        :param actuator: an 'Actuator' object from a Device - can be a normal, linear or rotary.
        :param args: For a regular actuator, this is just an intensity value 0<=x<=1
                     For a linear actuator, this is an integer duration, and floating position
                     For a rotary actuator, this is a floating speed, and bool for clockwise (false is CCW)
        :return: None
        """
        _retry_attempt = 1
        _extra_go_tried = False
        _max_retries = 3
        while _retry_attempt <= _max_retries:
            try:
                if isinstance(actuator, Actuator):
                    await self._apply_intensity_actuator(actuator, *args)
                elif isinstance(actuator, RotatoryActuator):
                    await self._apply_intensity_rotary(actuator, *args)
                elif isinstance(actuator, LinearActuator):
                    await self._apply_intensity_linear(actuator, *args)
                else:
                    logger.warning(f"Attempted to apply intensity on a non-actuator object: {actuator}.")
                    # do nothing
                return True
            except TimeoutError:
                logger.warning(f"Timed out attempting to apply an intensity to an actuator. "
                               f"(attempt {_retry_attempt}/{_max_retries})")
                _reconnect_attempts = 1
                _max_reconnect_retries = 3
                _success = False
                while _reconnect_attempts <= _max_reconnect_retries:
                    _res = await self.ensure_connected()
                    if _res:
                        logger.success(f"Reconnected successfully.")
                        _success = True
                        break
                    else:
                        _reconnect_attempts += 1
                if not _success:
                    # Abort attempt at applying intensity - reconnect failed.
                    logger.error(f"Could not connect to device, aborting intensity application.")
                    return False
                # If we 'succeed' on the reconnect, but we have already tried the max num of times, we get one 'extra'
                # go to attempt to apply the intensity.
                if _success and _retry_attempt == _max_retries and not _extra_go_tried:
                    _extra_go_tried = True
                else:
                    _retry_attempt += 1
        return False

    @staticmethod
    async def _apply_intensity_actuator(actuator: Actuator, intensity_value: float) -> None:
        _inten = intensity_value
        if not 0.0 <= _inten <= 1.0:
            logger.warning(f"given intensity value is out of range, clamping!")
            _inten = max(0.0, min(1.0, _inten))

        await await_with_timeout(actuator.command(_inten), 0.3)

    @staticmethod
    async def _apply_intensity_rotary(actuator: RotatoryActuator, speed: float, clockwise: bool = True) -> None:
        await await_with_timeout(actuator.command(speed, clockwise), 0.3)

    @staticmethod
    async def _apply_intensity_linear(actuator: LinearActuator, duration: int, position: float) -> None:
        await await_with_timeout(actuator.command(duration, position), 0.3)


def print_main_control_help():
    print("Test Control Loop Commands:")
    print("  help        - print this message")
    print("  exit        - exit the loop, send the kill signal to the handlers.")
    print("  set [float] - set the intensity on the connected toy to the given value (float between 0 and 1)")
    print("  get         - get (print) the current intensity value")
    return


def main():
    _control_queue = Queue()
    _control_queue.put(DummyMessage("MainTestThread-init"))
    _message_queue = Queue()
    _url = "localhost"
    _port = 12345
    logger.info("Starting toy client thread...")
    _control_thread = Thread(
        target=handle_toy_client,
        name="IntifaceToyClientHandlerThread",
        args=(_url, _port, _message_queue, _control_queue)
    )
    _control_thread.start()
    logger.success(f"Thread '{_control_thread.name}' started.")

    _control_queue.join()
    while True:
        try:
            _input = input("Enter Command >> ").strip().lower()
        except EOFError:
            logger.info("EOF detected. Exiting...")
            break
        if len(_input) < 1:
            continue

        _words = _input.split()
        match _words[0]:
            case "help":
                print_main_control_help()
            case "exit":
                break
            case "get":
                pass
            case "set":
                if not len(_words) > 1:
                    print(f"Provide a float value! e.g.: set 0.34")
                else:
                    try:
                        _val = float(_words[1])
                        _msg = NormalActuatorSetIntensityMessage(_val, "MainTestLoop(setCommand)")
                        _message_queue.put(_msg, block=True)
                    except ValueError:
                        print(f"Error - {_words[1]} is not a valid float value!")

    _message_queue.join()
    _control_queue.put(KillMessage("MainTestMethod"), block=True)
    _control_thread.join()
    logger.success(f"KillMessage successful, exiting now, bye bye!")
    return


if __name__ == "__main__":
    main()
