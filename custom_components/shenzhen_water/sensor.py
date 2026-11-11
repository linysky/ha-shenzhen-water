from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([WaterBillSensor(entry)])


class WaterBillSensor(CoordinatorEntity, SensorEntity):
    _attr_name = "深圳水务 最近账单"
    _attr_native_unit_of_measurement = "CNY"
    _attr_icon = "mdi:water"

    def __init__(self, entry):
        super().__init__(entry.runtime_data)
        self._attr_unique_id = f"{entry.entry_id}_bills"
        self._attr_device_info = {"identifiers": {("shenzhen_water", entry.unique_id)},
                                  "name": "深圳水务", "manufacturer": "深圳环境水务集团"}

    @property
    def native_value(self):
        bills = self.coordinator.data["bills"]
        return bills[-1]["totalCost"] if bills else None

    @property
    def extra_state_attributes(self):
        return self.coordinator.data
