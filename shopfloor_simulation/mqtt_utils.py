import paho.mqtt.client as mqtt
from time import sleep, perf_counter
import json
import jsonpickle
import copy
from random import randint
from shopfloor_simulation.entities import Structure
from shopfloor_simulation.settings import MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, MQTT_CLIENT_ID, ROOT_TOPIC
import os
from multiprocessing.pool import ThreadPool


class MqttGeneric:
    '''Generic class for MQTT protocol communication'''

    def __init__(self, host=MQTT_HOST, port=MQTT_PORT, username=MQTT_USERNAME, password=MQTT_PASSWORD,
                 run_event_check_sleep: float = 0.1, subscribed_topics: list = [], name="MQTT", root_topic=ROOT_TOPIC):
        self.client_id = MQTT_CLIENT_ID + name + "-" + str(randint(0, 1000))
        self.client = mqtt.Client(self.client_id)
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
        print("[#] " + self.name + " shutting down.")

    def on_connect(self, client, userdata, flags, rc):
        '''
            The callback for when the client receives a CONNACK response from the server.
            Subscribing in on_connect() means that if we lose the connection and reconnect then subscriptions will be renewed.
        '''
        print("[#] " + self.name + " connected with result code " + str(rc))
        for topic in self.subscribed_topics:
            client.subscribe(topic)
            print("[#] " + self.name + " subscribed to: " + topic)

    def on_message(self, client, userdata, msg):
        '''The callback for when a PUBLISH message is received from the server.'''
        print("[#] " + self.name + " " + msg.topic + " " + str(msg.payload))

    def on_publish(self, client, userdata, mid):
        '''The callback for when a message is published.'''
        print("[#] " + self.name + " ({}s) (msgs={})".format(perf_counter(), mid))


class ShopfloorPublisher(MqttGeneric):
    ''' MQTT Publisher that handles the Shopfloor's entities payloads. '''

    def __init__(self, host=MQTT_HOST, port=MQTT_PORT, username=MQTT_USERNAME, password=MQTT_PASSWORD, run_event_check_sleep=0.1, publishing_entities=[], name='MQTT', root_topic=ROOT_TOPIC):
        super().__init__(host=host, port=port, username=username, password=password,
                         run_event_check_sleep=run_event_check_sleep, subscribed_topics=[], name=name, root_topic=root_topic)
        self.publishing_entities = publishing_entities
        self.prev_payloads = {}

    def on_connect(self, client, userdata, flags, rc):
        print("[" + self.name + "] Connected with result code " + str(rc))
        for topic in self.subscribed_topics:
            client.subscribe(topic)
            print("[" + self.name + "] Subscribed to: " + topic)
        for entity in self.publishing_entities:
            if isinstance(entity, Structure):
                self.initialize_single_topic(entity)
                print("["+self.name+"] Published Structure data")

    def mqtt_loop(self, run_event):
        '''(OVERRIDDEN) Starts the MQTT communication. Updates and sends payloads every loop.'''
        self.client.loop_start()
        self.initialize_topics()
        while run_event.is_set():
            for entity in self.publishing_entities:
                self.send_payload(entity)
            sleep(self.run_event_check_sleep)
        self.client.loop_stop()
        print("[" + self.name + "] Shutting down.")

    def initialize_topics(self):
        ''' Publish all publishing_entities's payloads to their topics. '''
        # for entity in self.publishing_entities:
        #    if isinstance(entity, shopfloor_simulation.entities.SimStructure):
        #        self.initialize_single_topic(entity)
        #        sleep(3)
        for entity in self.publishing_entities:
            self.initialize_single_topic(entity)

    def initialize_single_topic(self, entity):
        ''' Publish a single entity's payload to its topic. '''
        # Encode the entity object to a JSON string
        payload = jsonpickle.encode(entity, unpicklable=False)

        # Decode the payload to a Python dict
        payload_dict = jsonpickle.decode(payload)

        # Initialize the head topic with the entire payload
        mqtt_topic = self.root_topic + \
            entity.header._namespace + "/" + entity.header._id
        self.client.publish(mqtt_topic, payload, 0)

        # Initialize the atomic topics (sub-topics) with the payload items
        for key, value in payload_dict.items():
            atomic_topic = mqtt_topic + '/' + key
            if type(value) is not str:  # Avoid escaping characters
                value = jsonpickle.encode(value)
            self.client.publish(atomic_topic, value, 0)

    def send_payload(self, entity):
        ''' Publish the entity's attributes as a JSON payload. 

        If the payload is the same as the previous one, it will be ignored.
        This function also publishes to sub-topics (called atomic topics).        
        '''

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
        self.client.publish(mqtt_topic, payload, 0)

        # Update the atomic topics as well
        self.send_payload_atomic(
            self.prev_payloads[payload_id], payload, mqtt_topic)

        # Update prev_payloads.
        self.prev_payloads[payload_id] = copy.deepcopy(payload)

    def send_payload_atomic(self, prev_payload, payload, mqtt_topic):
        ''' Split the payload into multiple atomic payloads with their own topics. 

            `prev_payload`: the previous instance of the payload.

            `payload`: the jsonpickle encoded entity (Python object).

            `mqtt_topic`: the publishing entity's topic.
        '''
        # Decode payloads to dict
        prev_payload_dict = jsonpickle.decode(prev_payload)
        payload_dict = jsonpickle.decode(payload)

        # Search for updates to publish
        for key, new_value in payload_dict.items():
            if prev_payload_dict[key] != new_value:
                # Previous value is different from current. Publish the update.
                atomic_topic = mqtt_topic + '/' + key
                if type(new_value) is not str:  # Avoid escaping characters
                    new_value = jsonpickle.encode(new_value)
                self.client.publish(atomic_topic, new_value, 0)

    def on_publish(self, client, userdata, mid):
        '''(OVERRIDDEN) The callback for when a message is published. Do nothing.'''
        pass


class MqttSubscriber(MqttGeneric):
    ''' MQTT Generic Subscriber that prints received messages. '''

    def on_message(self, client, userdata, msg):
        ''' (OVERRIDDEN) The callback for when a PUBLISH message is received from the server. '''
        try:
            content = json.loads(msg.payload.decode("utf-8"))
            print("[" + self.name + "] Received: " + str(content))
        except:
            print("[" + self.name + "] Non-JSON received: " + str(msg.payload))


class ActionBasedManager(MqttGeneric):
    ''' (deprecated) Action-based solution for receiving commands from MQTT and influencing the simulation. 

        Replaced by the JobManager, which fits scenario01 better.
    '''

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


class JobManager(MqttGeneric):
    ''' Subscribes to the Job's topic and monitors changes to their status.

        These status changes will influence the simulation flow. They represent
        the press of a button or a drag-and-drop to another field in the
        frontend's Job Board.
    '''

    def __init__(self, host=MQTT_HOST, port=MQTT_PORT, username=MQTT_USERNAME, password=MQTT_PASSWORD, run_event_check_sleep=0.1, subscribed_topics=[], name='MQTT', root_topic=ROOT_TOPIC):
        super().__init__(host=host, port=port, username=username, password=password,
                         run_event_check_sleep=run_event_check_sleep, subscribed_topics=subscribed_topics, name=name, root_topic=root_topic)
        self.job_update_queue = []

    def on_message(self, client, userdata, msg):
        '''The TwinViewer publishes messages in the topic /VR/viewer_info/tooltip when the mouse is on an object and publishes its name. 
        On /VR/viewer_info/tooltip, a message can be published that contains "tooltiplines", an array with lines to be displayed in a box.
        In this example, the name of the selected object is published.'''
        if "tooltip_request" in msg.topic:
            client.publish("/VR/viewer_info/tooltip", json.dumps({"name": "A1", "tooltiplines": [
                           "Object: <b>"+str(msg.payload.decode("utf-8"))+"</>"]}), 0)
        else:
            try:
                # A Job Status was published. Check it out.
                new_status = msg.payload.decode("utf-8")

                # The topic should be something like this: ROOT_TOPIC/jobs/<job_id>/status
                # Get the Job ID
                topic_parts = msg.topic.split('/')
                job_id = topic_parts[-2]
                self.job_update_queue.append((job_id, new_status))
            except:
                print("[" + self.name + "] Unrecognized: " + str(msg.payload))

    def update_jobs(self, job_queue: list):
        ''' Search the Job Queue and update the Jobs with their new statuses.

            Check if there are Job updates. For every one of them, search the
            `job_queue` for a matching id and apply the new status.
        '''
        if len(self.job_update_queue) > 0:
            # Loop through the new Job updates
            for (job_id, new_status) in self.job_update_queue:
                # Loop through the existing Jobs inside the job_queue
                for job in job_queue:
                    # Search for a matching id. If found, apply the new status
                    if job.header._id == job_id:
                        job.status = new_status
                        break
            # Empty the update queue
            self.job_update_queue = []


class DTVMqttClient(MqttGeneric):
    ''' 
        Handle MQTT communication for Digital Twin Viewer related scenarios.

        When the client loop starts, MQTT runs in a different thread from the
        main program. Be sure to always call client.loop_stop() to shut it down.

        If using the client in a publishing thread, calling thread.join() is enough.
    '''

    def __init__(self, scenario_manager, scenario, publishing_entities=[], host=MQTT_HOST, port=MQTT_PORT, username=MQTT_USERNAME, password=MQTT_PASSWORD, run_event_check_sleep=0.001, subscribed_topics=[], name='MQTT', root_topic=ROOT_TOPIC):
        super().__init__(host=host, port=port, username=username, password=password,
                         run_event_check_sleep=run_event_check_sleep, subscribed_topics=subscribed_topics, name=name, root_topic=root_topic)

        self.scenario_manager = scenario_manager  # A ref to the DTV Scenario Manager
        self.scenario = scenario  # A ref to the current scenario
        self.publishing_entities = publishing_entities
        self.prev_payloads = {}

    def on_message(self, client, userdata, msg):
        # The property name is the last subtopic, e.g.: ROOT_TOPIC/scenario_manager/<property>
        property_name = msg.topic.split('/')[-1]

        try:
            # Tooltip request received
            if property_name == "tooltip_request":
                # Publish the name of the selected object to the tooltip topic.
                tooltip_topic = "/VR/viewer_info/tooltip"
                content = {
                    "name": "A1",
                    "tooltiplines": [
                        "Object: <b>" +
                            str(msg.payload.decode("utf-8")) + "</>"
                    ]
                }
                client.publish(tooltip_topic, json.dumps(content), 0)

            # New Job status received
            elif property_name == "status":
                # A Job Status was published. Check it out.
                new_status = msg.payload.decode("utf-8")

                # The topic should be something like this: ROOT_TOPIC/jobs/<job_id>/status
                # Get the Job ID and append it to the update queue
                topic_parts = msg.topic.split('/')
                job_id = topic_parts[-2]
                self.scenario.job_update_queue.append((job_id, new_status))

            # New flexibility value for the Scenario Manager received
            elif property_name == "selected_flexibility":
                self.scenario_manager.selected_flexibility = int(
                    float(msg.payload))

            # Scenario Manager's is_enabled property
            elif property_name == "is_enabled":
                new_is_enabled = msg.payload.decode("utf-8")
                if new_is_enabled == "false":
                    self.scenario_manager.is_enabled = False
                else:
                    self.scenario_manager.is_enabled = True

            elif property_name == "action_message":
                action_message = msg.payload.decode("utf-8")
                if action_message == "BREAKDOWN":
                    # Signal breakdown
                    print("Breakdown request received.")
                    pass
                elif action_message == "CREATE_JOB":
                    # Signal creation of new Job.
                    print("Create Job request received.")
                    #! For now, create a new Job here with no PS
                    self.scenario.create_job(
                        self.scenario, "Porsche-Thingworx", [])

        except:
            print("[!] " + self.name + " raised an Exception when processing a value from " +
                  msg.topic + ". Is it of the correct type? Payload: " + str(msg.payload))

    def on_connect(self, client, userdata, flags, rc):
        """
            For the DTV, it's necessary to initialize the Structure topic upon
            connection, so that the DTV knows which topics it needs to subscribe to.
        """
        print("[#] " + self.name + " connected with result code " + str(rc))
        for topic in self.subscribed_topics:
            client.subscribe(topic)
            print("[#] " + self.name + " subscribed to: " + topic)

        # Initialize structure topics
        structures = [
            x for x in self.publishing_entities if isinstance(x, Structure)]
        for structure in structures:
            self.initialize_single_topic(structure)
            print("[#] " + self.name + " initialized " +
                  structure.header.name + " data")
        sleep(3)  # Delay so that the DTV subscribes to the topics

    def publish_thread(self, run_event):
        ''' Starts the MQTT communication. Updates and sends payloads every loop.'''
        self.client.loop_start()
        self.initialize_topics()

        # Publishing loop
        while run_event.is_set():
            for entity in self.publishing_entities:
                self.send_payload(entity)
            sleep(self.run_event_check_sleep)

        # Stop MQTT
        self.client.loop_stop()
        print("[#] " + self.name + " shutting down.")

    def initialize_topics(self):
        ''' Publish all publishing_entities's payloads to their topics. '''
        for entity in self.publishing_entities:
            self.initialize_single_topic(entity)

    def initialize_single_topic(self, entity):
        ''' Publish a single entity's payload to its topic. '''
        # Encode the entity object to a JSON string
        payload = jsonpickle.encode(entity, unpicklable=False)

        # Decode the payload to a Python dict
        payload_dict = jsonpickle.decode(payload)

        # Initialize the head topic with the entire payload
        mqtt_topic = self.root_topic + \
            entity.header._namespace + "/" + entity.header._id
        self.client.publish(mqtt_topic, payload, 0)

        # Initialize the atomic topics (sub-topics) with the payload items
        for key, value in payload_dict.items():
            atomic_topic = mqtt_topic + '/' + key
            if type(value) is not str:  # Avoid escaping characters
                value = jsonpickle.encode(value)
            self.client.publish(atomic_topic, value, 0)

    def send_payload(self, entity):
        ''' Publish the entity's attributes as a JSON payload. 

        If the payload is the same as the previous one, it will be ignored.
        This function also publishes to sub-topics (called atomic topics).        
        '''

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
        self.client.publish(mqtt_topic, payload, 0)

        # Update the atomic topics as well
        self.send_payload_atomic(
            self.prev_payloads[payload_id], payload, mqtt_topic)

        # Update prev_payloads.
        self.prev_payloads[payload_id] = copy.deepcopy(payload)

    def send_payload_atomic(self, prev_payload, payload, mqtt_topic):
        ''' Split the payload into multiple atomic payloads with their own topics. 

            `prev_payload`: the previous instance of the payload.

            `payload`: the jsonpickle encoded entity (Python object).

            `mqtt_topic`: the publishing entity's topic.
        '''
        # Decode payloads to dict
        prev_payload_dict = jsonpickle.decode(prev_payload)
        payload_dict = jsonpickle.decode(payload)

        # Search for updates to publish
        for key, new_value in payload_dict.items():
            if prev_payload_dict[key] != new_value:
                # Previous value is different from current. Publish the update.
                atomic_topic = mqtt_topic + '/' + key
                if type(new_value) is not str:  # Avoid escaping characters
                    new_value = jsonpickle.encode(new_value)
                self.client.publish(atomic_topic, new_value, 0)

    def on_publish(self, client, userdata, mid):
        '''The callback for when a message is published. Do nothing.'''
        pass
