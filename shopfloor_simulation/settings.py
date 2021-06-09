"""
    User configuration can be set here.
"""

from dotenv import dotenv_values

# secrets = {"USER": "foo", "EMAIL": "foo@example.org"}
secrets = dotenv_values(".env")


''' MQTT Connection setup. '''
# Public brokers: https://github.com/mqtt/mqtt.org/wiki/public_brokers
MQTT_HOST = "mqtt.flespi.io"  # "mqtt.flespi.io"
MQTT_PORT = 1883
MQTT_USERNAME = secrets["MQTT_USERNAME"]
MQTT_PASSWORD = secrets["MQTT_PASSWORD"]
MQTT_CLIENT_ID = "Shopfloor-Simulation-"  # A random number will be appended
ROOT_TOPIC = "freeaimTwin/StateMachine/"  # The start of every topic used
