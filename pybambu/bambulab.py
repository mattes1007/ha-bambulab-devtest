"""Asynchronous Python client for Bambu Lab Printers."""
from __future__ import annotations

import json
import asyncio
import logging

from dataclasses import dataclass
from paho.mqtt import client as mqtt_client

from .models import Device

from .exceptions import (
    BambuLabError,
    BambuLabConnectionError,
    BambuLabConnectionClosed,
    BambuLabUnsupportedFeature,
    BambuLabConnectionTimeoutError
)

LOGGER = logging.getLogger(__name__)


@dataclass
class BambuLab:
    """Main class for handling connections with Bambu Printers."""

    host: str
    _client: mqtt_client.Client | None = None
    _close_session: bool = False
    _device: Device | None = None

    def on_connect(self, client, userdata, flags, rc):
        LOGGER.debug("Connected with result code " + str(rc))

        if rc == 0:
            LOGGER.debug("Connected to MQTT Broker!")
        else:
            LOGGER.debug("Failed to connect, return code %d\n", rc)

    async def connect(self):
        """ Connect to the MQTT Server of a Bambu Printer

        Raises:
            BambuLabConnectionError: Error occurred while communicating with Bambu Printer
        """

        LOGGER.debug(f"Connecting MQTT Server on: {self.host}")
        self._client = mqtt_client.Client()
        self._client.on_connect = self.on_connect
        self._client.connect(self.host, 1883)
        self._client.loop_start()
        return self._client

    async def subscribe(self, callback):
        def on_message(client, userdata, msg):
            LOGGER.debug("Subscribe received message")
            if self._device is None:
                self._device = Device(json.loads(msg.payload))

            self._device.update_from_dict(data=json.loads(msg.payload))
            LOGGER.debug('Device Update')
            return callback(self._device)

        LOGGER.debug("Subscribing ")
        self._client.on_message = on_message
        self._client.subscribe("device/#")
        return

    async def disconnect(self):
        """Disconnect from the MQTT Server of a Bambu Printer."""
        if not self._client:
            LOGGER.debug("Cannot disconnect from MQTT Server, as no client connection exists")
            return

        LOGGER.debug("Disconnecting....")
        self._client.loop_stop()
        self._client.disconnect()
        LOGGER.debug("Disconnected")
        return

    async def get_device(self):
        device = None

        def new_update(cb):
            nonlocal device
            LOGGER.debug(f"new update {cb.__dict__}")
            device = cb

        await self.connect()
        asyncio.create_task(self.subscribe(callback=new_update))
        await asyncio.sleep(5)
        await self.disconnect()
        return device

    async def __aenter__(self):
        """Async enter.

        Returns:
            The BambuLab object.
        """
        return self

    async def __aexit__(self, *_exc_info):
        """Async exit.

        Args:
            _exc_info: Exec type.
        """
        await self.disconnect()
