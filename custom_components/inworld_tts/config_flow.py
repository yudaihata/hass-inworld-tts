"""Config flow for Inworld AI TTS integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import InworldTTSConfigEntry
from .const import (
    CONF_MODEL,
    DEFAULT_MODEL,
    DOMAIN,
    INWORLD_VOICES_API_URL,
    MODELS,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_api_key(hass, api_key: str) -> str | None:
    """Validate API key by listing voices. Returns error key or None."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            INWORLD_VOICES_API_URL,
            headers={"Authorization": f"Basic {api_key}"},
            params={"pageSize": 1},
        ) as resp:
            if resp.status in (401, 403):
                return "invalid_api_key"
            if resp.status not in (200, 201):
                _LOGGER.debug("Inworld voices API returned HTTP %s", resp.status)
                return "unknown"
    except Exception:
        _LOGGER.exception("Error connecting to Inworld AI")
        return "cannot_connect"
    return None


class InworldTTSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Inworld AI TTS."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await _validate_api_key(self.hass, user_input[CONF_API_KEY])
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="Inworld AI Speech",
                    data={CONF_API_KEY: user_input[CONF_API_KEY]},
                    options={CONF_MODEL: user_input.get(CONF_MODEL, DEFAULT_MODEL)},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(CONF_MODEL, default=DEFAULT_MODEL): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(label=label, value=model_id)
                            for model_id, label in MODELS.items()
                        ]
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: InworldTTSConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return InworldTTSOptionsFlow()


class InworldTTSOptionsFlow(OptionsFlow):
    """Inworld AI TTS options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="Inworld AI Speech", data=user_input)

        current_model = self.config_entry.options.get(CONF_MODEL, DEFAULT_MODEL)

        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(CONF_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(label=label, value=model_id)
                                for model_id, label in MODELS.items()
                            ]
                        )
                    ),
                }
            ),
            {CONF_MODEL: current_model},
        )

        return self.async_show_form(step_id="init", data_schema=schema)
