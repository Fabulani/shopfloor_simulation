import paho.mqtt.client as mqtt
from time import sleep, perf_counter


''' MQTT Connection setup. '''
# Public brokers: https://github.com/mqtt/mqtt.org/wiki/public_brokers
MQTT_HOST = "mqtt.flespi.io"
MQTT_PORT = 1883
MQTT_USERNAME = ""
MQTT_PASSWORD = ""


class MqttGeneric():
    '''Generic class for MQTT protocol communication'''

    def __init__(self, host=MQTT_HOST, port=MQTT_PORT, username=MQTT_USERNAME, password=MQTT_PASSWORD,
                 run_event_check_sleep: float = 0.1, subscribed_topics: list = [], name="MQTT"):
        self.client = mqtt.Client()
        self.client.username_pw_set(username, password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish
        self.client.connect(host, port, 60)
        self.subscribed_topics = subscribed_topics
        self.run_event_check_sleep = run_event_check_sleep
        self.name = name

    def mqtt_loop(self, run_event):
        '''
            Starts the MQTT communication. Designed to be used with the threading library. Shuts down when the run_event is cleared.
            Example call:

            run_event = threading.Event()
            run_event.set()

            mqtt_manager = MqttManager(MQTT_HOST, MQTT_PORT) 
            mqtt_thread = threading.Thread(target=mqtt_manager.mqtt_loop, args=[run_event])
            mqtt_thread.start()

            If the MQTT Manager will be used just for subscribing and receiving data, then this method will work fine.
            But if the MQTT Manager has to publish data, this method should be overridden to implement that.

            `run_event`: event used to sync thread shutdown.    
        '''
        self.client.loop_start()
        while run_event.is_set():
            sleep(self.run_event_check_sleep)
        self.client.loop_stop()
        print("[" + self.name + "] Shutting down.")

    def on_connect(self, client, userdata, flags, rc):
        '''
            The callback for when the client receives a CONNACK response from the server.
            Subscribing in on_connect() means that if we lose the connection and reconnect then subscriptions will be renewed.
        '''
        print("[" + self.name + "] Connected with result code " + str(rc))
        for topic in self.subscribed_topics:
            client.subscribe(topic)
            print("[" + self.name + "] Subscribed to: " + topic)

    @staticmethod
    def on_message(client, userdata, msg):
        '''The callback for when a PUBLISH message is received from the server.'''
        print("[" + self.name + "] " + msg.topic + " " + str(msg.payload))

    @staticmethod
    def on_publish(client, userdata, mid):
        '''The callback for when a message is published.'''
        print("[" + self.name + "] ({}s) (msgs={})".format(perf_counter(), mid))
