import pygame
import paho.mqtt.client as mqtt
import json
import threading
from time import sleep
from shopfloor_simulation.mqtt_utils import MqttGeneric

# Initialize pygame
pygame.init()

# Topics to subscribe to. Entity data will be collected from these.
subscribed_topics = ["freeaim/echo/+"]

# Display information
display_width = 1144
display_height = 816
display = pygame.display.set_mode((display_width, display_height))
pygame.display.set_caption('Shopfloor Simulation')
font = pygame.font.SysFont("monospace", 18)
FPS = 60

# Clock
display_clock = pygame.time.Clock()

# Images
IMG_SIZE = (60, 60)
bg = pygame.image.load("shopfloor_simulation/img/shopfloor2.PNG")
legend = pygame.image.load("shopfloor_simulation/img/legend.PNG")
legend = pygame.transform.scale(legend, (300, 132))  # Aspect ratio = 389:300
A1_img = pygame.image.load("shopfloor_simulation/img/agv.png")
A1_img = pygame.transform.scale(A1_img, IMG_SIZE)
M1_img = pygame.image.load("shopfloor_simulation/img/mobile.png")
M1_img = pygame.transform.scale(M1_img, IMG_SIZE)
M2_img = pygame.image.load("shopfloor_simulation/img/mobile.png")
M2_img = pygame.transform.scale(M2_img, IMG_SIZE)
pygame.display.set_icon(A1_img)

# Globals (data buffers for data exchange between MQTT Manager and the Simulation Objects)
A1_data = {"pos_x": 650, "pos_y": 160}
M1_data = {"pos_x": 450, "pos_y": 590}
M2_data = {"pos_x": 450, "pos_y": 485}
J1_data = {
    "status": "waiting for mqtt...",
    "current_progress": "waiting for mqtt...",
    "current_step": "waiting for mqtt...",
    "pending": "waiting for mqtt...",
    "completed": "waiting for mqtt..."
}


# Main Class
class MainRun(object):
    def __init__(self, display_width, display_height):
        self.dw = display_width
        self.dh = display_height
        self.Main()

    def Main(self):
        # Threading: create event for syncing thread shut down.
        run_event = threading.Event()
        run_event.set()

        # Connect to MQTT
        mqtt_manager = MqttManager(subscribed_topics=subscribed_topics)
        mqtt_thread = threading.Thread(
            target=mqtt_manager.mqtt_loop, args=[run_event])
        mqtt_thread.start()

        # Simulation Objects
        A1 = SimulationObject(650, 160, A1_img)
        M1 = SimulationObject(450, 590, M1_img)
        M2 = SimulationObject(450, 485, M2_img)

        # Draw everything
        A1.draw()
        M1.draw()
        M2.draw()

        while True:
            try:
                display.blit(bg, (0, 0))
                display.blit(self.update_fps(), (1050, 0))
                display.blit(legend, (770, 670))

                # Job information
                self.update_job_info()

                # Event Tasking
                # Add all your event tasking things here
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.shutdown_simulation(run_event, mqtt_thread)

                # Add things like player updates here
                # Also things like score updates or drawing additional items
                # Remember things on top get done first so they will update in the order yours is set at
                A1.move(x=A1_data["pos_x"], y=A1_data["pos_y"])
                A1.draw()

                M1.move(x=M1_data["pos_x"], y=M1_data["pos_y"])
                M1.draw()

                M2.move(x=M2_data["pos_x"], y=M2_data["pos_y"])
                M2.draw()

                # Remember to update your clock and display at the end
                pygame.display.update()
                display_clock.tick(60)

            # If you need to reset variables here
            # This includes things like score resets

            except KeyboardInterrupt:
                self.shutdown_simulation(run_event, mqtt_thread)

    # After your main loop throw in extra things such as a main menu or a pause menu
    # Make sure you throw them in your main loop somewhere where they can be activated by the user
    def shutdown_simulation(self, run_event, mqtt_thread):
        '''
        Shutdown the program.

        `run_event`: an event variable for syncing thread shutdown.

        `mqtt_thread`: thread used by the MQTT Manager.
        '''
        # Clear the run_event to shutdown threads.
        run_event.clear()

        # Wait for the threads to finish
        mqtt_thread.join()

        print("[THREADS] All threads closed. Exiting main thread.")
        pygame.quit()
        quit()

    def update_fps(self):
        '''Generate a FPS counter to be drawn in the corner of the display.'''
        fps = "fps: " + str(int(display_clock.get_fps()))
        fps_text = font.render(fps, 1, pygame.Color("coral"))
        return fps_text

    def update_job_info(self):
        job_x = 50
        job_y = 670
        display.blit(font.render(
            "[Job]", 1, pygame.Color("black")), (job_x, job_y))
        display.blit(font.render(
            "-Status: " + J1_data["status"], 1, pygame.Color("black")), (job_x, job_y + 20))
        display.blit(font.render("-Current Step: " +
                                 J1_data["current_step"], 1, pygame.Color("black")), (job_x, job_y + 40))
        display.blit(font.render(
            "-Pending: " + str(J1_data["pending"]), 1, pygame.Color("black")), (job_x, job_y + 60))
        display.blit(font.render(
            "-Completed: " + str(J1_data["completed"]), 1, pygame.Color("black")), (job_x, job_y + 80))
        display.blit(font.render(
            "-Progress: " + str(J1_data["current_progress"]) + "%", 1, pygame.Color("black")), (job_x, job_y + 100))

# All player classes and object classes should be made outside of the main class and called inside the class


class SimulationObject(object):
    '''Object to be drawn in the simulation.'''

    def __init__(self, x, y, image):
        self.x = x
        self.y = y
        self.image = image
        self.pos = image.get_rect()
        self.pos.centerx = self.x
        self.pos.centery = self.y

    def draw(self):
        '''Draw the object on the display.'''
        display.blit(self.image, self.pos)

    def move(self, x, y):
        '''Move the object to a new position. It'll need to be redrawn for the change to be visible.'''
        display.blit(display, self.pos, self.pos)
        self.pos.centerx = x
        self.pos.centery = y


class MqttManager(MqttGeneric):
    '''Handles MQTT protocol communication'''
    @staticmethod
    def on_message(client, userdata, msg):
        '''
            (OVERRIDDEN) The callback for when a PUBLISH message is received from the server.
            The message contents is assigned to the correct global variable by checking the "name" property.
            @static is added so it doesn't require "self"
        '''
        try:
            global A1_data, M1_data, M2_data, S1_data, J1_data
            content = json.loads(msg.payload.decode("utf-8"))

            if content["name"] == "A1":
                A1_data = content
            elif content["name"] == "M1":
                M1_data = content
            elif content["name"] == "M2":
                M2_data = content
            elif content["name"] == "J1":
                J1_data = content

        # Basic exception handling. Needs to be replaced with the "logging" module.
        except Exception as exc:
            print("[ERROR] {}".format(exc))


# Run everything
if __name__ == "__main__":
    MainRun(display_width, display_height)
