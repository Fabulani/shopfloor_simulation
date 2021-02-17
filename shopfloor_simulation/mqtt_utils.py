import paho.mqtt.client as mqtt
from time import sleep, perf_counter
import json
import jsonpickle
import copy


''' MQTT Connection setup. '''
# Public brokers: https://github.com/mqtt/mqtt.org/wiki/public_brokers
MQTT_HOST = "mqtt.flespi.io"
MQTT_PORT = 1883
MQTT_USERNAME = ""
MQTT_PASSWORD = ""
ROOT_TOPIC = "freeaim/echo/"


class MqttGeneric:
    '''Generic class for MQTT protocol communication'''

    def __init__(self, host=MQTT_HOST, port=MQTT_PORT, username=MQTT_USERNAME, password=MQTT_PASSWORD,
                 run_event_check_sleep: float = 0.1, subscribed_topics: list = [], name="MQTT", root_topic=ROOT_TOPIC):
        self.client = mqtt.Client()
        self.client.username_pw_set(username, password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish
        self.client.connect(host, port, 60)
        self.subscribed_topics = subscribed_topics
        self.run_event_check_sleep = run_event_check_sleep
        self.name = name
        self.root_topic = root_topic

    def mqtt_loop(self, run_event):
        '''
            Starts the MQTT communication. Designed to be used with the threading library. Shuts down when the run_event is cleared.
            Example call:

            run_event = threading.Event()
            run_event.set()

            mqtt_manager = MqttManager(MQTT_HOST, MQTT_PORT)
            mqtt_thread = threading.Thread(
                target=mqtt_manager.mqtt_loop, args=[run_event])
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

    def on_message(self, client, userdata, msg):
        '''The callback for when a PUBLISH message is received from the server.'''
        print("[" + self.name + "] " + msg.topic + " " + str(msg.payload))

    def on_publish(self, client, userdata, mid):
        '''The callback for when a message is published.'''
        print("[" + self.name + "] ({}s) (msgs={})".format(perf_counter(), mid))


class ShopfloorPublisher(MqttGeneric):
    ''' MQTT Publisher that handles the Shopfloor's entities payloads. '''

    def __init__(self, host=MQTT_HOST, port=MQTT_PORT, username=MQTT_USERNAME, password=MQTT_PASSWORD, run_event_check_sleep=0.1, publishing_entities=[], name='MQTT', root_topic=ROOT_TOPIC):
        super().__init__(host=host, port=port, username=username, password=password,
                         run_event_check_sleep=run_event_check_sleep, subscribed_topics=[], name=name, root_topic=root_topic)
        self.publishing_entities = publishing_entities
        self.prev_payloads = {}

    def mqtt_loop(self, run_event):
        '''(OVERRIDDEN) Starts the MQTT communication. Updates and sends payloads every loop.'''
        self.client.loop_start()
        sleep(1)
        while run_event.is_set():
            for entity in self.publishing_entities:
                self.send_payload(entity)
                sleep(0.01)
            sleep(self.run_event_check_sleep)
        self.client.loop_stop()
        print("[" + self.name + "] Shutting down.")

    def send_payload(self, entity):
        '''Publish the entity's attributes as a JSON payload. If the payload is the same as the previous one, it will be ignored.'''

        # Encode the entity object to JSON format
        payload = jsonpickle.encode(entity, unpicklable=False)

        # The payload id is used to verify if the new payload is different from its previous instance.
        payload_id = entity.header._id

        # Verify if the payload exists in the prev_payload dict. If it does, check if the new and the prev are different.
        if payload_id not in self.prev_payloads:
            # Payload hasn't been registered yet. Register it.
            self.prev_payloads[payload_id] = copy.deepcopy(payload)
        else:
            # A payload with the same id already exists. Check if they're different.
            prev_payload = self.prev_payloads[payload_id]
            if payload == prev_payload:
                # The new payload is the same as its previous instance. Do nothing and return.
                return

        # Publish the new payload.
        mqtt_topic = self.root_topic + \
            entity.header._namespace + "/" + entity.header._id
        self.client.publish(
            mqtt_topic, payload, 0)

        # Update previous payload.
        self.prev_payloads[payload_id] = copy.deepcopy(payload)

    def on_publish(self, client, userdata, mid):
        '''(OVERRIDDEN) The callback for when a message is published. Do nothing.'''
        pass


class ShopfloorSubscriber(MqttGeneric):
    ''' MQTT Subscriber that influences the simulation according to received messages. '''

    def on_message(self, client, userdata, msg):
        ''' (OVERRIDDEN) The callback for when a PUBLISH message is received from the server. '''
        try:
            content = json.loads(msg.payload.decode("utf-8"))
            print("[" + self.name + "] Received: " + str(content))
        except:
            print("[" + self.name + "] Unrecognized: " + str(msg.payload))


class ShopfloorManager(MqttGeneric):
    ''' Receives commands from MQTT and influences the simulation accordingly. '''

    def __init__(self, host=MQTT_HOST, port=MQTT_PORT, username=MQTT_USERNAME, password=MQTT_PASSWORD, run_event_check_sleep=0.1, subscribed_topics=[], name='MQTT', root_topic=ROOT_TOPIC):
        super().__init__(host=host, port=port, username=username, password=password,
                         run_event_check_sleep=run_event_check_sleep, subscribed_topics=subscribed_topics, name=name, root_topic=root_topic)
        self.prev_action = ""
        self.action_queue = []

    def on_message(self, client, userdata, msg):
        ''' (OVERRIDDEN) The callback for when a PUBLISH message is received from the server. '''
        try:
            content = json.loads(msg.payload.decode("utf-8"))
            if "action" in content:
                self.action_queue.append(content["action"])
        except:
            print("[" + self.name + "] Unrecognized: " + str(msg.payload))

    def next_action(self):
        ''' Return the next action from the action queue, but only if it's different from the previous action. '''
        while len(self.action_queue) > 0:
            # There are new actions in the queue.
            next_action = self.action_queue[0]
            if next_action != self.prev_action:
                # New action received. Update prev_action and pop the new action from the queue.
                self.prev_action = next_action
                return self.action_queue.pop(0)
            else:
                # Repeated action received. Pop it from the list, but return an empty string.
                self.action_queue.pop(0)
        else:
            # No new actions in the queue.
            return ""
