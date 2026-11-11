import hashlib
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import configuration, WaterClient, WaterError


class WaterConfigFlow(config_entries.ConfigFlow, domain="shenzhen_water"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                config = configuration(user_input["session_json"])
                client = WaterClient(async_get_clientsession(self.hass), config)
                await client.refresh()
                config = client.config
                identity = hashlib.sha256(config["templates"]["token"]["customercode"].encode()).hexdigest()
                await self.async_set_unique_id(identity)
                if self.source == "reauth":
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(self._get_reauth_entry(), data_updates=config)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="深圳水务", data=config)
            except WaterError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Required("session_json"): str}), errors=errors)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_user()
