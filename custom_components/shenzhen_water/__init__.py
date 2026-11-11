import logging
from datetime import timedelta
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import WaterClient, WaterError, WaterAuthError

DOMAIN = "shenzhen_water"


class WaterCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, logging.getLogger(__name__), name=DOMAIN,
                         config_entry=entry, update_interval=timedelta(hours=6))
        self.client = WaterClient(async_get_clientsession(hass), entry.data)
        self.entry = entry

    async def _async_update_data(self):
        try:
            data = await self.client.refresh()
            if self.client.config["headers"] != self.entry.data["headers"]:
                self.hass.config_entries.async_update_entry(
                    self.entry, data={**self.entry.data, "headers": dict(self.client.config["headers"])}
                )
            return data
        except WaterAuthError as error:
            raise ConfigEntryAuthFailed(str(error)) from None
        except WaterError as error:
            raise UpdateFailed(str(error)) from None


async def async_setup_entry(hass, entry):
    coordinator = WaterCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, ["sensor"])
