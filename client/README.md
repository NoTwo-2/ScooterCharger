# Setup

Please add setup instructions here!

# Setup the Pi for Temperature Sensor
1. In the Pi boot/config.txt file add the following line at the bottom:
dtoverlay=w1-gpio
2. Run the following commands:
   sudo modprobe w1-gpio
   sudo modprobe w1-thermo

# Setting up the Pi so it can take in input from the arduino:
Needs to be finished (dont know the exact buttons off of the top of my head)


# Something about a boot script idk
