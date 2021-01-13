### [REQUIREMENTS] ###
- Python 3


### [EXECUTION] ###
(Windows instructions)
1. Open the Windows cmd prompt in this folder.
2. Type "python -m pip install -r requirements.txt" (recommended to do this inside a Python virtual environment).
3. After installing the required modules, execute the script with:
	python sm_simulation.py
4. (optional) Open another terminal and execute "python draw_simulation.py" to open a window that'll get data from MQTT and draw the simulation. Use this for quick testing and visualization.

The sm_simulation script will continually publish data to the topics inside "freeaim/echo". To stop the script, use a keyboard interrupt (CTRL + C).

The draw_simulation script will open a window and continually draw the simulation using data from MQTT. To stop the script, you can either use a keyboard interrupt or close the window.

* Note: the MQTT host server is public, so anyone can publish/read. It's being used for now to handle the dummy data, but we'll setup our own internal servers once the shop floor is properly set up.


### [MQTT APP] ###
For monitoring the topics, the app MQTT-Explorer was used, available here: http://mqtt-explorer.com

After downloading it, you just need to click on "connect" in the respective host tab and type "freeaim" in the search bar to monitor these topics.

Host: "mqtt.eclipse.org"
Port: 1883
User/Pass: "" (none, empty)
Topics: "freeaim/echo/<ThingName>", where <ThingName> is the name of the Thing in Thingworx.

Alternative host: "mqtt.fluux.io" (currently being used)


### [Icons used] ###
- Wall-e movie icons: https://dribbble.com/shots/2772860-WALL-E-Movie-Icons?utm_source=Clipboard_Shot&utm_campaign=sandor&utm_content=WALL%C2%B7E%20Movie%20Icons&utm_medium=Social_Share
- Robotic arm: https://cdn5.vectorstock.com/i/1000x1000/80/34/isolated-robotic-arm-icon-vector-21678034.jpg