# Shopfloor simulation

The idea of this project is to provide a way to generate dummy data for other projects and services that depend on it, as well as make it easier to transition from dummy simulated data to real data from the Shopfloor.

This goal is achieved by utilizing a State Machine pattern to implement and execute user-defined scenarios that publish/subscribe to MQTT topics. New entities (such as a new type of robot) can be defined inside ```entities.py```, added into one of the scenarios in ```shopfloor_simulation/scenarios```, and then such scenarios can be imported and executed in ```simulation_sm.py```. MQTT settings can be changed in ```mqtt_utils.py```, and custom publish/subscribe functions can be added.

A graphics generator script called ```simulation_graphics.py``` built with Pygame is also provided as a means of visualizing data (note: graphics for the current build is failing!).


# Requirements
- Python 3
- (optional) Docker


# Execution

## Python only
1. Install Python requirements with:

   ```python -m pip install -r requirements.txt```
2. After installing the required modules, you can start the simulation with:

   ```python sm_simulation.py```

The ```simulation_sm.py``` script will continually publish data to the topics inside ```freeaim/echo```. To stop the script, use a keyboard interrupt (CTRL + C).

**Note**: you can change MQTT settings inside ```shopfloor_simulation/mqtt_utils.py```.


## (Optional) Docker
1. In this folder, run the following commands (don't forget the ```.```):

	```docker build -t simulation_sm .```
	
	```docker run -d --name simulation_sm simulation_sm```
2. To stop the container, run:

	```docker stop simulation_sm```
3. To run the container again, use:

	```docker start simulation_sm```

\* ```docker build``` might take a few minutes.
\* The ```-d``` flag means ```detached```. If you want the container to use your terminal, just remove this flag (the script prints the current state to the terminal).


# Other Info

* A State Machine diagram for Scenario01 can be found here: https://whimsical.com/shopfloor-simulation-state-machine-diagram-QUKKNykbMkyLasnx6ysvqB@2Ux7TurymLB2WJEDGpE5
* For monitoring the topics, the app MQTT-Explorer was used, available here: http://mqtt-explorer.com
* The root topic ```freeaim/echo``` is being used to publish data.

## Used icons
- Wall-e movie icons: https://dribbble.com/shots/2772860-WALL-E-Movie-Icons?utm_source=Clipboard_Shot&utm_campaign=sandor&utm_content=WALL%C2%B7E%20Movie%20Icons&utm_medium=Social_Share
- Robotic arm: https://cdn5.vectorstock.com/i/1000x1000/80/34/isolated-robotic-arm-icon-vector-21678034.jpg