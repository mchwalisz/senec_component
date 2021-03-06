"""The senec integration."""
import asyncio
import logging
from datetime import timedelta

import async_timeout
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pysenec import Senec

from .const import DEFAULT_HOST, DEFAULT_NAME, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the senec component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up senec from a config entry."""
    session = async_get_clientsession(hass)

    coordinator = SenecDataUpdateCoordinator(hass, session, entry)

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


class SenecDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold Senec data."""

    def __init__(self, hass, session, entry):
        """Initialize."""
        self._host = entry.data[CONF_HOST]
        self.senec = Senec(self._host, websession=session)
        self.name = entry.title

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=60)
        )

    async def _async_update_data(self):
        """Update data via library."""
        with async_timeout.timeout(20):
            await self.senec.update()
        return self.senec


async def async_unload_entry(hass, entry):
    """Unload Senec config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class SenecEntity(Entity):
    """Defines a base Senec entity."""

    def __init__(self, coordinator: SenecDataUpdateCoordinator, sensor: str) -> None:
        """Initialize the Atag entity."""
        self.coordinator = coordinator
        self._sensor = sensor
        self._name = DOMAIN.title()

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        device = self._name
        return {
            "identifiers": {(DOMAIN, device)},
            "name": "Senec Home Battery ",
            "model": "Senec",
            "sw_version": None,
            "manufacturer": "Senec",
        }

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    # @property
    # def unit_of_measurement(self):
    #     """Return the unit of measurement of this entity, if any."""
    #     return self.coordinator.atag.climate.temp_unit

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return f"{self._name}_{self._sensor}"

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update Atag entity."""
        await self.coordinator.async_request_refresh()
