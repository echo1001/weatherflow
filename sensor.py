import logging
from .const import DOMAIN

import threading
import socket
import time
import json
from datetime import datetime
import homeassistant.helpers.device_registry as dr
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, SPEED_MS, CONF_UNIT_SYSTEM_IMPERIAL, ILLUMINANCE, DEVICE_CLASS_ILLUMINANCE, UNIT_UV_INDEX, PRESSURE_MBAR, DEVICE_CLASS_PRESSURE, TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_SIGNAL_STRENGTH, PRESSURE_INHG


_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    #async_add_entities([Temp()])

    listener = WFListener(hass, config_entry, async_add_entities)
    listener.start()
    
    async def async_stop_listener(_event):
        listener.stopped.set()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_listener)

class WFSensor(Entity):
    def __init__(self, field, name, store, controller, hass):
        self._field = field
        self._name = name
        self._store = store
        self.controller = controller
        self.hass: HomeAssistant = hass

    async def async_added_to_hass(self):
        self._store.entities.append(self)
        self.push_update()

    def get_state(self):
        return self._store.data[self._field]

    def push_update(self):
        self.async_schedule_update_ha_state()

    @property
    def should_poll(self):
        return False

    @property
    def force_update(self):
        return True

    @property
    def unique_id(self):
        return self.controller.sn + "_" + self._field
        
    @property
    def device_state_attributes(self):
        attr = {}

        if "timestamp" in self._store.data and not self._store.data["timestamp"] is None:
            attr["Report Time"] = datetime.fromtimestamp(self._store.data["timestamp"])

        if "energy" in self._store.data:
            attr["Energy"] = self._store.data["energy"]

        if "report_interval" in self._store.data:
            attr["Report Interval"] = self._store.data["report_interval"]

        return attr

    @property
    def device_info(self):
        return {
            'identifiers': {
                (DOMAIN, self.controller.sn)
            },
            'name': self.controller._hubname,
            'manufacturer': "Weatherflow",
            'model': "",
            'sw_version': "",
            'via_device': (DOMAIN, self.controller.hub),
        }

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self.get_state()

class WindSensor(WFSensor):
    
    @property
    def unit_of_measurement(self):
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            return "mph"

        return "m/s"

    @property
    def icon(self):
        return 'mdi:weather-windy'

    @property
    def state(self):
        if self.get_state() is None:
            return None
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            return round(self.get_state() * 2.23694, 2)
        return self.get_state()

class WindDirection(WFSensor):

    @property
    def icon(self):
        return 'mdi:compass'

    @property
    def device_state_attributes(self):
        attr = {}

        if "timestamp" in self._store.data and not self._store.data["timestamp"] is None:
            attr["Report Time"] = datetime.fromtimestamp(self._store.data["timestamp"])

        if "energy" in self._store.data:
            attr["Energy"] = self._store.data["energy"]

        if "report_interval" in self._store.data:
            attr["Report Interval"] = self._store.data["report_interval"]

        attr['Direction'] = self.get_state()
        return attr

    @property
    def state(self):
        state = self.get_state()
        if state is None:
            return None

        val=int((state/22.5)+.5)
        arr=["N","NNE","NE","ENE","E","ESE", "SE", "SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
        return arr[(val % 16)]

class IlluminanceSensor(WFSensor):
    @property
    def unit_of_measurement(self):
        return ILLUMINANCE

    @property
    def device_class(self):
        return DEVICE_CLASS_ILLUMINANCE

class UV(WFSensor):
    @property
    def unit_of_measurement(self):
        return UNIT_UV_INDEX

    @property
    def icon(self):
        return 'mdi:weather-sunny'

class SolarRadiation(WFSensor):
    @property
    def unit_of_measurement(self):
        return "w/m2"

    @property
    def icon(self):
        return 'mdi:weather-sunny'

class Rain(WFSensor):
    @property
    def unit_of_measurement(self):
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            return 'in'
        return 'mm'

    @property
    def state(self):
        if self.get_state() is None:
            return None
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            return round(self.get_state() / 25.4, 3)
        return self.get_state()

    @property
    def icon(self):
        return 'mdi:water'

class RainRate(WFSensor):

    @property
    def rain_rate(self):
        if self._store.data['rain_accum'] is None or self._store.data['report_interval'] is None:
            return None
        return self._store.data['rain_accum'] / self._store.data['report_interval'] * 60

    @property
    def device_state_attributes(self):
        attr = {}

        if "timestamp" in self._store.data and not self._store.data["timestamp"] is None:
            attr["Report Time"] = datetime.fromtimestamp(self._store.data["timestamp"])

        if "energy" in self._store.data:
            attr["Energy"] = self._store.data["energy"]

        if "report_interval" in self._store.data:
            attr["Report Interval"] = self._store.data["report_interval"]

        if not self.rain_rate is None:
            if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
                attr['Rain Rate'] = round(self.rain_rate / 25.4, 3)
            else:
                attr['Rain Rate'] = self.rain_rate
        return attr

    @property
    def state(self):
        rain_rate = self.rain_rate
        if rain_rate is None:
            return None
        if rain_rate == 0:
            return "None"
        if rain_rate > 0 and rain_rate < 0.25:
            return "Very Light"
        if rain_rate >= 0.25 and rain_rate < 1.0:
            return "Light"
        if rain_rate >= 1.0 and rain_rate < 4.0:
            return "Moderate"
        if rain_rate >= 4.0 and rain_rate < 16.0:
            return "Heavy"
        if rain_rate >= 16.0 and rain_rate < 50.0:
            return "Very Heavy"
        if rain_rate >= 50.0:
            return "Extreme"

    @property
    def icon(self):
        if self.rain_rate is None or self.rain_rate == 0:
            return "mdi:water-off"
        if self.rain_rate >= 4:
            return "mdi:weather-pouring"

        return "mdi:weather-rainy"
    
class Battery(WFSensor):
    @property
    def unit_of_measurement(self):
        return 'V'
        
    @property
    def icon(self):
        return 'mdi:battery'

class Pressure(WFSensor):
    @property
    def unit_of_measurement(self):
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            return PRESSURE_INHG
        return PRESSURE_MBAR

    @property
    def device_class(self):
        return DEVICE_CLASS_PRESSURE

    @property
    def state(self):
        if self.get_state() is None:
            return None
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            return round(self.get_state() / 33.863753, 3)
        return self.get_state()

class Temperature(WFSensor):
    @property
    def unit_of_measurement(self):
        return TEMP_CELSIUS

    @property
    def device_class(self):
        return DEVICE_CLASS_TEMPERATURE

class Humidity(WFSensor):
    @property
    def unit_of_measurement(self):
        return '%'

    @property
    def device_class(self):
        return DEVICE_CLASS_HUMIDITY

class LightningCount(WFSensor):
    @property
    def icon(self):
        return "mdi:flash"

class LightningDistance(WFSensor):
    @property
    def icon(self):
        return "mdi:flash"

    @property
    def unit_of_measurement(self):
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            return 'mi'
        return 'km'

    @property
    def state(self):
        if self.get_state() is None:
            return None
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            return round(self.get_state() / 1.609, 3)
        return self.get_state()

class PrecipType(WFSensor):
    @property
    def state(self):
        if self.get_state() is None:
            return None
        if self.get_state() == 1:
            return 'Rain'
        if self.get_state() == 2:
            return 'Hail'
        return 'None'

    @property
    def icon(self):
        if self.get_state() == 1:
            return 'mdi:weather-rainy'
        if self.get_state() == 2:
            return 'mdi:weather-hail'
        return 'mdi:water-off'

class RSSI(WFSensor):
    @property
    def device_class(self):
        return DEVICE_CLASS_SIGNAL_STRENGTH

class Hub:
    def __init__(self, sn, hass, config_entry):
        self.sn = sn
        self.hass = hass
        self.config_entry = config_entry
        self._hubname = "Weatherflow Hub " + self.sn
    async def setupHub (self):
        device_registry = await dr.async_get_registry(self.hass)

        device_registry.async_get_or_create(
            config_entry_id = self.config_entry.entry_id,
            identifiers={
                (DOMAIN, self.sn)
            },
            name="Weatherflow Hub " + self.sn,
            manufacturer="Weatherflow",
            model="",
            sw_version="",
        )

class Store:
    def __init__(self, init={}):
        self.entities = []
        self.data = init

class Sky:
    def __init__(self, sn, hub, hass, config_entry, async_add_entities):
        self.sn = sn
        self.hub = hub
        self.hass = hass
        self.config_entry = config_entry
        self.async_add_entities = async_add_entities

        self.rapid_wind = Store({'timestamp': None, 'rapid_speed': None, 'rapid_direction': None})
        self.obs_sky = Store({
            'timestamp': None, 
            'illuminance': None, 
            'uv': None, 
            'rain_accum': None, 
            'wind_lull': None, 
            'wind_avg': None, 
            'wind_gust': None, 
            'wind_direction': None, 
            'report_interval': None, 
            'battery': None,
            'solar_radiation': None, 
            'precip_type': None
            })

        self.device_status = Store({
            'timestamp': None,
            'rssi': None
        })

        self.hasObs = False
        self._hubname = "Weatherflow Sky " + self.sn
    async def setupHub (self):
        pass

    async def parseData(self, data):
        if not self.hasObs:
            self.async_add_entities([
                WindSensor("rapid_speed", "Wind Current Speed", self.rapid_wind, self, self.hass),
                WindDirection("rapid_direction", "Wind Current Direction", self.rapid_wind, self, self.hass),
                IlluminanceSensor("illuminance", "Illuminance", self.obs_sky, self, self.hass),
                UV("uv", "UV Index", self.obs_sky, self, self.hass),
                Rain("rain_accum", "Accumulated Rain", self.obs_sky, self, self.hass),
                RainRate("", "Rain Rate", self.obs_sky, self, self.hass),
                WindSensor("wind_lull", "Wind Lull", self.obs_sky, self, self.hass),
                WindSensor("wind_avg", "Wind Average", self.obs_sky, self, self.hass),
                WindSensor("wind_gust", "Wind Gust", self.obs_sky, self, self.hass),
                WindDirection("wind_direction", "Wind Direction", self.obs_sky, self, self.hass),
                Battery("battery", "Battery Voltage", self.obs_sky, self, self.hass),
                SolarRadiation("solar_radiation", "Solar Radiation", self.obs_sky, self, self.hass),
                PrecipType("precip_type", "Precipitation Type", self.obs_sky, self, self.hass),
                RSSI("rssi", "RSSI", self.device_status, self, self.hass),
            ])
            self.hasObs = True

        if data["type"] == "device_status":
            
            if self.device_status.data['timestamp'] != data['timestamp']:
                self.device_status.data['timestamp'] = data['timestamp']
                self.device_status.data['rssi'     ] = data['rssi']

                for sensor in self.device_status.entities:
                    sensor.push_update()

        if data["type"] == "rapid_wind":

            if self.rapid_wind.data['timestamp'] != data['ob'][0]:
                self.rapid_wind.data['timestamp'      ] = data['ob'][0]
                self.rapid_wind.data['rapid_speed'    ] = data['ob'][1]
                self.rapid_wind.data['rapid_direction'] = data['ob'][2]

                for sensor in self.rapid_wind.entities:
                    sensor.push_update()

        if data["type"] == "obs_sky":

            if self.obs_sky.data['timestamp'] != data['obs'][0][0]:

                self.obs_sky.data['timestamp'        ] = data['obs'][0][0]
                self.obs_sky.data['illuminance'      ] = data['obs'][0][1]
                self.obs_sky.data['uv'               ] = data['obs'][0][2]
                self.obs_sky.data['rain_accum'       ] = data['obs'][0][3]
                self.obs_sky.data['wind_lull'        ] = data['obs'][0][4]
                self.obs_sky.data['wind_avg'         ] = data['obs'][0][5]
                self.obs_sky.data['wind_gust'        ] = data['obs'][0][6]
                self.obs_sky.data['wind_direction'   ] = data['obs'][0][7]
                self.obs_sky.data['battery'          ] = data['obs'][0][8]
                self.obs_sky.data['report_interval'  ] = data['obs'][0][9]
                self.obs_sky.data['solar_radiation'  ] = data['obs'][0][10]
                self.obs_sky.data['precip_type'      ] = data['obs'][0][12]

                for sensor in self.obs_sky.entities:
                    sensor.push_update()

class Air:

    def __init__(self, sn, hub, hass, config_entry, async_add_entities):
        self.sn = sn
        self.hub = hub
        self.hass = hass
        self.config_entry = config_entry
        self.async_add_entities = async_add_entities

        self.obs_air = Store({
            'timestamp': None, 
            'pressure': None, 
            'temp': None, 
            'humidity': None, 
            'lightning_count': None, 
            'lightning_avg_dist': None, 
            'battery': None, 
            'report_interval': None})

        self.lightning = Store({
            'timestamp': None, 
            'distance': None, 
            'energy': None})

        self.device_status = Store({
            'timestamp': None,
            'rssi': None
        })

        self.hasObs = False
        self._hubname = "Weatherflow Air " + self.sn
    async def setupHub (self):
        pass

    async def parseData(self, data):
        if not self.hasObs:
            self.async_add_entities([
                Pressure("pressure", "Station Pressure", self.obs_air, self, self.hass),
                Temperature("temp", "Temperature", self.obs_air, self, self.hass),
                Humidity("humidity", "Relative Humidity", self.obs_air, self, self.hass),
                LightningCount("lightning_count", "Lightning Strike Count", self.obs_air, self, self.hass),
                LightningDistance("lightning_avg_dist", "Lightning Average Distance", self.obs_air, self, self.hass),
                Battery("battery", "Battery Voltage", self.obs_air, self, self.hass),
                LightningDistance("distance", "Lightning Strike", self.lightning, self, self.hass),
                RSSI("rssi", "RSSI", self.device_status, self, self.hass),
            ])
            self.hasObs = True

        if data["type"] == "device_status":
            if self.device_status.data['timestamp'] != data['timestamp']:
                self.device_status.data['timestamp'] = data['timestamp']
                self.device_status.data['rssi'] = data['rssi']

                for sensor in self.device_status.entities:
                    sensor.push_update()

        if data["type"] == "obs_air":

            if self.obs_air.data['timestamp'] != data['obs'][0][0]:
                self.obs_air.data['timestamp'         ] = data['obs'][0][0]
                self.obs_air.data['pressure'          ] = data['obs'][0][1]
                self.obs_air.data['temp'              ] = data['obs'][0][2]
                self.obs_air.data['humidity'          ] = data['obs'][0][3]
                self.obs_air.data['lightning_count'   ] = data['obs'][0][4]
                self.obs_air.data['lightning_avg_dist'] = data['obs'][0][5]
                self.obs_air.data['battery'           ] = data['obs'][0][6]
                self.obs_air.data['report_interval'   ] = data['obs'][0][7]

                for sensor in self.obs_air.entities:
                    sensor.push_update()

        if data["type"] == "evt_strike":

            if self.lightning.data['timestamp'] != data['evt'][0]:
                self.lightning.data['timestamp'         ] = data['evt'][0]
                self.lightning.data['distance'          ] = data['evt'][1]
                self.lightning.data['energy'            ] = data['evt'][2]

                for sensor in self.lightning.entities:
                    sensor.push_update()

                hass.bus.fire('lightning_strike', {
                    'sn': self.sn,
                    'hubsn': self.hubsn,
                    'timestamp': datetime.fromtimestamp(data['evt'][0]),
                    'distance': data['evt'][1],
                    'energy': data['evt'][2]
                })


class WFListener(threading.Thread):
    def __init__(self, hass, config_entry, async_add_entities):
        threading.Thread.__init__(self)
        self.daemon = True
        self.hass = hass
        self.config_entry = config_entry

        self.controllers = {}

        self.async_add_entities = async_add_entities
        self.stopped = threading.Event()

    def setupHub(self, data):
        if not data['hub_sn'] in self.controllers:
            self.controllers[data['hub_sn']] = Hub(data['hub_sn'], self.hass, self.config_entry)
            self.hass.async_create_task(self.controllers[data['hub_sn']].setupHub())

    def setupSky(self, data):
        if not data['serial_number'] in self.controllers:
            self.controllers[data['serial_number']] = Sky(
                data['serial_number'], data['hub_sn'], self.hass, self.config_entry, self.async_add_entities)
            self.hass.async_create_task(self.controllers[data['serial_number']].setupHub())

    def setupAir(self, data):
        if not data['serial_number'] in self.controllers:
            self.controllers[data['serial_number']] = Air(
                data['serial_number'], data['hub_sn'], self.hass, self.config_entry, self.async_add_entities)
            self.hass.async_create_task(self.controllers[data['serial_number']].setupHub())


    async def async_prep_payload(self, data):
        #_LOGGER.info(data)
        try:
            type = data['type']
            if type == "device_status":
                if data['serial_number'] in self.controllers:
                    self.hass.async_create_task(self.controllers[data['serial_number']].parseData(data))
            if type == "evt_precip":
                self.setupHub(data)
                self.setupSky(data)
                hass.bus.fire('precip_start', {
                    'sn': data['serial_number'],
                    'hubsn': data['hub_sn'],
                    'timestamp': datetime.fromtimestamp(data['evt'][0])
                })

            if type == "rapid_wind" or type == "obs_sky":
                self.setupHub(data)
                self.setupSky(data)

                self.hass.async_create_task(self.controllers[data['serial_number']].parseData(data))

            if type == "obs_air" or type == "evt_strike":
                self.setupHub(data)
                self.setupAir(data)

                self.hass.async_create_task(self.controllers[data['serial_number']].parseData(data))
        except:
            pass



    def run(self):
        
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setblocking(False)
        s.bind(("", 50222))

        while not self.stopped.isSet():
            try:
                msg=s.recvfrom(1024)
                data=json.loads(msg[0])      # this is the JSON payload

                self.hass.async_create_task(self.async_prep_payload(data))
            except socket.error as ex:
                time.sleep(0.01)
                continue
                    
        s.close()

    def stop(self):
        self._stopped = True        