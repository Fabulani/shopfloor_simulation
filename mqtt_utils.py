import paho.mqtt.client as mqtt
from time import sleep


class MqttGeneric():
    '''Handles MQTT protocol communication'''
    def __init__(self, host:str, port:int, username:str="", password:str="", mqtt_sleep:float=1, subscribed_topics:list=[]):
        '''ATTENTION: The default init parameters are for a public MQTT broker. NEVER send sensitive data to this address!'''
        self.client = mqtt.Client()
        self.client.username_pw_set(username, password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish
        self.client.connect(host, port, 60)
        self.mqtt_sleep = mqtt_sleep  # Amount of time between MQTT run_event checks
        self.subscribed_topics = subscribed_topics

    def mqtt_loop(self, run_event):
        '''
            Starts the MQTT communication. Designed to be used with the threading library. Shuts down when the run_event is cleared.
            If the MQTT Manager will be used just for subscribing and receiving data, then this method will work fine.
            But if the MQTT Manager has to publish data, this method should be overridden to implement that.

            `run_event`: event used to sync thread shutdown.    
        '''
        self.client.loop_start()
        while run_event.is_set():
            sleep(self.mqtt_sleep)
        self.client.loop_stop()
        print("[MQTT] Shutting down.")

    def on_connect(self, client, userdata, flags, rc):
        '''
            The callback for when the client receives a CONNACK response from the server.
            Subscribing in on_connect() means that if we lose the connection and reconnect then subscriptions will be renewed.
        '''
        print("Connected with result code " + str(rc))
        for topic in self.subscribed_topics:
            client.subscribe(topic)
    
    @staticmethod
    def on_message(client, userdata, msg):
        '''The callback for when a PUBLISH message is received from the server.'''
        print(msg.topic + " " + str(msg.payload))

    @staticmethod
    def on_publish(client, userdata, mid):
        '''The callback for when a message is published.'''
        print("[MQTT] ({}s) (msgs={})".format(time.perf_counter(), mid))
