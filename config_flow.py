"""Config flow for Weatherflow."""
import logging
from homeassistant.helpers import config_entry_flow
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN
from homeassistant import data_entry_flow
from collections import OrderedDict
from typing import Optional
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

class WeatherflowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH
    async def async_step_user(self, user_input=None):
        # Use OrderedDict to guarantee order of the form shown to the user
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        data_schema = OrderedDict()

        return self.async_show_form(
            step_id='confirm',
            data_schema=vol.Schema(data_schema)
        )
    async def async_step_confirm(self, user_input=None):
        return self.async_create_entry(title="Weatherflow", data={})

    async def async_step_import(self, user_input=None):
        return self.async_create_entry(title="Weatherflow", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return None